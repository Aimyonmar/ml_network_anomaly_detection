"""异常检测服务（D5 核心）。

职责（CONTEXT.md §2 目录说明）：
- 读取上传 csv → 列校验（features.json 41 列，缺/多/乱序拒绝）
- 调用 ml/predict.py 批量推理
- 分批写 t_detection_result（几十万行不一次灌入）
- 回写任务状态 pending→running→success/failed、耗时、行数统计
- 失败路径：error_msg 写明原因 + 清理临时文件（不留 orphan）

注意：本函数由 BackgroundTasks 调用，运行在请求响应之后，
必须自己管理 DB session（不能复用请求作用域的 get_db）。
"""
import time
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DetectionResult, DetectionTask
from app.utils.file_io import safe_remove
from ml import predict as ml_predict

BATCH_SIZE = settings.DETECTION_BATCH_SIZE


def load_upload_dataframe(path: Path) -> pd.DataFrame:
    """读取上传 csv 为 DataFrame。

    带表头：列名必须与 features.json 41 列完全一致（predict.validate_columns 校验）。
    无表头（NSL-KDD 原始格式，42 列=41 特征+攻击名）：自动补官方列名并剔除末列，
    兼容直接用 KDDTest+.csv 做上传测试的场景。
    """
    head = pd.read_csv(path, nrows=0)
    if len(head.columns) == 41 and set(head.columns) == set(ml_predict.load_expected_features()):
        return pd.read_csv(path)
    # 无表头分支：首行若含非数值文本（如 "tcp"）说明其实有表头但列不对，直接报错
    probe = pd.read_csv(path, nrows=5, header=None)
    if probe.shape[1] == 42:
        names = ml_predict.load_expected_features() + ["attack_name"]
        df = pd.read_csv(path, header=None, names=names)
        return df.drop(columns=["attack_name"])
    raise ml_predict.FeatureMismatchError(
        f"无法识别文件列结构：表头列数={len(head.columns)}，"
        f"模型要求 {len(ml_predict.load_expected_features())} 列（见 features.json）。"
        f"请检查首行列名或确认 csv 无表头且恰为 42 列的 NSL-KDD 原始格式。"
    )


def run_detection(task_id: int, file_path: str) -> None:
    """后台任务入口：对 task 执行完整检测链路。任何异常都落 failed + error_msg。"""
    db: Session = _new_session()
    task = db.get(DetectionTask, task_id)
    if task is None:
        logger.error(f"[detection] task_id={task_id} 不存在，放弃")
        db.close()
        return

    try:
        task.status = "running"
        db.commit()

        t0 = time.perf_counter()
        df = load_upload_dataframe(Path(file_path))
        records = df.to_dict(orient="records")
        ml_predict.validate_columns(records)

        model = ml_predict.load_model()
        attack_rows = 0
        total = len(records)
        for start in range(0, total, BATCH_SIZE):
            batch = records[start:start + BATCH_SIZE]
            results = ml_predict.predict(batch, model)
            rows = []
            for i, r in enumerate(results):
                if r["prediction"] == "Attack":
                    attack_rows += 1
                rows.append(DetectionResult(
                    task_id=task_id,
                    row_no=start + i + 1,  # 从 1 开始
                    prediction=r["prediction"],
                    confidence=r["confidence"],
                ))
            db.bulk_save_objects(rows)
            db.commit()

        elapsed = time.perf_counter() - t0
        task.status = "success"
        task.total_rows = total
        task.attack_rows = attack_rows
        task.normal_rows = total - attack_rows
        task.cost_seconds = round(elapsed, 3)
        db.commit()
        logger.info(
            f"[detection] task={task_id} success rows={total} attack={attack_rows} cost={elapsed:.2f}s"
        )
    except Exception as exc:
        db.rollback()
        task = db.get(DetectionTask, task_id)
        if task is not None:
            # 清理已写入的部分结果行，避免半截脏数据被 stats/results 查到
            db.query(DetectionResult).filter(DetectionResult.task_id == task_id).delete()
            task.status = "failed"
            task.error_msg = str(exc)[:512]
            db.commit()
        # 失败清理临时文件，不留 orphan（CONTEXT.md §3）
        safe_remove(Path(file_path))
        logger.exception(f"[detection] task={task_id} failed: {exc}")
    finally:
        db.close()


def _new_session() -> Session:
    """后台任务专用 session（请求作用域的 get_db 在此不可用）。"""
    from app.database import SessionLocal

    return SessionLocal()
