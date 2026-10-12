"""告警路由（V2 产品化，Gap 4）。

接口：
- GET  /api/v1/alerts             我的告警列表（分页，可按状态过滤，open 优先）
- GET  /api/v1/alerts/count       open 告警数（前端菜单红点轮询）
- PUT  /api/v1/alerts/{id}/ack    确认处置（open → acked，记 acked_by）
- PUT  /api/v1/alerts/{id}/dismiss 忽略（open → dismissed）

归属校验与 tasks 同风格：非本人非 admin 403，不存在 404。
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Alert, User
from app.schemas import AlertCountData, AlertItem, PageData

router = APIRouter()


def _not_found(detail: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"code": 404, "msg": detail, "data": None})


def _get_owned_alert(db: Session, alert_id: int, user: User) -> Alert | JSONResponse:
    alert = db.get(Alert, alert_id)
    if alert is None:
        return _not_found("告警不存在")
    if alert.user_id != user.id and user.role != "admin":
        return JSONResponse(status_code=403, content={"code": 403, "msg": "无权访问该告警", "data": None})
    return alert


@router.get("", summary="我的告警列表（分页，open 优先）")
def list_alerts(
    status: str = Query("all", pattern="^(all|open|acked|dismissed)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Alert).filter(Alert.user_id == user.id)
    if status != "all":
        q = q.filter(Alert.status == status)
    total = q.count()
    # open 优先（未处置的排最前），同级按置信度降序
    items = (
        q.order_by(
            (Alert.status != "open"),
            Alert.confidence.desc(),
            Alert.created_at.desc(),
            Alert.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageData(
        total=total, page=page, page_size=page_size,
        items=[AlertItem.model_validate(a).model_dump() for a in items],
    )
    return {"code": 200, "msg": "ok", "data": data.model_dump()}


@router.get("/count", summary="open 告警数（菜单红点）")
def count_open(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = (
        db.query(sqlfunc.count(Alert.id))
        .filter(Alert.user_id == user.id, Alert.status == "open")
        .scalar()
    )
    return {"code": 200, "msg": "ok", "data": AlertCountData(open_count=int(n or 0)).model_dump()}


@router.put("/{alert_id}/ack", summary="确认处置（open → acked）")
def ack_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = _get_owned_alert(db, alert_id, user)
    if isinstance(alert, JSONResponse):
        return alert
    if alert.status != "open":
        return JSONResponse(status_code=400, content={"code": 400, "msg": f"当前状态 {alert.status} 不可确认", "data": None})
    alert.status = "acked"
    alert.acked_by = user.id
    db.commit()
    return {"code": 200, "msg": "ok", "data": AlertItem.model_validate(alert).model_dump()}


@router.put("/{alert_id}/dismiss", summary="忽略告警（open → dismissed）")
def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = _get_owned_alert(db, alert_id, user)
    if isinstance(alert, JSONResponse):
        return alert
    if alert.status != "open":
        return JSONResponse(status_code=400, content={"code": 400, "msg": f"当前状态 {alert.status} 不可忽略", "data": None})
    alert.status = "dismissed"
    alert.acked_by = user.id
    db.commit()
    return {"code": 200, "msg": "ok", "data": AlertItem.model_validate(alert).model_dump()}
