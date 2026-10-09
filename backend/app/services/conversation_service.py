# 会话/消息/报告 DB 服务层
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.models.models import Conversation, ConversationStage, Message, MessageRole, StageConfirmation, StageType

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的上下文管理器"""
    async with async_session() as session:
        yield session


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
            conv.stage = stage_enum
        await session.commit()
        await session.refresh(conv)
        return conv.id

    if db is not None:
        try:
            return await _do_insert(db)
        except Exception as e:
            logger.warning(f"会话写库失败: {e}")
            await db.rollback()
            return None

    async with async_session() as session:
        try:
            return await _do_insert(session)
        except Exception as e:
            logger.warning(f"会话写库失败: {e}")
            await session.rollback()
            return None


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

    async def _do_insert(session: AsyncSession):
        session.add(Message(conversation_id=conv_id, role=role_enum, content=content, stage=stage_enum))
        await session.commit()

    if db is not None:
        try:
            await _do_insert(db)
        except Exception as e:
            logger.warning(f"消息写库失败: {e}")
            await db.rollback()
        return

    async with async_session() as session:
        try:
            await _do_insert(session)
        except Exception as e:
            logger.warning(f"消息写库失败: {e}")
            await session.rollback()


async def update_stage(
    thread_id: str,
    stage: str,
    db: AsyncSession | None = None,
    ) -> None:
    """更新会话阶段"""
    try:
        stage_enum = ConversationStage(stage)
    except ValueError:
        return

    async def _do_update(session: AsyncSession):
        result = await session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.stage = stage_enum
            await session.commit()

    if db is not None:
        try:
            await _do_update(db)
        except Exception as e:
            logger.warning(f"阶段更新失败: {e}")
            await db.rollback()
        return

    async with async_session() as session:
        try:
            await _do_update(session)
        except Exception as e:
            logger.warning(f"阶段更新失败: {e}")
            await session.rollback()


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
        except Exception as e:
            logger.warning(f"标题更新失败: {e}")
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
    ) -> None:
    """写入阶段确认记录"""

    async def _do_insert(session: AsyncSession):
        session.add(StageConfirmation(
            conversation_id=conv_id,
            stage=stage,
            input_data=input_data,
            output_data=output_data,
            is_confirmed=True,
        ))
        await session.commit()

    if db is not None:
        try:
            await _do_insert(db)
        except Exception as e:
            logger.warning(f"阶段确认写库失败: {e}")
            await db.rollback()
        return

    async with async_session() as session:
        try:
            await _do_insert(session)
        except Exception as e:
            logger.warning(f"阶段确认写库失败: {e}")
            await session.rollback()
