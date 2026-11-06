"""【非正式功能·实验原型】模拟流式实时检测。

把 NSL-KDD 的 KDDTest+.csv 按设定速率逐条"喂"给模型，模拟实时流量，
终端滚动显示每条判定的延迟与结果，Attack 行高亮告警，并与真实标签对照。

与主项目的关系（见 DECISIONS.md 2026-10-12 条）：
- 只读复用 backend/ml 的 model.pkl + features.json + predict.py，不改任何主线代码
- 不碰 backend/app、不碰 requirements.txt 白名单、不进正式发布范围

用法（在项目根目录，venv 已激活）：
    python playground/sim_stream.py                 # 默认 10 条/秒回放 KDDTest+
    python playground/sim_stream.py --rate 100      # 100 条/秒
    python playground/sim_stream.py --limit 500     # 只回放前 500 条
    python playground/sim_stream.py --burst         # 不限速全速跑，看真实吞吐上限
"""
import argparse
import sys
import time
from pathlib import Path

# 只读引入主项目推理模块（backend/ml），不复制模型代码
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from ml import predict as ml_predict  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "backend" / "ml" / "data" / "KDDTest+.csv"

# NSL-KDD 官方无表头 CSV 的列名 = features.json 41 列 + 末列真实攻击名
FEATURE_NAMES = ml_predict.load_expected_features()
COLS = FEATURE_NAMES + ["attack_name"]


def read_rows(csv_path: Path, limit: int | None):
    """读无表头 42 列 CSV，产出 (record_dict, 真实标签) 的流。

    真实标签列不进模型输入，仅用于回放结束后的对照统计。
    """
    import csv as _csv

    n = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for raw in _csv.reader(f):
            if len(raw) != len(COLS):
                raise ValueError(f"第 {n + 1} 行有 {len(raw)} 列，期望 {len(COLS)} 列")
            values = []
            for name, v in zip(COLS, raw):
                if name in ("protocol_type", "service", "flag", "attack_name"):
                    values.append(v.strip())
                elif name in ("land", "logged_in", "is_host_login", "is_guest_login"):
                    values.append(v.strip() == "1")
                elif name in (
                    "wrong_fragment", "urgent", "hot", "num_failed_logins",
                    "num_compromised", "root_shell", "su_attempted", "num_root",
                    "num_file_creations", "num_shells", "num_access_files",
                    "num_outbound_cmds", "row_no_placeholder",
                ):
                    values.append(int(float(v)))
                else:
                    values.append(float(v))
            record = dict(zip(COLS, values))
            label = record.pop("attack_name")
            yield record, label
            n += 1
            if limit and n >= limit:
                return


def main() -> int:
    parser = argparse.ArgumentParser(description="模拟流式实时检测（玩票原型）")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="无表头 42 列 NSL-KDD csv")
    parser.add_argument("--rate", type=float, default=10.0, help="回放速率（条/秒），默认 10")
    parser.add_argument("--limit", type=int, default=None, help="最多回放条数")
    parser.add_argument("--burst", action="store_true", help="不限速全速回放")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"[错误] 找不到数据文件：{csv_path}")
        return 1

    print("[加载] model.pkl + features.json ...")
    model = ml_predict.load_model()

    interval = 0.0 if args.burst else 1.0 / args.rate
    mode = "全速" if args.burst else f"{args.rate:g} 条/秒"
    print(f"[回放] {csv_path.name} 模式={mode}  Ctrl+C 随时退出\n")
    print(f"{'#':>6}  {'判定':<6} {'置信度':>7} {'单条延迟':>8}  {'真实标签':<12} 备注")
    print("-" * 72)

    stats = {"n": 0, "attack": 0, "agree": 0, "lat_sum": 0.0, "lat_max": 0.0}
    t_start = time.perf_counter()
    try:
        for record, label in read_rows(csv_path, args.limit):
            if interval:
                time.sleep(interval)
            t0 = time.perf_counter()
            result = ml_predict.predict([record], model)[0]
            latency_ms = (time.perf_counter() - t0) * 1000

            stats["n"] += 1
            stats["lat_sum"] += latency_ms
            stats["lat_max"] = max(stats["lat_max"], latency_ms)
            pred = result["prediction"]
            if pred == "Attack":
                stats["attack"] += 1
            actual = "Attack" if label.lower() != "normal" else "Normal"
            agree = pred == actual
            if agree:
                stats["agree"] += 1

            # Attack 判定行用 ANSI 红色高亮，模拟实时告警的视觉感
            line = (
                f"{stats['n']:>6}  {pred:<6} {result['confidence']:>7.4f} "
                f"{latency_ms:>7.2f}ms  {actual:<12} "
                f"{'✓' if agree else '✗ 漏报' if actual == 'Attack' else '✗ 误报'} ({label})"
            )
            if pred == "Attack":
                print(f"\033[91m{line}\033[0m")
            else:
                print(line)
    except KeyboardInterrupt:
        print("\n[中断] 手动停止回放")

    elapsed = time.perf_counter() - t_start
    if stats["n"] == 0:
        print("[结束] 没有回放任何记录")
        return 1
    print("-" * 72)
    print(
        f"[汇总] 共 {stats['n']} 条，用时 {elapsed:.1f}s（实际 {stats['n'] / elapsed:.1f} 条/秒）\n"
        f"       判定 Attack：{stats['attack']} 条 | 与真实标签一致：{stats['agree']} 条"
        f"（{stats['agree'] / stats['n']:.1%}）\n"
        f"       单条推理延迟：平均 {stats['lat_sum'] / stats['n']:.2f}ms，最大 {stats['lat_max']:.2f}ms"
    )
    print("\n[提示] 一致率是跨集泛化口径（约 76.9%），漏报多为 KDDTest+ 里未见过的攻击族，属预期。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
