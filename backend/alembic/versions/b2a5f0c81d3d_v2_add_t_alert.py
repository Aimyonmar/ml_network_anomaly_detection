"""v2 add t_alert

Revision ID: b2a5f0c81d3d
Revises: ad96f59252ef
Create Date: 2026-10-12 12:00:00.000000

V2 产品化（product 分支）：Gap 4 告警与处置建议表。
SQL 已于 V2产品化改造计划.md 第五节经用户批准；与 docs/schema.sql 追加段一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2a5f0c81d3d'
down_revision: Union[str, Sequence[str], None] = 'ad96f59252ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('t_alert',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.BigInteger(), nullable=False, comment='触发告警的检测任务'),
    sa.Column('user_id', sa.BigInteger(), nullable=False, comment='任务归属用户'),
    sa.Column('src_key', sa.String(length=64), nullable=False, comment='攻击源(src ip；无 ip schema 用行引用)'),
    sa.Column('confidence', sa.Float(), nullable=False, comment='模型置信度 0~1'),
    sa.Column('prediction', sa.String(length=20), server_default='Attack', nullable=False, comment='恒为 Attack'),
    sa.Column('rule_cmd', sa.String(length=512), nullable=True, comment='处置建议命令（绝不自动执行）'),
    sa.Column('status', sa.String(length=20), server_default='open', nullable=False, comment='open|acked|dismissed'),
    sa.Column('acked_by', sa.BigInteger(), nullable=True, comment='确认人 t_user.id'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_status', 't_alert', ['user_id', 'status'], unique=False)
    op.create_index('idx_alert_task', 't_alert', ['task_id'], unique=False)
    op.create_index('idx_src_time', 't_alert', ['src_key', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_src_time', table_name='t_alert')
    op.drop_index('idx_alert_task', table_name='t_alert')
    op.drop_index('idx_user_status', table_name='t_alert')
    op.drop_table('t_alert')
