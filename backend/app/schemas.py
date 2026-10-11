"""Pydantic 请求/响应 schemas。

统一返回结构 {code, msg, data}（CONTEXT.md 第 4 节）：
- code：与 HTTP 状态码一致（200/201 成功，4xx 错误）
- msg：人类可读提示
- data：业务载荷，错误时为 null
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- 认证 ----------
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="登录名")
    password: str = Field(min_length=6, max_length=64, description="明文密码（bcrypt 上限 72 字节，此处收紧到 64）")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    token: str
    role: str


class UserOut(BaseModel):
    """用户信息响应（不含密码）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    status: int
    created_at: datetime
