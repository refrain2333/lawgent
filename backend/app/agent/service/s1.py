# S1 案情收集
import json
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.service.utils import llm_stream, load_prompt, parse_json
from app.core.logger import log_ai_call
from app.infrastructure.llm_client import get_chat_model

_PROMPT = load_prompt("s1")
_PROMPT_CONFIRMING = load_prompt("s1_confirming")

_TITLE_SYSTEM = "你是一个法律助手，请根据案情摘要生成一个简短的会话标题，不超过15个字，只输出标题本身，不要任何解释。"

_CHECK_SYSTEM = """你是一名刑事法律专家，请判断以下对话能否确认是一个刑事案件并生成客观概述。

严谨验证，必须同时清晰描述出：
1. 刑事行为类型；
2. 基本时间/地点/人员；
3. 初步核心后果(伤情/损失/数额等)。

任意一条缺失都不算 sufficient。

输出JSON，不要任何解释：
{"sufficient": true/false, "reason": "说明原因", "summary": "如果sufficient=true，生成客观案情概述：案情概述：XXX；如果false则为空字符串"}

只输出JSON。"""


# ── Tool 定义 ──────────────────────────────────────────────
class CaseReadyInput(BaseModel):
    summary: str = Field(description="完整的客观案情概述，包含时间、地点、行为、后果")


@tool(args_schema=CaseReadyInput)
def case_ready_tool(summary: str) -> str:
    """当对话中已收集到足够的刑事案件信息（案发时间地点、行为经过、基本后果）时调用此工具，传入案情概述。"""
    return summary


# ── 主函数 ─────────────────────────────────────────────────
async def chat_s1(
    user_message: str,
    history: list[dict],
    thread_id: str = "",
    ) -> AsyncGenerator[str, None]:
    """案情收集：流式对话 + Tool Calling 强制触发阶段推进"""
    messages = [SystemMessage(content=_PROMPT)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    llm = get_chat_model().bind_tools([case_ready_tool])

    accumulated = AIMessageChunk(content="")
    text_chunks = []

    async for chunk in llm.astream(messages):
        accumulated = accumulated + chunk
        if chunk.content:
            text_chunks.append(chunk.content)
            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

    full_text = "".join(text_chunks)
    log_ai_call(stage="s1_collecting", thread_id=thread_id, input_messages=messages, output=full_text)

    # 检查是否触发了 tool call
    if accumulated.tool_calls:
        tool_call = accumulated.tool_calls[0]
        summary = tool_call.get("args", {}).get("summary", "")
        if tool_call.get("name") == "case_ready_tool" and isinstance(summary, str) and summary.strip():
            yield f"data: {json.dumps({'type': 'case_ready', 'summary': summary}, ensure_ascii=False)}\n\n"
            return

    yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"


async def chat_s1_confirming(user_message: str, history: list[dict], thread_id: str = "") -> AsyncGenerator[str, None]:
    """案情确认：处理用户纠正或补充"""
    response_chunks = []
    async for chunk in llm_stream(_PROMPT_CONFIRMING, history, user_message, stage="s1_confirming", thread_id=thread_id):
        data = json.loads(chunk[6:])
        if data.get("type") == "token":
            response_chunks.append(data["content"])
            yield chunk
    updated_history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": "".join(response_chunks)},
    ]
    result = await check_sufficient(updated_history, thread_id=thread_id)
    if result["sufficient"]:
        yield f"data: {json.dumps({'type': 'case_ready', 'summary': result['summary']}, ensure_ascii=False)}\n\n"
    else:
        yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"


async def check_sufficient(history: list[dict], thread_id: str = "") -> dict:
    """判断当前对话信息是否足以描述一个刑事案件"""
    messages = [SystemMessage(content=_CHECK_SYSTEM)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    response = await get_chat_model().ainvoke(messages)
    raw = response.content.strip()
    log_ai_call(stage="s1_check_sufficient", thread_id=thread_id, input_messages=messages, output=raw)

    result = parse_json(raw)
    if isinstance(result.get("sufficient"), bool):
        summary = result.get("summary")
        if not result["sufficient"]:
            reason = result.get("reason")
            return {"sufficient": False, "reason": reason if isinstance(reason, str) and reason.strip() else "信息不足，请继续补充案情", "summary": ""}
        if isinstance(summary, str) and summary.strip():
            return result
    return {"sufficient": False, "reason": "判断失败，请继续补充案情", "summary": ""}


async def generate_title(summary: str) -> str:
    """根据案情摘要生成会话标题"""
    messages = [
        SystemMessage(content=_TITLE_SYSTEM),
        HumanMessage(content=summary),
    ]
    response = await get_chat_model().ainvoke(messages)
    return response.content.strip()[:30]
