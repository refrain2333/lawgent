# S3 量刑情节收集
import json
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.service.utils import load_prompt
from app.core.logger import log_ai_call
from app.infrastructure.llm_client import get_chat_model

_PROMPT_TEMPLATE = load_prompt("s3")


# ── Tool 定义 ──────────────────────────────────────────────
class S3ReadyInput(BaseModel):
    facts: str = Field(description="已收集到的量刑情节汇总，逐项列出，未知的标注'不明'")


@tool(args_schema=S3ReadyInput)
def s3_ready_tool(facts: str) -> str:
    """当所有 importance=high 的量刑要素已收集完毕时调用此工具，传入情节汇总。"""
    return facts


# ── 辅助函数 ───────────────────────────────────────────────
def _build_search_context(s2_data: dict) -> str:
    """从S2检索结果提取关键信息注入提示词"""
    if not s2_data:
        return "暂无检索结果"

    lines = []
    fused = s2_data.get("fused", {})

    articles = fused.get("articles", [])
    if articles:
        lines.append("### 相关法条")
        for a in articles[:3]:
            title = a.get("title", "")
            content = (a.get("content") or "")[:150]
            lines.append(f"- {title}：{content}")

    cases = fused.get("cases", [])
    if cases:
        lines.append("### 类似案例量刑参考")
        for c in cases[:3]:
            acc = "、".join(c.get("accusations", []))
            months = c.get("sentence_months")
            sentence = f"{months}个月" if months else "未知"
            lines.append(f"- 罪名：{acc}，判决：有期徒刑{sentence}")

    kg = s2_data.get("paths", {}).get("kg", {})
    kg_articles = kg.get("articles", [])
    if kg_articles:
        lines.append("### 知识图谱匹配法条")
        for a in kg_articles[:2]:
            lines.append(f"- {a.get('title', '')}：{(a.get('content') or '')[:100]}")

    return "\n".join(lines) if lines else "暂无检索结果"


def build_s3_prompt(summary: str, s2_data: dict, checklist: dict) -> str:
    """构建注入了S2上下文和清单的S3提示词"""
    search_context = _build_search_context(s2_data)

    checklist_text = ""
    if checklist:
        crime = checklist.get("crime", "")
        items = checklist.get("checklist", [])
        lines = [f"罪名：{crime}"] if crime else []
        for item in items:
            importance = item.get("importance", "")
            label = item.get("label", "")
            question = item.get("question", "")
            lines.append(f"- [{importance}] {label}：{question}")
        checklist_text = "\n".join(lines)
    else:
        checklist_text = "暂无清单，请根据案情自行判断关键量刑要素"

    return (
        _PROMPT_TEMPLATE
        .replace("{summary}", summary)
        .replace("{search_context}", search_context)
        .replace("{checklist}", checklist_text)
    )

async def gen_s3_opener(checklist: dict, thread_id: str = "") -> str:
    """依据 S2 生成的量刑要素清单 (checklist) 生成具有针对性的 S3 开场破冰语"""
    # 提取排名前三的高优先级问题
    high_priority_questions = []
    if checklist and "checklist" in checklist:
        for item in checklist["checklist"]:
            if item.get("importance") == "high":
                high_priority_questions.append(item.get("question", ""))
            if len(high_priority_questions) >= 3:
                break

    if not high_priority_questions:
        return "基于刚才为您匹配的相关法条和判例，为了能够更精准地为您评估量刑风险，能向我补充一些案件细节吗（例如：有无退赃、是否自首等）？"

    prompt = (
        "你是一名专业的刑事律师助理，正在向一位由于涉嫌刑事案件而倍感焦虑的当事人进行询问。"
        "系统刚刚完成了罪名检索和判例参考，现在你需要向当事人收集关键的定罪量刑情节。\n\n"
        "以下是需要收集的最紧急和核心的几个情节问题：\n"
        f"{chr(10).join(['- ' + q for q in high_priority_questions])}\n\n"
        "请根据这些问题，生成一段流畅、亲和、专业的开场白（约80-120字）。\n"
        "风格要求：尽量自然、不过于模板化；尽量先聚焦一个最关键问题，避免一次抛出多个并列问题；"
        "如果确有必要可简短过渡，但整体保持简洁。\n"
        "你可以这样开头：'基于刚才检索出的法条与判例，我们需要补充一些关键事实。'\n"
        "注意：直接输出这段开场白本身，不要包含任何多余解释。"
    )

    messages = [
        SystemMessage(content="你是一名刑事法律专家助理。"),
        HumanMessage(content=prompt),
    ]
    response = await get_chat_model().ainvoke(messages)
    opener = response.content.strip()
    log_ai_call(stage="s3_gen_opener", thread_id=thread_id, input_messages=messages, output=opener)
    return opener


# ── 主函数 ─────────────────────────────────────────────────
async def chat_s3(
    user_message: str,
    history: list[dict],
    summary: str,
    s2_data: dict,
    checklist: dict,
    thread_id: str = "",
    ) -> AsyncGenerator[str, None]:
    """量刑情节收集：流式对话 + Tool Calling 强制触发阶段推进"""
    prompt = build_s3_prompt(summary, s2_data, checklist)

    messages = [SystemMessage(content=prompt)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    llm = get_chat_model().bind_tools([s3_ready_tool])

    accumulated = AIMessageChunk(content="")
    text_chunks = []

    async for chunk in llm.astream(messages):
        accumulated = accumulated + chunk
        if chunk.content:
            text_chunks.append(chunk.content)
            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

    full_text = "".join(text_chunks)
    log_ai_call(stage="s3_collecting", thread_id=thread_id, input_messages=messages, output=full_text)

    # 检查是否触发了 tool call
    if accumulated.tool_calls:
        tool_call = accumulated.tool_calls[0]
        facts = tool_call.get("args", {}).get("facts", "")
        if facts:
            yield f"data: {json.dumps({'type': 's3_ready', 'facts': facts}, ensure_ascii=False)}\n\n"
            return

    yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"
