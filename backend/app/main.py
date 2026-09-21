"""FastAPI 应用入口。

职责：
- 创建 FastAPI 应用实例
- 注册 CORS 中间件
- 注册所有路由（auth / tasks / results / admin / model_api）
- 暴露 /health 健康检查

不在此处实现业务逻辑。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, model_api, results, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动钩子：将来在此初始化数据库连接池、ML 模型加载等
    yield
    # 关闭钩子：将来在此关闭连接池


app = FastAPI(
    title="ml_network_anomaly_detection",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 上线前收紧到具体前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(results.router, prefix="/results", tags=["results"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(model_api.router, prefix="/model", tags=["model_api"])


@app.get("/health", tags=["health"])
def health() -> dict:
    """健康检查端点。"""
    return {"status": "ok"}
