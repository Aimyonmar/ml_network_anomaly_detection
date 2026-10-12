"""CIC-IDS2017 数据加载与清洗（V2，被 train_v2 / threshold_optimizer 共用）。

清洗口径（全部如实计数打印，坏数据也不许静默丢弃——CONTEXT §6 记录规范）：
- 列名 strip（官方 CSV 有前导空格怪癖）
- 流特征列转数值，无法解析的值 → NaN 计数报告
- Flow Bytes/s / Flow Packets/s 存在 Inf（CICFlowMeter 除零产物）→ 一并按 NaN 处理
- 含 NaN 的行整行剔除（数量打印；CIC-IDS2017 官方数据约有数千行此情况）
- label 二值化：BENIGN→0(Normal)，其余→1(Attack)（schema_registry 口径）

数据来源：MachineLearningCSV.zip 解压后的 MachineLearningCVE/*.csv
（官方直链 http://205.174.165.80/CICDataset/CIC-IDS-2017/Dataset/MachineLearningCSV.zip）
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.schema_registry import load_cicids_schema

DATA_DIR = Path(__file__).resolve().parent / "data" / "cicids" / "MachineLearningCVE"


def load_cicids_dataframe(data_dir: Path | str = DATA_DIR, sample: int = 0) -> pd.DataFrame:
    """加载全部 CSV（或 sample>0 时随机抽样行数），清洗并二值化 label。

    返回列：feature_cols... + "label"(0/1)。随机抽样 seed=42，只用于快速冒烟，
    正式训练用全量（sample=0）。
    """
    data_dir = Path(data_dir)
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(
            f"未找到 CIC-IDS2017 CSV：{data_dir} 为空。\n"
            f"请下载 MachineLearningCSV.zip 解压到该目录（官方直链见模块 docstring）。"
        )

    parts = [pd.read_csv(f, low_memory=False) for f in csvs]
    df = pd.concat(parts, ignore_index=True)
    # 官方 CSV 列名带前导空格（如 ' Destination Port'），统一 strip
    df.columns = [str(c).strip() for c in df.columns]

    print(f"[data] 读入 {len(csvs)} 个 csv，共 {len(df)} 行")

    schema = load_cicids_schema(list(df.columns))
    feats = schema.feature_cols

    # 特征转数值：无法解析的 → NaN（注意：字符串 'Infinity' 会被解析成 float inf，isna 抓不到）
    for col in feats:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    arr = df[feats].to_numpy(dtype=np.float64, na_value=np.nan)
    # NaN/±Inf（CICFlowMeter 除零产物）整行剔除
    nonfinite_mask = ~np.isfinite(arr).all(axis=1)
    # 超出 float32 上限的有限大数：sklearn 内部转 float32 会溢出成 inf，同样剔除
    over_f32_mask = (np.abs(arr) > np.finfo(np.float32).max).any(axis=1)
    bad_mask = nonfinite_mask | over_f32_mask
    bad_count = int(bad_mask.sum())
    if bad_count:
        print(
            f"[data] 剔除 NaN/Inf/超 float32 大数行 {bad_count} 行"
            f"（NaN/Inf={int(nonfinite_mask.sum())}，超限={int(over_f32_mask.sum())}，如实记录）"
        )
        df = df[~bad_mask]

    # label 二值化（BENIGN→0，其余→1）
    df["label"] = df["Label"].map(lambda v: 1 if schema.is_attack_label(v) else 0).astype(int)

    dist = df["label"].value_counts().to_dict()
    print(f"[data] label 分布：Normal(0)={dist.get(0, 0)} Attack(1)={dist.get(1, 0)}")

    if sample and sample > 0 and len(df) > sample:
        df = df.sample(n=sample, random_state=42).reset_index(drop=True)
        print(f"[data] 冒烟抽样：{sample} 行（random_state=42，非正式训练口径）")

    keep = feats + ["label"]
    return df[keep].copy(), feats  # type: ignore[return-value]


def make_split(df: pd.DataFrame, feats: list[str], test_size: float = 0.2):
    """规则 1：split 先行（任何预处理之前），stratify + random_state=42。"""
    from sklearn.model_selection import train_test_split

    X = df[feats].astype(np.float64)
    y = df["label"]
    return train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)
