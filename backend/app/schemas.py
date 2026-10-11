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


# ---------- 检测任务（D5） ----------
class TaskOut(BaseModel):
    """任务详情/列表项（前端轮询 status 用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    total_rows: int
    attack_rows: int
    normal_rows: int
    status: str
    error_msg: str | None
    cost_seconds: float | None
    created_at: datetime
    updated_at: datetime


class TaskCreatedData(BaseModel):
    """POST /tasks 立即返回的载荷。"""

    task_id: int
    status: str


class ResultItem(BaseModel):
    """结果分页单条。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    row_no: int
    prediction: str
    attack_type: str | None
    confidence: float | None


class PageData(BaseModel):
    """通用分页包装（list + total + page + page_size）。"""

    total: int
    page: int
    page_size: int
    items: list
