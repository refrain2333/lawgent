"""add stage to messages

Revision ID: a1b2c3d4e5f6
Revises: f4a2b3c1d5e6
Create Date: 2026-02-26 00:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4a2b3c1d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('stage', sa.VARCHAR(), nullable=False, server_default='s1_collecting', comment='消息所属阶段'))


def downgrade() -> None:
    op.drop_column('messages', 'stage')
