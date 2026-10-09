"""update conversation stage values

Revision ID: e3f1a2b4c5d6
Revises: d19484681ae2
Create Date: 2026-02-26 00:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'e3f1a2b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd19484681ae2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STAGE_MAP = {
    "s1": "s1_collecting",
    "s2": "s2_searching",
    "s3": "s3_collecting",
    "s4": "s4_done",
    "done": "s4_done",
}


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in STAGE_MAP.items():
        conn.execute(
            sa.text("UPDATE conversations SET stage = :new WHERE stage = :old"),
            {"new": new, "old": old},
        )


def downgrade() -> None:
    conn = op.get_bind()
    reverse_map = {
        "s1_collecting": "s1",
        "s1_confirming": "s1",
        "s2_searching": "s2",
        "s3_collecting": "s3",
        "s3_confirming": "s3",
        "s4_done": "done",
    }
    for old, new in reverse_map.items():
        conn.execute(
            sa.text("UPDATE conversations SET stage = :new WHERE stage = :old"),
            {"new": new, "old": old},
        )
