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


class LiveScanRequest(BaseModel):
    """POST /tasks/live 一键体检请求（V3，CONTEXT.md §11.2）。"""

    duration: int = Field(default=60, description="抓包时长（秒），仅允许 30/60/120")


class LiveScanData(BaseModel):
    """一键体检创建响应：task_id 复用任务轮询与报告页。"""

    task_id: int
    status: str
    duration: int


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


# ---------- 告警（V2 产品化，Gap 4） ----------
class AlertItem(BaseModel):
    """告警列表单条（含处置建议命令，供前端一键复制）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    src_key: str
    confidence: float
    prediction: str
    rule_cmd: str | None
    status: str
    created_at: datetime


class AlertCountData(BaseModel):
    """当前用户 open 告警数（菜单红点轮询用）。"""

    open_count: int
