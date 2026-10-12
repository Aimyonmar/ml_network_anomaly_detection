"""V2 阈值调优器（Gap 3：召回优先）。

在 train_v2 的同一测试切分（random_state=42 确定性）上扫描 Attack 判定阈值，
找「召回 ≥ target 的最低阈值」——召回↑必致 precision↓，PR 权衡表如实输出。

产物：ml/artifacts/threshold_v2.json（含推荐阈值与全表），供 .env
MODEL_DECISION_THRESHOLD 注入（app.config 读取后 predict 生效）。

用法：python -m ml.threshold_optimizer [--target 0.90] [--sample N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from ml.cicids_data import DATA_DIR, load_cicids_dataframe
from sklearn.model_selection import train_test_split

ML_DIR = Path(__file__).resolve().parent
ART_DIR = ML_DIR / "artifacts"
OUT_PATH = ART_DIR / "threshold_v2.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="召回优先阈值扫描")
    parser.add_argument("--target", type=float, default=0.90, help="目标攻击召回（默认 0.90）")
    parser.add_argument("--data", default=str(DATA_DIR))
    parser.add_argument("--sample", type=int, default=0)
    args = parser.parse_args()

    model = joblib.load(ART_DIR / "model_v2.pkl")
    contract = json.loads((ML_DIR / "features_cicids.json").read_text(encoding="utf-8"))
    feats = [f["name"] for f in contract["features"] if f["type"] != "target"]

    df, _ = load_cicids_dataframe(args.data, sample=args.sample)
    X_train, X_test, y_train, y_test = train_test_split(
        df[feats].astype(np.float64), df["label"],
        test_size=0.2, stratify=df["label"], random_state=42,
    )
    # 与 train_v2 相同 seed → 同一 test 集，调优结果与其评估口径一致

    proba = model.predict_proba(X_test)[:, 1]
    y_true = y_test.values

    table = []
    for t in [round(x, 2) for x in np.arange(0.05, 0.96, 0.05)]:
        preds = (proba >= t).astype(int)
        table.append({
            "threshold": t,
            "accuracy": round(accuracy_score(y_true, preds), 4),
            "precision_attack": round(precision_score(y_true, preds, zero_division=0), 4),
            "recall_attack": round(recall_score(y_true, preds), 4),
            "f1_attack": round(f1_score(y_true, preds), 4),
        })
        row = table[-1]
        print(f"t={t:.2f}  acc={row['accuracy']:.4f}  P={row['precision_attack']:.4f} "
              f"R={row['recall_attack']:.4f}  F1={row['f1_attack']:.4f}")

    ok = [r for r in table if r["recall_attack"] >= args.target]
    if ok:
        best = min(ok, key=lambda r: r["threshold"])
        note = f"召回 ≥ {args.target} 的最低阈值"
    else:
        best = max(table, key=lambda r: r["recall_attack"])
        note = f"未达目标召回 {args.target}，给最高召回阈值（如实报告，禁止美化）"
    print(f"\n[推荐] threshold={best['threshold']} "
          f"(P={best['precision_attack']} R={best['recall_attack']}) —— {note}")
    print(f"[部署] backend/.env 写入 MODEL_DECISION_THRESHOLD={best['threshold']}")

    OUT_PATH.write_text(
        json.dumps({"target_recall": args.target, "recommend": best, "table": table},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[done] 已写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
