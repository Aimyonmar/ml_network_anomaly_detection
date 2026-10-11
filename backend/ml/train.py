"""离线训练脚本（不随 web 启动）。

用法（cwd=backend/）：
    python -m ml.train --data ml/data/KDDTrain+.csv

严格遵守 CONTEXT.md 第 5 节 ML 硬规则：
1. train_test_split 是第一步（stratify=y, random_state=42），在任何预处理之前
2. 预处理全部包在 Pipeline 里，杜绝泄漏
3. 不只报 accuracy：输出各类 P/R/F1、混淆矩阵、ROC-AUC、全猜多数类基线
4. 先打印 label 分布，再决定 class_weight 并说明理由
6. 同时产出 model.pkl + 回填 features.json（列序）
8. 指标 >99.5% 时主动怀疑泄漏并打印排查清单
10. 随机森林默认参数，锁死不调参
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")  # 无窗口环境，仅保存图片
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# NSL-KDD 官方 41 列名（文件无表头，最后一列为攻击名字符串）
NSL_KDD_COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate",
    "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]

CATEGORICAL_FEATURES = ["protocol_type", "flag", "service"]
TARGET = "label"
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
FEATURES_JSON = Path(__file__).resolve().parent / "features.json"
ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根


def load_dataset(path: str) -> pd.DataFrame:
    """加载 NSL-KDD csv（无表头，42 列 = 41 特征 + 攻击名）。

    原始 label 列是攻击名字符串（normal / neptune / smurf ...），
    这里二值化：normal=0，其余=1（泄漏规则：只留这一列作标签，
    绝不把 attack 细分名/malicious 等辅助列混进特征）。
    """
    names = NSL_KDD_COLUMNS + ["attack_name"]
    df = pd.read_csv(path, header=None, names=names)
    df[TARGET] = (df["attack_name"] != "normal").astype(int)
    df = df.drop(columns=["attack_name"])
    return df


def train_model(dataset: pd.DataFrame) -> Pipeline:
    """按硬规则训练随机森林（默认参数，锁死）。"""
    y = dataset[TARGET].astype(int)
    X = dataset.drop(columns=[TARGET])
    numeric = [c for c in X.columns if c not in CATEGORICAL_FEATURES]

    # 规则 1：split 必须是第一步，在任何预处理之前
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # 规则 4：先打印分布，再决定 class_weight
    n_normal, n_attack = int((y_train == 0).sum()), int((y_train == 1).sum())
    ratio = max(n_normal, n_attack) / min(n_normal, n_attack)
    class_weight = "balanced" if ratio > 1.5 else None
    print(f"[分布] 训练集 正常={n_normal} 攻击={n_attack} 比例 1:{ratio:.2f}")
    print(f"[决策] class_weight={class_weight}（阈值 1.5:1，未超限则不干预）")

    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", "passthrough", numeric),
        ]
    )
    pipe = Pipeline(
        steps=[
            ("preprocess", pre),
            ("model", RandomForestClassifier(
                class_weight=class_weight, random_state=42
            )),  # 规则 10：默认参数
        ]
    )
    pipe.fit(X_train, y_train)
    return pipe, (X_test, y_test)


def evaluate(pipe: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """规则 3：全指标 + 基线对照；规则 8：高指标泄漏自查。"""
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=["Normal", "Attack"], output_dict=True)
    cm = confusion_matrix(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    baseline = max(y_test.value_counts()) / len(y_test)  # 全猜多数类

    print("\n=== 测试集评估 ===")
    print(f"基线（全猜多数类）: Acc = {baseline:.4f}")
    print(f"随机森林:          Acc = {acc:.4f} | ROC-AUC = {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Attack"], digits=4))
    print(f"混淆矩阵 [[TN FP],[FN TP]] = {cm.tolist()}")

    if acc > 0.995:
        print("\n⚠️ Acc > 99.5%，按规则 8 主动怀疑数据泄漏，排查清单：")
        print("  1. attack/malicious 列是否混进了特征（本脚本已显式剔除）")
        print("  2. 预处理是否在 split 之前 fit 了全量（本脚本用 Pipeline 保证否）")
        print("  3. 数据集是否有重复行（train/test 同源拷贝）")
        print("  4. label 是否可由某单列直接推出（如 malicious 列泄漏）")

    return {
        "accuracy": round(acc, 4),
        "roc_auc": round(auc, 4),
        "baseline_majority": round(baseline, 4),
        "per_class": {
            k: {m: round(v[m], 4) for m in ("precision", "recall", "f1-score")}
            for k, v in report.items() if k in ("Normal", "Attack")
        },
        "confusion_matrix": cm.tolist(),
        "n_test": int(len(y_test)),
    }


def save_artifacts(pipe: Pipeline, features: list[str], metrics: dict,
                   cross_test_metrics: dict | None = None) -> None:
    """规则 6：产出 model.pkl + 回填 features.json 列序与 model 块。"""
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, ARTIFACTS / "model.pkl")

    cfg = json.loads(FEATURES_JSON.read_text(encoding="utf-8"))
    cfg["features"] = [
        {"name": c, "type": "categorical" if c in CATEGORICAL_FEATURES else "numeric",
         "dtype": "str" if c in CATEGORICAL_FEATURES else "float64"}
        for c in features
    ] + [{"name": TARGET, "type": "target", "dtype": "int64",
          "_comment": "0=正常 1=异常"}]
    cfg["model"] = {
        "algorithm": "random_forest",
        "version": "1.0.0",
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "n_features": len(features),
        "accuracy": metrics["accuracy"],
        "roc_auc": metrics["roc_auc"],
    }
    if cross_test_metrics is not None:
        cfg["model"]["cross_test"] = {
            "dataset": cross_test_metrics["dataset"],
            "accuracy": cross_test_metrics["accuracy"],
            "roc_auc": cross_test_metrics["roc_auc"],
        }
    FEATURES_JSON.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # 混淆矩阵图（设计文档素材，按图号命名入 screenshots/）
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(metrics["confusion_matrix"], cmap="Blues")
    ax.set_xticks([0, 1], ["Normal", "Attack"])
    ax.set_yticks([0, 1], ["Normal", "Attack"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix (NSL-KDD test split)")
    cm_list = metrics["confusion_matrix"]
    vmax = max(max(row) for row in cm_list)
    for i in range(2):
        for j in range(2):
            v = cm_list[i][j]
            ax.text(j, i, str(v), ha="center", va="center",
                    color="white" if v > vmax / 2 else "black")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    shot_dir = ROOT / "screenshots"
    shot_dir.mkdir(exist_ok=True)
    fig.savefig(shot_dir / "图5-1_混淆矩阵.png", dpi=150)
    print(f"\n[产物] {ARTIFACTS / 'model.pkl'}")
    print(f"[产物] {FEATURES_JSON}（已回填列序与 model 块）")
    print(f"[产物] {shot_dir / '图5-1_混淆矩阵.png'}")


def cross_test(pipe: Pipeline, test_path: str) -> dict:
    """跨集评估：用官方 KDDTest+ 测真实泛化能力。

    随机划分（同分布）会高估精度；跨集才是设计文档该报的诚实数字。
    """
    dft = load_dataset(test_path)
    X = dft.drop(columns=[TARGET])
    y = dft[TARGET].astype(int)
    y_pred = pipe.predict(X)
    y_prob = pipe.predict_proba(X)[:, 1]
    acc = accuracy_score(y, y_pred)
    cm = confusion_matrix(y, y_pred)
    auc = roc_auc_score(y, y_prob)
    rep = classification_report(y, y_pred, target_names=["Normal", "Attack"], output_dict=True)
    baseline = max(y.value_counts()) / len(y)
    print("\n=== 跨集评估（官方 KDDTest+，真实泛化）===")
    print(f"样本={len(y)}  基线(全猜多数类)={baseline:.4f}")
    print(f"随机森林 Acc={acc:.4f}  ROC-AUC={auc:.4f}")
    print(classification_report(y, y_pred, target_names=["Normal", "Attack"], digits=4))
    print(f"混淆矩阵 [[TN FP],[FN TP]] = {cm.tolist()}")
    return {
        "dataset": "KDDTest+",
        "n_test": int(len(y)),
        "accuracy": round(acc, 4),
        "roc_auc": round(auc, 4),
        "baseline_majority": round(baseline, 4),
        "per_class": {
            k: {m: round(v[m], 4) for m in ("precision", "recall", "f1-score")}
            for k, v in rep.items() if k in ("Normal", "Attack")
        },
        "confusion_matrix": cm.tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="NSL-KDD 随机森林训练")
    parser.add_argument("--data", required=True, help="KDDTrain+.csv 路径（无表头）")
    parser.add_argument("--test", default=None, help="可选：官方 KDDTest+ 跨集评估路径")
    args = parser.parse_args()

    dataset = load_dataset(args.data)
    print(f"[数据] {args.data} 总样本={len(dataset)}")
    dist = dataset[TARGET].value_counts()
    print(f"[数据] 全量 label 分布: 正常={int(dist[0])} 攻击={int(dist[1])} 比例 1:{dist[0]/dist[1]:.2f}")

    pipe, (X_test, y_test) = train_model(dataset)
    metrics = evaluate(pipe, X_test, y_test)
    metrics["random_split"] = True

    # 列序 = 原始特征列（OneHot 在 Pipeline 内部处理，predict 时传原始列即可）
    features = [c for c in dataset.columns if c != TARGET]
    save_artifacts(pipe, features, metrics)

    if args.test:
        cross = cross_test(pipe, args.test)
        save_artifacts(pipe, features, metrics, cross_test_metrics=cross)
        print("\n=== CROSS_TEST_JSON ===")
        print(json.dumps(cross, ensure_ascii=False))

    print("\n=== METRICS_JSON ===")
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
