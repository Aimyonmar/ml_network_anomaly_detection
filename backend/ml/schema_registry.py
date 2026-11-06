"""数据集 schema 注册表（V2 产品化，Gap 1：多格式输入）。

三种 schema：
- nslkdd    : v1 模型的 41 列（从 features.json 动态读取，与 v1 模型锁定同步）
- cicids2017: CIC-IDS2017 MachineLearningCVE / TrafficLabelling CSV。
              特征列从表头自动派生（列名去空白，兼容官方 CSV 前导空格怪癖），
              排除元数据列后全部按数值特征处理。
- flow      : 本系统 pcap 流特征提取器（flow_extract.py）产出的记录，
              命名对齐 cicids2017；缺失特征按默认值 0 填充。

诚实声明（进产品页）：flow 是 cicids2017 全量特征的降级子集，
无法复刻 CICFlowMeter 的 Subflow/Bulk/Active/Idle 等派生统计，缺失列填 0。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ML_DIR = Path(__file__).resolve().parent

# CIC-IDS2017 中的元数据列（strip 后比较）：不作为模型特征
CICIDS_META_COLS = {
    "label", "flow id", "source ip", "source port",
    "destination ip", "timestamp", "protocol",
}
# CIC-IDS2017 的 label 取值：BENIGN → Normal，其余（DDoS/DoS Hulk/SSH-Patator...）→ Attack
CICIDS_NORMAL_LABELS = {"benign"}


@dataclass
class DatasetSchema:
    """一个数据集的模型输入契约。"""
    name: str
    feature_cols: list[str]
    categorical_cols: frozenset[str] = frozenset()
    src_ip_col: str | None = None        # 有源 IP 列 → 告警 src_key 用它；None → 用行号引用
    defaults: dict[str, float] = field(default_factory=dict)  # 缺失特征默认填充值

    def is_attack_label(self, raw) -> bool:
        """label 二值化：nslkdd 'normal' / cicids 'BENIGN' → Normal，其余 → Attack。"""
        return str(raw).strip().lower() not in CICIDS_NORMAL_LABELS | {"normal"}

    def fill_defaults(self, record: dict) -> dict:
        """把记录补齐到本 schema 的完整特征列（缺失列按 defaults 填充，多余列剔除）。"""
        out = {}
        for col in self.feature_cols:
            if col in record:
                out[col] = record[col]
            elif col in self.defaults:
                out[col] = self.defaults[col]
            else:
                out[col] = 0
        return out


def load_nslkdd_schema(features_path: Path | str | None = None) -> DatasetSchema:
    """v1 schema：41 列直接读 v1 模型的 features.json（冻结资产，保持同步）。"""
    p = Path(features_path) if features_path else ML_DIR / "features.json"
    cfg = json.loads(Path(p).read_text(encoding="utf-8"))
    cats = {f["name"] for f in cfg["features"]
            if f.get("type") == "categorical" and f.get("type") != "target"}
    feats = [f["name"] for f in cfg["features"] if f["type"] != "target"]
    # nslkdd 无源 IP 列（连接级统计特征），告警 src_key 回退为行号引用
    return DatasetSchema(name="nslkdd", feature_cols=feats,
                         categorical_cols=frozenset(cats), src_ip_col=None)


def load_cicids_schema(columns: list[str]) -> DatasetSchema:
    """cicids2017 schema：特征列从表头自动派生（strip 空白）。"""
    stripped = [c.strip() for c in columns]
    feats = [s for s in stripped if s.lower() not in CICIDS_META_COLS]
    src_ip = "Source IP" if "Source IP" in stripped else None
    return DatasetSchema(name="cicids2017", feature_cols=feats,
                         categorical_cols=frozenset(), src_ip_col=src_ip)


def get_flow_schema(model_feature_cols: list[str]) -> DatasetSchema:
    """flow schema：特征列 = 当前生效模型（v2/cicids2017）的特征契约。

    flow_extract 只产出其中可计算子集，其余由 fill_defaults 填 0。
    源 IP 由 flow_extract 以 _src_ip 侧带字段交付，不进特征。
    """
    return DatasetSchema(name="flow", feature_cols=list(model_feature_cols),
                         categorical_cols=frozenset(), src_ip_col=None,
                         defaults={c: 0.0 for c in model_feature_cols})


def sniff_schema(df: pd.DataFrame) -> tuple[DatasetSchema, pd.DataFrame]:
    """按表头嗅探 csv 属于哪个 schema，返回 (schema, 清洗后的 DataFrame)。

    判定顺序（与 v1 行为完全兼容）：
    1. 列集合 == nslkdd 41 列 → nslkdd（原样返回，v1 链路零改动）
    2. strip 后含 'Label' → cicids2017（列名规范化为 strip 后形式）
    3. 否则报错并给出明确指引
    """
    nslkdd = load_nslkdd_schema()
    cols = list(df.columns)
    if len(cols) == 41 and set(cols) == set(nslkdd.feature_cols):
        return nslkdd, df
    stripped = [str(c).strip() for c in cols]
    if "Label" in stripped:
        df = df.copy()
        df.columns = stripped
        return load_cicids_schema(stripped), df
    raise ValueError(
        f"无法识别 csv 列结构（表头 {len(cols)} 列）：既不是 nslkdd 41 列表头，"
        f"也不含 CIC-IDS2017 的 Label 列。请检查文件来源或改用 .pcap 上传。"
    )
