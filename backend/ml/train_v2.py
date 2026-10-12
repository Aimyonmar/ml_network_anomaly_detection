"""V2 训练脚本：CIC-IDS2017 二分类模型（product 分支，与项目 train.py/v1 模型共存）。

用法（backend/ 下执行）：
    python -m ml.train_v2                       # 全量训练（约 280 万行）
    python -m ml.train_v2 --sample 100000       # 冒烟抽样训练（快速验证链路，非正式口径）

产物（不覆盖 v1 冻结资产）：
    ml/artifacts/model_v2.pkl          # 胜出模型 Pipeline
    ml/features_cicids.json            # 特征契约 + 双模型成绩单元数据

严格遵守 CONTEXT.md §5（V2 继承项目硬规则）：
1. train_test_split 先行，stratify=y, random_state=42，任何预处理之前
2. 树模型无需缩放/独热（全数值特征），仍用 Pipeline 包裹保持结构一致
3. 绝不只报 accuracy：P/R/F1、混淆矩阵、ROC-AUC、多数类基线全输出
4. 类别不平衡先打印分布再决策：BENIGN:Attack ≈ 8:2，白名单无 imblearn（SMOTE 不可用），
   用 class_weight="balanced"（RF 用 balanced_subsample）
8. 指标 >99.5% 主动怀疑泄漏：CIC-IDS2017 同分布切分常见 99%+，需检查是否同源切片泄漏
   （周一 benign 与周五 attack 分在不同 split 属正常；同一 pcap 的流在同一 split 属同分布口径）
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.cicids_data import DATA_DIR, load_cicids_dataframe

ML_DIR = Path(__file__).resolve().parent
ART_DIR = ML_DIR / "artifacts"
LABELS = {0: "Normal", 1: "Attack"}


def _train_one(name: str, clf) -> tuple[Pipeline, dict]:
    print(f"[train] 训练 {name} ...")
    pipe = Pipeline([("model", clf)])
    t0 = time.perf_counter()
    pipe.fit(X_train, y_train)
    fit_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    preds = pipe.predict(X_test)
    proba = pipe.predict_proba(X_test)[:, 1]
    infer_s = time.perf_counter() - t0

    scores = {
        "algorithm": name,
        "fit_seconds": round(fit_s, 1),
        "infer_seconds": round(infer_s, 2),
        "throughput_rps": round(len(X_test) / infer_s) if infer_s > 0 else None,
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "precision_attack": round(precision_score(y_test, preds, pos_label=1), 4),
        "recall_attack": round(recall_score(y_test, preds, pos_label=1), 4),
        "f1_attack": round(f1_score(y_test, preds, pos_label=1), 4),
        "roc_auc": round(roc_auc_score(y_test, proba), 4),
    }
    print(f"  {name}: acc={scores['accuracy']} recall@t=0.5={scores['recall_attack']} "
          f"f1={scores['f1_attack']} auc={scores['roc_auc']} fit={fit_s:.0f}s")
    return pipe, scores


def _baseline() -> dict:
    """规则 3：全猜多数类基线对照。"""
    majority = int(y_train.value_counts().idxmax())
    preds = np.full(len(y_test), majority)
    return {
        "algorithm": f"majority({LABELS[majority]})",
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "recall_attack": round(recall_score(y_test, preds, pos_label=1, zero_division=0), 4),
        "note": "全猜多数类：攻击全漏，acc=正常占比——说明 acc 数字本身无意义",
    }


def _plot_confusion(cm: np.ndarray, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(4, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1], ["Normal", "Attack"])
    ax.set_yticks([0, 1], ["Normal", "Attack"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("预测"), ax.set_ylabel("真实")
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CIC-IDS2017 V2 模型训练")
    parser.add_argument("--data", default=str(DATA_DIR))
    parser.add_argument("--sample", type=int, default=0, help=">0 时抽样 N 行冒烟（非正式口径）")
    parser.add_argument("--no-hgb", action="store_true", help="跳过 HistGB 对照（冒烟用）")
    args = parser.parse_args()

    df, feats = load_cicids_dataframe(args.data, sample=args.sample)
    X_train, X_test, y_train, y_test = train_test_split(
        df[feats].astype(np.float64), df["label"],
        test_size=0.2, stratify=df["label"], random_state=42,
    )
    n_total = len(df)
    dist = df["label"].value_counts().to_dict()
    print(f"[split] total={n_total} train={len(X_train)} test={len(X_test)}")
    print(f"[split] 攻击占比：train={y_train.mean():.4f} test={y_test.mean():.4f}")

    baseline = _baseline()
    print(f"[baseline] {baseline}")

    models = {}
    all_scores = {}
    rf_pipe, rf_scores = _train_one("RandomForest", RandomForestClassifier(
        n_estimators=100, class_weight="balanced_subsample",
        n_jobs=-1, random_state=42))
    models["RandomForest"], all_scores["RandomForest"] = rf_pipe, rf_scores

    if not args.no_hgb:
        hgb_pipe, hgb_scores = _train_one("HistGradientBoosting", HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, class_weight="balanced", random_state=42))
        models["HistGradientBoosting"], all_scores["HistGradientBoosting"] = hgb_pipe, hgb_scores

    # 胜者：召回优先（V2 目标是少漏攻击），同分看 F1
    winner = max(all_scores, key=lambda k: (all_scores[k]["recall_attack"], all_scores[k]["f1_attack"]))
    print(f"[winner] {winner}")
    pipe = models[winner]

    # 规则 3 完整指标
    preds = pipe.predict(X_test)
    cm = confusion_matrix(y_test, preds)
    print("[confusion]\n", cm)
    print(classification_report(y_test, preds, target_names=["Normal", "Attack"], digits=4))

    # 规则 8：>99.5% 怀疑泄漏提示（同分布切分下 CIC 常见 99%+，口径如实标注）
    acc = all_scores[winner]["accuracy"]
    if acc > 0.995:
        print("[warn] 指标>99.5%：同分布切分口径（train/test 同源随机切分），"
              "不代表跨集/跨网络泛化。产品页演示需注明。")

    # 产物落盘
    ART_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, ART_DIR / "model_v2.pkl")
    contract = {
        "_comment": "CIC-IDS2017 特征契约（V2）。列名已 strip；与 flow_extract.pcap 提取器命名对齐。",
        "features": [{"name": f, "type": "numeric"} for f in feats],
        "model": {
            "algorithm": winner,
            "version": "v2",
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_features": len(feats),
            "sample_mode": "full" if args.sample == 0 else f"sample={args.sample}",
            "baseline": baseline,
            "scores": all_scores,
        },
    }
    (ML_DIR / "features_cicids.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    cm_path = ART_DIR / "confusion_v2.png"
    _plot_confusion(cm, cm_path)
    print(f"[done] 产物：{ART_DIR / 'model_v2.pkl'}、{ML_DIR / 'features_cicids.json'}、{cm_path}")
    print("[next] 阈值调优：python -m ml.threshold_optimizer")
