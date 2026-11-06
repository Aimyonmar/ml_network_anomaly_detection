"""模型推理脚本（被 services/detection.py 调用，也可独立 CLI 运行）。

用法：
    python -m ml.predict --input <records.json> --output <result.json>

records.json 格式：[{"duration": 0, "protocol_type": "tcp", ...}, ...]
result.json 格式：[{"prediction": "Normal|Attack", "confidence": 0.xx}, ...]

严格遵守 CONTEXT.md 第 5 节：
6. 加载 model.pkl + features.json，校验列序一致，不一致抛明确错误
7. 支持单条与批量，返回标签+置信度，输出实测吞吐（条/秒）
"""
import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "artifacts" / "model.pkl"
FEATURES_PATH = ML_DIR / "features.json"

LABEL_MAP = {0: "Normal", 1: "Attack"}


class FeatureMismatchError(ValueError):
    """输入列与 features.json 训练列序不一致时抛出（规则6）。"""


def load_expected_features(path: str | Path | None = None) -> list[str]:
    """读取 features json 中的训练特征列序（不含 target）。

    path 为空时用 v1 契约（features.json，冻结资产）；v2 传 cicids 契约路径。
    """
    p = Path(path) if path is not None else FEATURES_PATH
    cfg = json.loads(p.read_text(encoding="utf-8"))
    return [f["name"] for f in cfg["features"] if f["type"] != "target"]


def load_model(path: str | Path = MODEL_PATH) -> Any:
    """加载已训练的 Pipeline 模型。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"模型文件不存在：{p}\n请先运行训练：python -m ml.train --data ml/data/KDDTrain+.csv"
        )
    return joblib.load(p)


def validate_columns(records: list[dict], expected: list[str] | None = None) -> None:
    """校验每条记录的列与训练列序完全一致（缺失/多余/乱序都拒绝）。

    报错信息精确到：缺哪些列、多哪些列、第几条记录。
    expected 为空时用 v1 契约（独立 CLI 兼容）；detection 传当前生效契约。
    """
    if expected is None:
        expected = load_expected_features()
    if not records:
        raise FeatureMismatchError("输入记录为空，无法推理")
    for i, rec in enumerate(records):
        got = list(rec.keys())
        missing = [c for c in expected if c not in got]
        extra = [c for c in got if c not in expected]
        if missing or extra:
            raise FeatureMismatchError(
                f"第 {i} 条记录列与模型要求不一致："
                f"缺失列={missing or '无'} 多余列={extra or '无'}。"
                f"模型要求 {len(expected)} 列（见 features 契约文件），实际 {len(got)} 列。"
            )
        if got != expected:
            raise FeatureMismatchError(
                f"第 {i} 条记录列序与特征契约不一致（内容相同但顺序不同）。"
                f"期望列序：{expected}"
            )


def predict(
    records: list[dict],
    model: Any,
    expected: list[str] | None = None,
    decision_threshold: float = 0.5,
) -> list[dict]:
    """对一批记录做推理，返回每条 {prediction, confidence}。

    单条 = 长度为 1 的列表，天然支持。
    decision_threshold：Attack 判定阈值（默认 0.5 = 与 v1 model.predict 等价）。
    V2 召回优先模式由 threshold_optimizer 给出更低阈值，经 config 注入；
    v1 链路恒为 0.5，行为与定稿完全一致（冻结要求）。
    confidence 报模型最大类概率（阈值只影响判定，不影响置信度口径）。
    """
    validate_columns(records, expected)
    cols = load_expected_features() if expected is None else expected
    df = pd.DataFrame(records)[cols]
    probs = model.predict_proba(df)
    classes = list(model.classes_)
    attack_idx = classes.index(1) if 1 in classes else int(classes[-1])
    out = []
    for row_prob in probs:
        p_attack = float(row_prob[attack_idx])
        label = "Attack" if p_attack >= decision_threshold else "Normal"
        out.append({"prediction": label, "confidence": round(max(row_prob), 4)})
    return out


def predict_file(input_path: str, output_path: str | None) -> None:
    """CLI 主流程：读 json → 推理 → 写结果 + 打印实测吞吐（规则7）。"""
    records = json.loads(Path(input_path).read_text(encoding="utf-8"))
    model = load_model()

    t0 = time.perf_counter()
    results = predict(records, model)
    elapsed = time.perf_counter() - t0

    n = len(records)
    throughput = n / elapsed if elapsed > 0 else float("inf")
    print(f"[推理] 记录数={n} 耗时={elapsed:.3f}s 吞吐={throughput:.1f} 条/秒")

    if output_path:
        Path(output_path).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[推理] 结果已写入 {output_path}")
    else:
        print(json.dumps(results[:5], ensure_ascii=False, indent=2))
        if n > 5:
            print(f"...（其余 {n - 5} 条未展示）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSL-KDD 模型推理")
    parser.add_argument("--input", required=True, help="记录 json 文件路径")
    parser.add_argument("--output", default=None, help="结果 json 输出路径（缺省打印前5条）")
    args = parser.parse_args()
    predict_file(args.input, args.output)
