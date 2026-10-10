# 会话/消息/报告 DB 服务层
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.models.models import (
    Conversation,
    ConversationStage,
    Message,
    MessageRole,
    StageConfirmation,
    StageType,
    utc_now,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_session(db: AsyncSession | None = None) -> AsyncGenerator[AsyncSession, None]:
    """复用请求事务；写入失败必须向调用方传播，避免错误推进阶段。"""
    if db is not None:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
    else:
        async with async_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def list_conversations(user_id: int, db: AsyncSession) -> list[dict]:
    """返回用户历史会话列表，按更新时间倒序"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(
            func.coalesce(Conversation.updated_at, Conversation.created_at).desc(),
            Conversation.created_at.desc(),
        )
        .limit(50)
        )
    convs = result.scalars().all()
    return [
        {
            "id": c.id,
            "thread_id": c.thread_id,
            "title": c.title,
            "stage": c.stage,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


async def upsert_conversation(
    user_id: int,
    thread_id: str,
    stage: str,
    db: AsyncSession | None = None,
) -> int | None:
    """写入或更新会话记录，返回 conversation.id"""
    try:
        stage_enum = ConversationStage(stage)
    except ValueError:
        stage_enum = ConversationStage.S1_COLLECTING

    async def _do_insert(session: AsyncSession):
        result = await session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(user_id=user_id, thread_id=thread_id, stage=stage_enum)
            session.add(conv)
        else:
            if conv.user_id != user_id:
                raise ValueError("会话归属不匹配")
            conv.stage = stage_enum
        await session.commit()
        await session.refresh(conv)
        return conv.id

    async with get_session(db) as session:
        return await _do_insert(session)


async def save_message(
    conv_id: int,
    role: str,
    content: str,
    stage: str = "s1_collecting",
    db: AsyncSession | None = None,
) -> None:
    """写入一条消息记录"""
    if not conv_id or not content:
        return
    try:
        role_enum = MessageRole(role)
    except ValueError:
        role_enum = MessageRole.ASSISTANT
    try:
        stage_enum = ConversationStage(stage)
    except ValueError:
        stage_enum = ConversationStage.S1_COLLECTING

    async with get_session(db) as session:
        session.add(Message(conversation_id=conv_id, role=role_enum, content=content, stage=stage_enum))
        await session.execute(update(Conversation).where(Conversation.id == conv_id).values(updated_at=utc_now()))
        await session.commit()


async def update_stage(
    thread_id: str,
    stage: str,
    db: AsyncSession | None = None,
    *,
    expected_stage: str | None = None,
    inactive_before: datetime | None = None,
) -> bool:
    """按预期阶段更新，阻止重复确认和过期任务覆盖新状态。"""
    stage_enum = ConversationStage(stage)
    async with get_session(db) as session:
        stmt = update(Conversation).where(Conversation.thread_id == thread_id)
        if expected_stage is not None:
            stmt = stmt.where(Conversation.stage == expected_stage)
        if inactive_before is not None:
            stmt = stmt.where(func.coalesce(Conversation.updated_at, Conversation.created_at) <= inactive_before)
        result = await session.execute(stmt.values(stage=stage_enum, updated_at=utc_now()))
        await session.commit()
        return result.rowcount == 1


async def update_title(thread_id: str, title: str) -> None:
    """异步更新会话标题"""
    async with async_session() as session:
        try:
            result = await session.execute(
                select(Conversation).where(Conversation.thread_id == thread_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.title = title
                await session.commit()
        except Exception:
            logger.warning("标题更新失败")
            await session.rollback()


async def get_messages(thread_id: str, db: AsyncSession | None = None) -> list[dict]:
    """根据 thread_id 查询会话历史消息"""

    async def _do_query(session: AsyncSession):
        result = await session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return []
        msg_result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
        )
        msgs = msg_result.scalars().all()
        return [
            {
                "role": m.role,
                "content": m.content,
                "stage": m.stage,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]

    if db is not None:
        return await _do_query(db)

    async with async_session() as session:
        return await _do_query(session)


async def delete_conversation(thread_id: str, user_id: int, db: AsyncSession) -> bool:
    """删除会话及其所有关联数据（消息、阶段确认），返回是否成功"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    await db.delete(conv)
    await db.commit()
    return True


async def save_stage_confirmation(
    conv_id: int,
    stage: StageType,
    input_data: dict,
    output_data: dict,
    db: AsyncSession | None = None,
    *,
    next_stage: str | None = None,
    expected_stage: str | None = None,
) -> bool:
    """将阶段产物与状态在同一事务中保存，失败时一起回滚。"""
    async with get_session(db) as session:
        if next_stage is not None:
            stmt = update(Conversation).where(Conversation.id == conv_id)
            if expected_stage is not None:
                stmt = stmt.where(Conversation.stage == expected_stage)
            result = await session.execute(stmt.values(stage=ConversationStage(next_stage), updated_at=utc_now()))
            if result.rowcount != 1:
                await session.rollback()
                return False
        session.add(StageConfirmation(
            conversation_id=conv_id,
            stage=stage,
            input_data=input_data,
            output_data=output_data,
            is_confirmed=True,
        ))
        await session.commit()
        return True
