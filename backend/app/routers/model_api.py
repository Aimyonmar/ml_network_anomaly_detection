"""模型管理路由。占位，D1 实现模型上传/切换/版本管理。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """占位路由，验证路由注册成功。"""
    return {"module": "model_api", "status": "todo"}
