"""安全相关工具。

职责：
- 密码哈希与校验
- JWT 签发与解析

当前阶段不实现具体逻辑，仅声明函数签名与 docstring。
"""
from datetime import datetime
from typing import Any


def hash_password(raw: str) -> str:
    """对明文密码做哈希，返回哈希字符串。

    Args:
        raw: 明文密码
    Returns:
        哈希后的密码字符串
    """
    # TODO: 用 passlib[bcrypt] 实现
    raise NotImplementedError


def verify_password(raw: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    # TODO: 用 passlib[bcrypt] 实现
    raise NotImplementedError


def create_access_token(subject: str, expires_at: datetime) -> str:
    """签发 JWT access token。"""
    # TODO: 用 python-jose 或 PyJWT 实现
    raise NotImplementedError


def decode_access_token(token: str) -> Any:
    """解析 JWT，返回 claims。"""
    # TODO: 同上
    raise NotImplementedError
