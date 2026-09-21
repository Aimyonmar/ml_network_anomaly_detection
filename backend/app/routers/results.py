"""检测结果路由。占位，D1 实现结果查询。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """占位路由，验证路由注册成功。"""
    return {"module": "results", "status": "todo"}
