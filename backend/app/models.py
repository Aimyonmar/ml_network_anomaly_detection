"""SQLAlchemy ORM 模型。

与 docs/schema.sql 严格一致（schema.sql 是唯一真相来源）。
注意：auto_log.py check 会校验本文件中 `class Xxx(` 出现次数
与 docs/schema.sql 中 `CREATE TABLE` 出现次数一致（当前均为 3）。
新增表时两边同步。

约束（CONTEXT.md 第 3 节）：
- 不加 FOREIGN KEY，逻辑关联即可
- 字段名下划线小写
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """对应 t_user。"""

    __tablename__ = "t_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="登录名")
    password: Mapped[str] = mapped_column(String(100), nullable=False, comment="bcrypt 哈希 ($2b$...)")
    role: Mapped[str] = mapped_column(String(10), nullable=False, server_default="user", comment="user|admin")
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1", comment="1启用 0禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (Index("idx_username", "username"),)


class DetectionTask(Base):
    """对应 t_detection_task。"""

    __tablename__ = "t_detection_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="关联 t_user.id")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="服务器存储路径")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="总行数")
    attack_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="判定为攻击的行数")
    normal_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="判定为正常的行数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", comment="pending|running|success|failed")
    error_msg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cost_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index("idx_user_time", "user_id", "created_at"),
        Index("idx_status", "status"),
    )


class DetectionResult(Base):
    """对应 t_detection_result。可能几十万行，查询必须分页。"""

    __tablename__ = "t_detection_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="关联 t_detection_task.id")
    row_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="文件中第几行（从1开始）")
    prediction: Mapped[str] = mapped_column(String(20), nullable=False, comment="Normal|Attack")
    attack_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="多分类时才有值")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, comment="置信度 0~1")

    __table_args__ = (Index("idx_task", "task_id"),)
