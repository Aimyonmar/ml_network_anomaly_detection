"""检测任务路由（D5）。

接口（CONTEXT.md §4）：
- POST /api/v1/tasks        上传 csv，立即返回 task_id（pending），BackgroundTasks 异步检测
- GET  /api/v1/tasks        我的任务列表（分页）
- GET  /api/v1/tasks/{id}   任务详情（前端轮询 status）
- GET  /api/v1/tasks/{id}/results  结果分页（t_detection_result 可能几十万行，禁全量）
- GET  /api/v1/tasks/{id}/stats    聚合统计（SQL 聚合，不拉明细）

验收标准（TODO.md D5）：
- 上传 1 万行 CSV，1 秒内返回 task_id
- 轮询 status 从 pending 变 success
- stats 总数与 count(*) 一致
"""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import DetectionResult, DetectionTask, User
from app.schemas import PageData, ResultItem, TaskCreatedData, TaskOut
from app.services.detection import run_detection
from app.utils.file_io import UploadValidationError, save_upload

router = APIRouter()


def _forbidden(detail: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"code": 403, "msg": detail, "data": None})


def _not_found(detail: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"code": 404, "msg": detail, "data": None})


def _get_owned_task(db: Session, task_id: int, user: User) -> DetectionTask | JSONResponse:
    """取任务并校验归属：非本人且非 admin 返回 403，不存在返回 404。"""
    task = db.get(DetectionTask, task_id)
    if task is None:
        return _not_found("任务不存在")
    if task.user_id != user.id and user.role != "admin":
        return _forbidden("无权访问该任务")
    return task


@router.post("", status_code=201, summary="上传文件创建检测任务（异步）")
def create_task(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="检测流量 csv（≤50MB）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        path = save_upload(file, Path(settings.UPLOAD_DIR))
    except UploadValidationError as e:
        return JSONResponse(status_code=400, content={"code": 400, "msg": str(e), "data": None})

    task = DetectionTask(
        user_id=user.id,
        file_name=file.filename or "unnamed.csv",
        file_path=str(path),
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 立即返回 task_id（pending），检测在响应后异步执行
    background.add_task(run_detection, task.id, str(path))
    return {
        "code": 201,
        "msg": "ok",
        "data": TaskCreatedData(task_id=task.id, status=task.status).model_dump(),
    }



@router.get("", summary="我的任务列表（分页）")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(DetectionTask).filter(DetectionTask.user_id == user.id)
    total = q.count()
    items = (
        q.order_by(DetectionTask.created_at.desc(), DetectionTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageData(
        total=total, page=page, page_size=page_size,
        items=[TaskOut.model_validate(t).model_dump() for t in items],
    )
    return {"code": 200, "msg": "ok", "data": data.model_dump()}


@router.get("/{task_id}", summary="任务详情（轮询 status）")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, user)
    if isinstance(task, JSONResponse):
        return task
    return {"code": 200, "msg": "ok", "data": TaskOut.model_validate(task).model_dump()}


@router.get("/{task_id}/results", summary="检测结果分页")
def get_results(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, user)
    if isinstance(task, JSONResponse):
        return task
    q = db.query(DetectionResult).filter(DetectionResult.task_id == task_id)
    total = q.count()
    # 显式列清单，禁 SELECT *（CONTEXT.md §3）
    items = (
        q.with_entities(
            DetectionResult.id, DetectionResult.row_no, DetectionResult.prediction,
            DetectionResult.attack_type, DetectionResult.confidence,
        )
        .order_by(DetectionResult.row_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageData(
        total=total, page=page, page_size=page_size,
        items=[ResultItem.model_validate(r, from_attributes=True).model_dump() for r in items],
    )
    return {"code": 200, "msg": "ok", "data": data.model_dump()}


@router.get("/{task_id}/stats", summary="聚合统计（图表用）")
def get_stats(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, user)
    if isinstance(task, JSONResponse):
        return task
    # 聚合 SQL，不拉明细（验收：总数与 count(*) 一致）
    agg = (
        db.query(
            DetectionResult.prediction,
            sqlfunc.count(DetectionResult.id),
            sqlfunc.avg(DetectionResult.confidence),
        )
        .filter(DetectionResult.task_id == task_id)
        .group_by(DetectionResult.prediction)
        .all()
    )
    dist = {
        p: {"count": c, "avg_confidence": round(float(avg), 4) if avg is not None else None}
        for p, c, avg in agg
    }
    total = sum(v["count"] for v in dist.values())
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "task_id": task_id,
            "status": task.status,
            "total_results": total,
            "prediction_distribution": dist,
            "task_rows": {
                "total_rows": task.total_rows,
                "attack_rows": task.attack_rows,
                "normal_rows": task.normal_rows,
            },
            "cost_seconds": task.cost_seconds,
        },
    }
