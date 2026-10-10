# 公共工具
import json
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.logger import log_ai_call
from app.infrastructure.llm_client import get_chat_model

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str, with_base: bool = True) -> str:
    base = ""
    if with_base:
        base_p = PROMPTS_DIR / "base.md"
        if base_p.exists():
            base = base_p.read_text(encoding="utf-8").strip() + "\n\n---\n\n"
    p = PROMPTS_DIR / f"{name}.md"
    content = p.read_text(encoding="utf-8") if p.exists() else ""
    return base + content


def parse_json(raw: str) -> dict:
    """解析 LLM 输出的 JSON 对象，兼容 markdown 代码块包裹的情况"""
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            result = json.loads(m.group())
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return {}


async def llm_stream(
    system: str,
    history: list[dict],
    user_message: str,
    stage: str = "unknown",
    thread_id: str = "",
    ) -> AsyncGenerator[str, None]:
    messages = [SystemMessage(content=system)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    output_chunks = []
    async for chunk in get_chat_model().astream(messages):
        if chunk.content:
            output_chunks.append(chunk.content)
            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

    output = "".join(output_chunks)
    log_ai_call(stage=stage, thread_id=thread_id, input_messages=messages, output=output)
    yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"
