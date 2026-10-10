# S4 风险评估报告生成
import json
import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.service.utils import llm_stream, load_prompt, parse_json
from app.core.logger import log_ai_call
from app.infrastructure.llm_client import get_chat_model

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = load_prompt("s4", with_base=False)
_CHAT_PROMPT_TEMPLATE = load_prompt("s4_chat", with_base=False)


def _build_prompt(summary: str, s2_data: dict, checklist: dict, s3_facts: str) -> str:
    fused = s2_data.get("fused", {})

    articles_text = "\n".join(
        f"- {a.get('title', '')}：{(a.get('content') or '')[:200]}"
        for a in fused.get("articles", [])[:5]
    ) or "暂无"

    cases_text = "\n".join(
        f"- 罪名：{'、'.join(c.get('accusations', []))}，判决：{c.get('sentence_months', '未知')}个月"
        for c in fused.get("cases", [])[:5]
    ) or "暂无"

    if checklist:
        crime = checklist.get("crime", "")
        items = checklist.get("checklist", [])
        lines = [f"罪名：{crime}"] if crime else []
        for item in items:
            lines.append(f"- {item.get('label', '')}：{item.get('question', '')}")
        checklist_text = "\n".join(lines)
    else:
        checklist_text = "暂无"

    return (
        _PROMPT_TEMPLATE
        .replace("{summary}", summary)
        .replace("{articles}", articles_text)
        .replace("{cases}", cases_text)
        .replace("{checklist}", checklist_text)
        .replace("{s3_facts}", s3_facts or "暂无")
    )


async def chat_s4(
    user_message: str,
    history: list[dict],
    summary: str,
    s3_facts: str,
    report: dict,
    thread_id: str = "",
    ) -> AsyncGenerator[str, None]:
    """S4 答疑对话，基于已生成报告回答用户疑问"""
    prompt = (
        _CHAT_PROMPT_TEMPLATE
        .replace("{summary}", summary or "暂无")
        .replace("{s3_facts}", s3_facts or "暂无")
        .replace("{report}", json.dumps(report, ensure_ascii=False) if report else "暂无")
    )
    async for chunk in llm_stream(prompt, history, user_message, stage="s4_chat", thread_id=thread_id):
        yield chunk


async def gen_report(
    summary: str,
    s2_data: dict,
    checklist: dict,
    s3_facts: str,
    thread_id: str = "",
    ) -> dict:
    """生成S4风险评估报告"""
    prompt = _build_prompt(summary, s2_data, checklist, s3_facts)
    messages = [
        SystemMessage(content="你是一名专业的刑事法律助手。"),
        HumanMessage(content=prompt),
    ]
    response = await get_chat_model().ainvoke(messages)
    raw = response.content.strip()
    log_ai_call(stage="s4_report", thread_id=thread_id, input_messages=messages, output=raw)

    result = parse_json(raw)
    if not result:
        logger.warning("S4 报告输出不是有效 JSON 对象")
    return result
