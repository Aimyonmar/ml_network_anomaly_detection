"""安全相关工具。

职责：
- 密码哈希与校验（passlib[bcrypt]）
- JWT 签发与解析（python-jose）

约束（CONTEXT.md §1）：
- 密码绝不存明文，只存 bcrypt 哈希（$2b$...）
- 若 passlib 在 3.12 + bcrypt5.0 下不可用，改用固定版 bcrypt 库直接哈希，
  但只许改本文件（见 DECISIONS.md）。当前实现已实测通过。
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt 哈希上下文；scheme 固定 bcrypt，产出 $2b$ 前缀
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    """对明文密码做 bcrypt 哈希，返回 $2b$... 字符串。"""
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return pwd_context.verify(raw, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """签发 JWT access token。

    Args:
        subject: 写入 sub 声明的内容（这里用 username，便于 /auth/me 直接取）
        expires_delta: 过期时长，默认取配置 ACCESS_TOKEN_EXPIRE_MINUTES
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    """解析 JWT，返回 subject（username）。

    token 无效/被篡改/过期时返回 None，由调用方转成 401。
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None
