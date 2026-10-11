# Agent REST + SSE 接口
import asyncio
import json
import uuid
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service.s1 import chat_s1, chat_s1_confirming, check_sufficient, generate_title
from app.agent.service.s2 import gen_checklist, run_s2
from app.agent.service.s3 import chat_s3, summarize_facts
from app.agent.service.s4 import chat_s4, gen_report
from app.core.deps import get_user_id
from app.core.logger import logger
from app.core.rate_limit import check_rate_limit
from app.db.database import get_db
from app.models.models import (
    Conversation,
    ConversationStage,
    Message,
    MessageRole,
    StageConfirmation,
    StageType,
    utc_now,
)
from app.schemas.v1.agent import ConfirmRequest, MessageRequest, SessionCreateRequest
from app.services import conversation_service

router = APIRouter(tags=["Agent"])
_background_tasks: set[asyncio.Task[None]] = set()
_STAGE_TASK_TIMEOUT = 15 * 60
_STAGE_RECOVERY_AFTER = timedelta(minutes=30)

# 单用户限流：创建会话与发送消息（消息会消耗 LLM 额度）
_SESSION_RATE_LIMIT = 10
_SESSION_RATE_WINDOW = 60
_MESSAGE_RATE_LIMIT = 20
_MESSAGE_RATE_WINDOW = 60


def _start_background(coro: Coroutine[Any, Any, None]) -> None:
    """持有任务引用，并消费后台异常以免敏感异常输出到默认日志。"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def done(completed: asyncio.Task[None]) -> None:
        _background_tasks.discard(completed)
        if not completed.cancelled() and (error := completed.exception()) is not None:
            logger.error(f"后台任务未完成: {type(error).__name__}")

    task.add_done_callback(done)


async def _run_stage_task(
    thread_id: str,
    coro: Coroutine[Any, Any, None],
    running_stage: ConversationStage,
    failed_stage: ConversationStage,
) -> None:
    try:
        await asyncio.wait_for(coro, timeout=_STAGE_TASK_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError) as error:
        await conversation_service.update_stage(thread_id, failed_stage, expected_stage=running_stage)
        if isinstance(error, asyncio.CancelledError):
            raise
        logger.warning(f"阶段任务超时: thread={thread_id}")


async def _get_conv(thread_id: str, user_id: int, db: AsyncSession) -> Conversation:
    """获取当前用户的会话；未知或他人会话统一返回 404。"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.thread_id == thread_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


async def _get_stage_confirmation(conv_id: int, stage: StageType, db: AsyncSession) -> dict:
    """取指定阶段的确认数据"""
    result = await db.execute(
        select(StageConfirmation)
        .where(
            StageConfirmation.conversation_id == conv_id,
            StageConfirmation.stage == stage,
        )
        .order_by(StageConfirmation.created_at.desc())
        .limit(1)
    )
    sc = result.scalar_one_or_none()
    return sc.output_data if sc else {}


@router.get("/conversations", summary="获取当前用户会话列表")
async def list_conversations(
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """返回当前用户的历史会话列表"""
    result = await conversation_service.list_conversations(user_id, db)
    logger.debug(f"获取会话列表: user={user_id} count={len(result)}")
    return result


@router.get("/conversations/{thread_id}/messages", summary="获取会话历史消息")
async def get_conversation_messages(
    thread_id: str,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """返回指定会话的历史消息列表"""
    await _get_conv(thread_id, user_id, db)  # 校验会话归属
    result = await conversation_service.get_messages(thread_id, db)
    logger.debug(f"获取历史消息: thread={thread_id} user={user_id} count={len(result)}")
    return result


@router.post("/sessions", summary="创建会话")
async def create_session(
    body: SessionCreateRequest,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """创建新会话，返回 thread_id"""
    check_rate_limit(f"session:{user_id}", _SESSION_RATE_LIMIT, _SESSION_RATE_WINDOW)
    thread_id = str(uuid.uuid4())
    conv = Conversation(user_id=user_id, thread_id=thread_id, stage=ConversationStage.S1_COLLECTING)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    logger.info(f"新会话创建: thread={thread_id} user={user_id}")
    return {"thread_id": thread_id, "stage": conv.stage}


@router.get("/sessions/{thread_id}/state", summary="查询会话当前状态")
async def get_session_state(
    thread_id: str,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """返回当前阶段，confirming 阶段额外返回摘要供前端恢复确认卡片"""
    conv = await _get_conv(thread_id, user_id, db)
    failed_stage = {
        ConversationStage.S2_SEARCHING: ConversationStage.S2_FAILED,
        ConversationStage.S4_GENERATING: ConversationStage.S4_FAILED,
    }.get(conv.stage)
    if failed_stage is not None:
        # 恢复窗口长于运行时限；条件更新避免过期轮询误伤刚重试的任务。
        changed = await conversation_service.update_stage(
            thread_id, failed_stage, db, expected_stage=conv.stage,
            inactive_before=utc_now() - _STAGE_RECOVERY_AFTER,
        )
        if changed:
            conv.stage = failed_stage
            logger.warning(f"已恢复中断的阶段任务: thread={thread_id}")
    resp: dict = {"thread_id": thread_id, "stage": conv.stage}

    # 包含所有阶段的历史确认结果，可以在前端统一展示
    s1_data = await _get_stage_confirmation(conv.id, StageType.S1_CONFIRM, db)
    if s1_data:
        resp["s1_summary"] = s1_data.get("summary", "")

    s2_search = await _get_stage_confirmation(conv.id, StageType.S2_SEARCH, db)
    if s2_search:
        # S2 的结果直接是完整的字典结果
        resp["s2_search"] = s2_search.get("fused", {}) if "fused" in s2_search else s2_search

    s3_data = await _get_stage_confirmation(conv.id, StageType.S3_CONFIRM, db)
    if s3_data:
        resp["s3_facts"] = s3_data.get("facts", "")

    # S3 开场白是否已写入（用于前端控制“进入S3”按钮显示）
    opener_result = await db.execute(
        select(Message.id)
        .where(
            Message.conversation_id == conv.id,
            Message.stage == ConversationStage.S3_COLLECTING,
            Message.role == MessageRole.ASSISTANT,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    resp["s3_opener_ready"] = opener_result.scalar_one_or_none() is not None

    if conv.stage == ConversationStage.S1_CONFIRMING:
        resp["summary"] = s1_data.get("summary", "")
    elif conv.stage == ConversationStage.S3_CONFIRMING:
        resp["facts"] = s3_data.get("facts", "")

    logger.debug(f"查询会话状态: thread={thread_id} stage={conv.stage}")
    return resp


@router.post("/sessions/{thread_id}/message", summary="发送消息（SSE 流式）")
async def send_message(
    thread_id: str,
    body: MessageRequest,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """根据当前阶段路由到对应处理函数"""
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    check_rate_limit(f"message:{user_id}", _MESSAGE_RATE_LIMIT, _MESSAGE_RATE_WINDOW)
    conv = await _get_conv(thread_id, user_id, db)
    history = await conversation_service.get_messages(thread_id, db)
    message_stage = conv.stage
    correction = message_stage == ConversationStage.S1_CONFIRMING

    if conv.stage == ConversationStage.S1_COLLECTING:
        def stream_fn(c, h, **kw):
            return chat_s1(c, h, **kw)
    elif conv.stage == ConversationStage.S1_CONFIRMING:
        def stream_fn(c, h, **kw):
            return chat_s1_confirming(c, h, **kw)
    elif conv.stage == ConversationStage.S3_COLLECTING:
        s1_data = await _get_stage_confirmation(conv.id, StageType.S1_CONFIRM, db)
        s2_data = await _get_stage_confirmation(conv.id, StageType.S2_SEARCH, db)
        checklist = await _get_stage_confirmation(conv.id, StageType.S2_CHECKLIST, db)
        summary = s1_data.get("summary", "")
        history = [m for m in history if m.get("stage") == ConversationStage.S3_COLLECTING]
        def stream_fn(c, h, **kw):
            return chat_s3(c, h, summary=summary, s2_data=s2_data, checklist=checklist, **kw)
    elif conv.stage == ConversationStage.S4_DONE:
        s1_data = await _get_stage_confirmation(conv.id, StageType.S1_CONFIRM, db)
        s3_data = await _get_stage_confirmation(conv.id, StageType.S3_CONFIRM, db)
        report_data = await _get_stage_confirmation(conv.id, StageType.S4_REPORT, db)
        summary = s1_data.get("summary", "")
        s3_facts = s3_data.get("facts", "")
        def stream_fn(c, h, **kw):
            return chat_s4(c, h, summary=summary, s3_facts=s3_facts, report=report_data, **kw)
    else:
        raise HTTPException(status_code=400, detail=f"当前阶段 {conv.stage} 不支持发送消息")

    if correction:
        changed = await conversation_service.update_stage(
            thread_id, ConversationStage.S1_COLLECTING, db,
            expected_stage=ConversationStage.S1_CONFIRMING,
        )
        if not changed:
            raise HTTPException(status_code=409, detail="会话阶段已变化，请刷新")
        message_stage = ConversationStage.S1_COLLECTING
    await conversation_service.save_message(conv.id, "user", content, message_stage, db)
    logger.info(f"收到消息: thread={thread_id} stage={message_stage} len={len(content)}")

    async def generate():
        ai_content = []
        terminal_event = None
        saved = False
        try:
            if correction:
                yield f"data: {json.dumps({'type': 'stage_changed', 'stage': message_stage})}\n\n"
            async for chunk in stream_fn(content, history, thread_id=thread_id):
                if chunk.startswith("data: "):
                    data = json.loads(chunk[6:])
                    if data.get("type") == "token":
                        ai_content.append(data.get("content", ""))
                    elif data.get("type") in {"case_ready", "s3_ready", "end", "done"}:
                        terminal_event = data
                        continue
                yield chunk

            # 确认卡片只能在对应摘要及阶段已成功持久化后发送。
            if ai_content:
                await conversation_service.save_message(conv.id, "assistant", "".join(ai_content).strip(), message_stage)
            saved = True
            if terminal_event and terminal_event["type"] in {"case_ready", "s3_ready"}:
                is_s1 = terminal_event["type"] == "case_ready"
                key = "summary" if is_s1 else "facts"
                value = terminal_event.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("阶段摘要无效")
                changed = await conversation_service.save_stage_confirmation(
                    conv_id=conv.id,
                    stage=StageType.S1_CONFIRM if is_s1 else StageType.S3_CONFIRM,
                    input_data={}, output_data={key: value},
                    next_stage=ConversationStage.S1_CONFIRMING if is_s1 else ConversationStage.S3_CONFIRMING,
                    expected_stage=message_stage,
                )
                if not changed:
                    raise ValueError("会话阶段已变化")
                if is_s1:
                    _start_background(_gen_and_save_title(thread_id, value))
            event = terminal_event or {"type": "end"}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            logger.error(f"对话生成或保存失败: thread={thread_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': '回复未完成，请刷新会话后重试'}, ensure_ascii=False)}\n\n"
        finally:
            # 中途断流也尽量保存部分回复，不推进确认阶段。
            if not saved and ai_content:
                _start_background(conversation_service.save_message(
                    conv.id, "assistant", "".join(ai_content).strip(), message_stage,
                ))

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/conversations/{thread_id}", summary="删除会话")
async def delete_conversation(
    thread_id: str,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """删除会话及其全部消息和阶段数据"""
    ok = await conversation_service.delete_conversation(thread_id, user_id, db)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    logger.info(f"会话已删除: thread={thread_id} user={user_id}")
    return {"deleted": True}


@router.get("/sessions/{thread_id}/report", summary="获取S4风险评估报告")
async def get_report(
    thread_id: str,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """返回S4阶段生成的风险评估报告"""
    conv = await _get_conv(thread_id, user_id, db)
    if conv.stage != ConversationStage.S4_DONE:
        raise HTTPException(status_code=404, detail="报告尚未生成")
    report = await _get_stage_confirmation(conv.id, StageType.S4_REPORT, db)
    if not report:
        logger.debug(f"报告尚未生成: thread={thread_id}")
        raise HTTPException(status_code=404, detail="报告尚未生成")
    logger.debug(f"获取报告: thread={thread_id}")
    return report


@router.post("/sessions/{thread_id}/advance", summary="推进阶段")
async def advance_stage(
    thread_id: str,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """S1收集完毕时，AI判断信息是否足够；S3信号失效时手动推进"""
    conv = await _get_conv(thread_id, user_id, db)

    if conv.stage == ConversationStage.S3_COLLECTING:
        history = await conversation_service.get_messages(thread_id, db)
        history = [m for m in history if m.get("stage") == ConversationStage.S3_COLLECTING]
        if not any(m["role"] == "user" for m in history):
            raise HTTPException(status_code=400, detail="请先补充量刑情节再确认")
        facts = await summarize_facts(history, thread_id=thread_id)
        changed = await conversation_service.save_stage_confirmation(
            conv_id=conv.id, stage=StageType.S3_CONFIRM,
            input_data={}, output_data={"facts": facts}, db=db,
            next_stage=ConversationStage.S3_CONFIRMING,
            expected_stage=ConversationStage.S3_COLLECTING,
        )
        if not changed:
            raise HTTPException(status_code=409, detail="会话阶段已变化，请刷新")
        logger.info(f"S3 手动推进: thread={thread_id} -> s3_confirming")
        return {"thread_id": thread_id, "stage": ConversationStage.S3_CONFIRMING, "sufficient": True, "summary": facts}

    if conv.stage != ConversationStage.S1_COLLECTING:
        raise HTTPException(status_code=400, detail=f"当前阶段 {conv.stage} 不支持推进")

    history = await conversation_service.get_messages(thread_id, db)
    result = await check_sufficient(history, thread_id=thread_id)
    if not result.get("sufficient"):
        reason = result.get("reason", "信息不足，请继续补充案情")
        logger.info(f"S1 advance 信息不足: thread={thread_id}")
        await conversation_service.save_message(conv.id, "assistant", reason, conv.stage, db)
        return {
            "thread_id": thread_id,
            "stage": conv.stage,
            "sufficient": False,
            "reason": reason,
        }
    summary = result.get("summary", "")
    changed = await conversation_service.save_stage_confirmation(
        conv_id=conv.id,
        stage=StageType.S1_CONFIRM,
        input_data={},
        output_data={"summary": summary},
        db=db,
        next_stage=ConversationStage.S1_CONFIRMING,
        expected_stage=ConversationStage.S1_COLLECTING,
    )
    if not changed:
        raise HTTPException(status_code=409, detail="会话阶段已变化，请刷新")
    logger.info(f"S1 手动推进: thread={thread_id} -> s1_confirming")
    return {
        "thread_id": thread_id,
        "stage": ConversationStage.S1_CONFIRMING,
        "sufficient": True,
        "summary": summary,
    }


@router.post("/sessions/{thread_id}/confirm", summary="确认当前阶段")
async def confirm_stage(
    thread_id: str,
    body: ConfirmRequest,
    user_id: int = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    ):
    """卡点确认：accepted=true 推进阶段，false 回退重新收集"""
    conv = await _get_conv(thread_id, user_id, db)

    previous_stage = conv.stage
    summary = ""
    if previous_stage in {ConversationStage.S1_CONFIRMING, ConversationStage.S2_FAILED}:
        next_stage = ConversationStage.S2_SEARCHING if body.accepted else ConversationStage.S1_COLLECTING
        if body.accepted:
            s1_data = await _get_stage_confirmation(conv.id, StageType.S1_CONFIRM, db)
            summary = s1_data.get("summary", "")
            if not isinstance(summary, str) or not summary.strip():
                raise HTTPException(status_code=400, detail="缺少案情摘要，请先补充案情")
    elif previous_stage in {ConversationStage.S3_CONFIRMING, ConversationStage.S4_FAILED}:
        next_stage = ConversationStage.S4_GENERATING if body.accepted else ConversationStage.S3_COLLECTING
        if body.accepted:
            s3_data = await _get_stage_confirmation(conv.id, StageType.S3_CONFIRM, db)
            facts = s3_data.get("facts")
            if not isinstance(facts, str) or not facts.strip():
                raise HTTPException(status_code=400, detail="缺少量刑情节，请先补充")
    else:
        raise HTTPException(status_code=400, detail=f"当前阶段 {previous_stage} 无需确认")

    changed = await conversation_service.update_stage(thread_id, next_stage, db, expected_stage=previous_stage)
    if not changed:
        raise HTTPException(status_code=409, detail="会话阶段已变化，请刷新")
    # 先提交阶段，再启动任务；重复确认不能启动第二份后台任务。
    if body.accepted:
        if next_stage == ConversationStage.S2_SEARCHING:
            _start_background(_gen_and_save_title(thread_id, summary))
            _start_background(_run_stage_task(
                thread_id, _run_s2_and_save(thread_id, conv.id, summary),
                ConversationStage.S2_SEARCHING, ConversationStage.S2_FAILED,
            ))
        else:
            _start_background(_run_stage_task(
                thread_id, _run_s4_and_save(thread_id, conv.id),
                ConversationStage.S4_GENERATING, ConversationStage.S4_FAILED,
            ))
    logger.info(f"阶段确认: thread={thread_id} accepted={body.accepted} {previous_stage} -> {next_stage}")
    return {"thread_id": thread_id, "stage": next_stage}


async def _gen_and_save_title(thread_id: str, summary: str) -> None:
    """后台任务：根据案情摘要生成会话标题并写库"""
    try:
        title = await generate_title(summary)
        await conversation_service.update_title(thread_id, title)
        logger.info(f"会话标题已生成: thread={thread_id}")
    except Exception:
        logger.warning(f"标题生成失败: thread={thread_id}")


async def _run_s2_and_save(thread_id: str, conv_id: int, summary: str) -> None:
    """后台任务：执行S2检索+生成清单，结果写入StageConfirmation，推进到s3_collecting"""
    try:
        # 1. 执行检索
        search_result = await run_s2(summary, thread_id=thread_id)
        await conversation_service.save_stage_confirmation(
            conv_id=conv_id,
            stage=StageType.S2_SEARCH,
            input_data={"summary": summary},
            output_data=search_result,
        )
        logger.info(f"S2检索完成: {thread_id}")

        # 2. 生成量刑要素清单
        checklist = await gen_checklist(summary, search_result, thread_id=thread_id)
        changed = await conversation_service.save_stage_confirmation(
            conv_id=conv_id,
            stage=StageType.S2_CHECKLIST,
            input_data={"summary": summary},
            output_data=checklist,
            next_stage=ConversationStage.S3_COLLECTING,
            expected_stage=ConversationStage.S2_SEARCHING,
        )
        if not changed:
            return
        logger.info(f"S2清单生成完成: {thread_id}")
    except Exception:
        logger.error(f"S2任务失败: thread={thread_id}")
        # 写入失败状态，前端轮询时可感知
        await conversation_service.update_stage(thread_id, ConversationStage.S2_FAILED, expected_stage=ConversationStage.S2_SEARCHING)
        return

    # 3. S2核心产物完成后立即推进到 s3_collecting，避免被 opener 生成耗时阻塞
    logger.info(f"已推进到s3_collecting: {thread_id}")

    # 4. 异步生成 S3 开场白（失败不回退阶段）
    from app.agent.service.s3 import gen_s3_opener
    from app.db.database import async_session

    try:
        welcome_msg = await gen_s3_opener(checklist, thread_id)
        if not welcome_msg.strip():
            raise ValueError("开场语为空")
    except Exception:
        logger.warning(f"S3开场白生成失败，使用默认提示: thread={thread_id}")
        welcome_msg = "检索已完成。请补充量刑相关事实，例如是否自首、是否退赔；不确定的内容可以说明不清楚。"
    try:
        async with async_session() as db:
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id).with_for_update())
            conv = result.scalar_one_or_none()
            if conv is None or conv.stage != ConversationStage.S3_COLLECTING:
                return
            user_message = await db.execute(select(Message.id).where(
                Message.conversation_id == conv_id,
                Message.stage == ConversationStage.S3_COLLECTING,
                Message.role == MessageRole.USER,
            ).limit(1))
            if user_message.scalar_one_or_none() is None:
                await conversation_service.save_message(conv_id, "assistant", welcome_msg, ConversationStage.S3_COLLECTING, db)
    except Exception:
        logger.warning(f"S3开场白生成失败: thread={thread_id}")


async def _run_s4_and_save(thread_id: str, conv_id: int) -> None:
    """后台任务：取S1/S2/S3数据生成风险报告，写入StageConfirmation"""
    try:
        from sqlalchemy import select as _select

        from app.db.database import async_session
        async with async_session() as db:
            async def _get(stage):
                r = await db.execute(
                    _select(StageConfirmation)
                    .where(StageConfirmation.conversation_id == conv_id, StageConfirmation.stage == stage)
                    .order_by(StageConfirmation.created_at.desc()).limit(1)
                )
                sc = r.scalar_one_or_none()
                return sc.output_data if sc else {}

            s1_data = await _get(StageType.S1_CONFIRM)
            s2_data = await _get(StageType.S2_SEARCH)
            checklist = await _get(StageType.S2_CHECKLIST)
            s3_data = await _get(StageType.S3_CONFIRM)

        summary = s1_data.get("summary", "")
        s3_facts = s3_data.get("facts", "")

        report = await gen_report(summary, s2_data, checklist, s3_facts, thread_id=thread_id)
        changed = await conversation_service.save_stage_confirmation(
            conv_id=conv_id,
            stage=StageType.S4_REPORT,
            input_data={"summary": summary},
            output_data=report,
            next_stage=ConversationStage.S4_DONE,
            expected_stage=ConversationStage.S4_GENERATING,
        )
        if changed:
            logger.info(f"S4报告生成完成: {thread_id}")
    except Exception:
        logger.error(f"S4任务失败: thread={thread_id}")
        await conversation_service.update_stage(thread_id, ConversationStage.S4_FAILED, expected_stage=ConversationStage.S4_GENERATING)
