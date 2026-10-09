"""remove facts_json from conversations

Revision ID: f4a2b3c1d5e6
Revises: e3f1a2b4c5d6
Create Date: 2026-02-26 00:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'f4a2b3c1d5e6'
down_revision: Union[str, Sequence[str], None] = 'e3f1a2b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 清空测试数据
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM stage_confirmations"))
    conn.execute(sa.text("DELETE FROM messages"))
    conn.execute(sa.text("DELETE FROM conversations"))
    conn.execute(sa.text("DELETE FROM users"))

    # 删除 facts_json 列
    op.drop_column('conversations', 'facts_json')


def downgrade() -> None:
    op.add_column('conversations', sa.Column('facts_json', sa.JSON(), nullable=False, server_default='{}', comment='结构化案情事实'))
