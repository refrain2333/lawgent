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
    # 迁移只变更字段，不能将已有用户和咨询记录当作测试数据清空。
    op.drop_column('conversations', 'facts_json')


def downgrade() -> None:
    op.add_column('conversations', sa.Column('facts_json', sa.JSON(), nullable=False, server_default='{}', comment='结构化案情事实'))
