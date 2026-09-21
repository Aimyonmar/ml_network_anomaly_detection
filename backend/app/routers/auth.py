"""认证路由。占位，D1 实现登录/注册逻辑。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """占位路由，验证路由注册成功。"""
    return {"module": "auth", "status": "todo"}
