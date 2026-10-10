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

    # 兼容旧版本将 thread_id 放在 title 的记录；空标题、重复标题需独立标识。
    conn = op.get_bind()
    # 在 PostgreSQL 内执行回填，也支持 Alembic --sql 生成离线迁移脚本。
    conn.execute(sa.text("""
        DO $migration$
        DECLARE
            old_conversation RECORD;
            candidate TEXT;
        BEGIN
            FOR old_conversation IN SELECT id, title FROM conversations ORDER BY id LOOP
                candidate := old_conversation.title;
                IF candidate IS NULL OR btrim(candidate) = '' OR EXISTS (
                    SELECT 1 FROM conversations WHERE thread_id = candidate
                ) THEN
                    LOOP
                        candidate := md5(random()::text || clock_timestamp()::text || old_conversation.id::text)::uuid::text;
                        EXIT WHEN NOT EXISTS (
                            SELECT 1 FROM conversations WHERE title = candidate OR thread_id = candidate
                        );
                    END LOOP;
                END IF;
                UPDATE conversations SET thread_id = candidate WHERE id = old_conversation.id;
            END LOOP;
        END;
        $migration$;
    """))

    # 设为非空并加唯一索引
    op.alter_column('conversations', 'thread_id', nullable=False)
    op.create_unique_constraint('uq_conversations_thread_id', 'conversations', ['thread_id'])
    op.create_index('ix_conversations_thread_id', 'conversations', ['thread_id'])

    # 保留旧标题，不因标识迁移丢失可读信息。


def downgrade() -> None:
    op.drop_index('ix_conversations_thread_id', table_name='conversations')
    op.drop_constraint('uq_conversations_thread_id', 'conversations', type_='unique')
    op.drop_column('conversations', 'thread_id')
