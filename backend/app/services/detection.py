"""异常检测服务（D5 核心，V2 产品化扩展多格式输入与双模型调度）。

职责：
- 读取上传文件：csv（nslkdd 41 列表头 / 42 列无表头 / CIC-IDS2017 Label 表头）
  或 pcap（流特征提取，V2）
- 按 settings.MODEL_VERSION 调度 v1/v2 模型与其特征契约
- 列校验（契约 41/78 列，缺/多/乱序拒绝）→ 分批推理（V2 支持判定阈值）
- 分批写 t_detection_result、回写任务状态 pending→running→success/failed
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
from app.services import alert_service
from app.utils.file_io import safe_remove
from ml import predict as ml_predict
from ml import schema_registry

BATCH_SIZE = settings.DETECTION_BATCH_SIZE


def _active_model_paths() -> tuple[Path, Path]:
    """按 MODEL_VERSION 返回 (model_path, features_path)。路径以 backend/ 为基准。"""
    if settings.MODEL_VERSION == "v2":
        return Path(settings.MODEL_PATH_V2), Path(settings.FEATURES_PATH_V2)
    # v1：与 predict.py 默认值同源（ml/ 模块相对），保持项目链路零改动
    return ml_predict.MODEL_PATH, ml_predict.FEATURES_PATH


def load_upload_input(path: Path) -> tuple[list[dict], list[str] | None]:
    """读取上传文件为 (模型输入记录, 告警源键列表或 None)。

    - .pcap：流特征提取 → flow schema 对齐当前生效契约（缺失特征填 0）
    - .csv 带表头 41 列 nslkdd：v1 原样兼容
    - .csv 无表头 42 列（KDDTest+ 原始格式）：v1 原样兼容
    - .csv 带表头含 Label（CIC-IDS2017）：列名 strip 规范化、剥 Label 与元数据列
    src_key：有源 IP 的 schema 用 IP；无则 None（告警按行号引用）
    """
    suffix = path.suffix.lower()
    if suffix == ".pcap":
        from ml import flow_extract

        raw = flow_extract.pcap_to_records(path)
        model_path, features_path = _active_model_paths()
        expected = ml_predict.load_expected_features(features_path)
        flow_schema = schema_registry.get_flow_schema(expected)
        records, src_keys = [], []
        for r in raw:
            src_keys.append(str(r.pop("_src_ip", "")) or f"row")
            r.pop("_dst_ip", None)
            records.append(flow_schema.fill_defaults(r))
        return records, src_keys

    # ---- csv 分支 ----
    head = pd.read_csv(path, nrows=0)
    nslkdd_cols = ml_predict.load_expected_features()  # v1 契约默认
    if len(head.columns) == 41 and set(head.columns) == set(nslkdd_cols):
        return pd.read_csv(path).to_dict(orient="records"), None

    probe = pd.read_csv(path, nrows=5, header=None)
    if probe.shape[1] == 42:
        names = nslkdd_cols + ["attack_name"]
        df = pd.read_csv(path, header=None, names=names)
        return df.drop(columns=["attack_name"]).to_dict(orient="records"), None

    # CIC-IDS2017 分支：嗅探（含 Label 判定与列名 strip）
    df = pd.read_csv(path, low_memory=False)
    cic_schema, df = schema_registry.sniff_schema(df)  # 非 cicids 会抛 ValueError 带指引
    src_keys = None
    if cic_schema.src_ip_col:
        src_keys = df[cic_schema.src_ip_col].astype(str).fillna("").tolist()
    records = [cic_schema.fill_defaults(rec) for rec in df.to_dict(orient="records")]
    return records, src_keys


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
        records, src_keys = load_upload_input(Path(file_path))
        model_path, features_path = _active_model_paths()
        expected = ml_predict.load_expected_features(features_path)
        # pcap/flow 记录由 fill_defaults 保证契约对齐；这里校验最终列序
        ml_predict.validate_columns(records, expected)

        model = ml_predict.load_model(model_path)
        threshold = settings.MODEL_DECISION_THRESHOLD if settings.MODEL_VERSION == "v2" else 0.5
        attack_rows = 0
        hits: list[dict] = []  # 高置信攻击命中（V2 告警源）
        total = len(records)
        for start in range(0, total, BATCH_SIZE):
            batch = records[start:start + BATCH_SIZE]
            results = ml_predict.predict(batch, model, expected, decision_threshold=threshold)
            rows = []
            for i, r in enumerate(results):
                if r["prediction"] == "Attack":
                    attack_rows += 1
                    if r["confidence"] >= settings.ALERT_CONFIDENCE_THRESHOLD:
                        hits.append({
                            "row_no": start + i + 1,
                            "confidence": r["confidence"],
                            "src_key": (src_keys[start + i] if src_keys else "") or "",
                        })
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
            f"[detection] task={task_id} success rows={total} attack={attack_rows} "
            f"model={settings.MODEL_VERSION} cost={elapsed:.2f}s"
        )
        # V2 告警（Gap 4）：告警失败绝不影响任务成功态
        try:
            alert_service.generate_alerts(db, task_id, task.user_id, hits)
        except Exception as alert_exc:
            db.rollback()
            logger.warning(f"[alert] 告警生成失败（不影响任务状态）：{alert_exc}")
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
