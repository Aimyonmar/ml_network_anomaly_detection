"""数据库连接与 Session 工厂。

全链路同步（决策见 DECISIONS.md 2026-09-21 pymysql 条）：
- engine 用 create_engine
- 会话用同步 Session
- 路由处理函数用普通 def
禁止在此引入 create_async_engine / AsyncSession。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, class_=Session
)


def get_db() -> Session:
    """FastAPI 依赖：普通生成器函数（非 async），请求结束自动关闭 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
