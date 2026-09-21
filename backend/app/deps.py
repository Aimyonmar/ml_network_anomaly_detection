"""FastAPI 公共依赖。

提供跨路由复用的依赖项，例如：
- get_db：数据库 session（来自 app.database）
- get_current_user：当前用户（D1 实现登录后启用）
"""
from typing import Any

from fastapi import Depends

from app.database import get_db


def get_current_user(db: Any = Depends(get_db)) -> Any:
    """当前登录用户依赖。

    当前阶段未实现登录逻辑，返回 None。
    D1 实现登录后改为解析 JWT 并查库返回 User 实例。
    """
    return None
