"""后台管理路由。占位，D1 实现用户/模型管理。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """占位路由，验证路由注册成功。"""
    return {"module": "admin", "status": "todo"}
