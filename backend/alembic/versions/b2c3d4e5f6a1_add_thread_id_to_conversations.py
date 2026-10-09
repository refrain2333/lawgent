"""add thread_id to conversations

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-02-26 00:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增 thread_id 列（先允许 null）
    op.add_column('conversations', sa.Column('thread_id', sa.VARCHAR(255), nullable=True, comment='会话唯一标识'))

    # 把现有 title 值迁移到 thread_id
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE conversations SET thread_id = title"))

    # 设为非空并加唯一索引
    op.alter_column('conversations', 'thread_id', nullable=False)
    op.create_unique_constraint('uq_conversations_thread_id', 'conversations', ['thread_id'])
    op.create_index('ix_conversations_thread_id', 'conversations', ['thread_id'])

    # 清空 title（留给可读标题）
    conn.execute(sa.text("UPDATE conversations SET title = NULL"))


def downgrade() -> None:
    op.drop_index('ix_conversations_thread_id', table_name='conversations')
    op.drop_constraint('uq_conversations_thread_id', 'conversations', type_='unique')
    op.drop_column('conversations', 'thread_id')
