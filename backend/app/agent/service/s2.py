# S2 罪名检索
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.service.utils import load_prompt, parse_json
from app.core.logger import log_ai_call
from app.infrastructure.llm_client import get_chat_model
from app.services.search_service import search_async

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = load_prompt("s2", with_base=False)
_CHECKLIST_PROMPT = load_prompt("s2_checklist", with_base=False)

_CRIMES_FILE = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "cases" / "crime.txt"
_CRIMES = "、".join(
    line.strip() for line in _CRIMES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()
) if _CRIMES_FILE.exists() else ""

_PROMPT = _PROMPT_TEMPLATE.replace("{crimes}", _CRIMES)


async def _gen_queries(summary: str, thread_id: str = "") -> dict:
    """LLM 根据案情摘要生成5种检索词"""
    prompt = _PROMPT.replace("{summary}", summary)
    messages = [
        SystemMessage(content="你是一名刑事法律专家。"),
        HumanMessage(content=prompt),
    ]
    response = await get_chat_model().ainvoke(messages)
    raw = response.content.strip()
    log_ai_call(stage="s2_gen_queries", thread_id=thread_id, input_messages=messages, output=raw)
    result = parse_json(raw)
    if not result:
        logger.warning("S2 检索词解析失败，使用案情摘要回退")
    return result


async def gen_checklist(summary: str, search_result: dict, thread_id: str = "") -> dict:
    """根据案情和检索结果生成量刑要素清单"""
    fused = search_result.get("fused", {})

    articles_text = "\n".join(
        f"- {a.get('title', '')}：{(a.get('content') or '')[:150]}"
        for a in fused.get("articles", [])[:5]
    ) or "暂无"

    cases_text = "\n".join(
        f"- 罪名：{'、'.join(c.get('accusations', []))}，判决：{c.get('sentence_months', '未知')}个月"
        for c in fused.get("cases", [])[:5]
    ) or "暂无"

    prompt = _CHECKLIST_PROMPT.replace("{summary}", summary).replace("{articles}", articles_text).replace("{cases}", cases_text)
    messages = [
        SystemMessage(content="你是一名刑事法律专家。"),
        HumanMessage(content=prompt),
    ]
    response = await get_chat_model().ainvoke(messages)
    raw = response.content.strip()
    log_ai_call(stage="s2_checklist", thread_id=thread_id, input_messages=messages, output=raw)
    result = parse_json(raw)
    if not result:
        logger.warning("清单输出不是有效 JSON 对象")
    return result


async def run_s2(summary: str, thread_id: str = "", count: int = 5) -> dict:
    """执行S2检索，返回检索结果dict"""
    queries = await _gen_queries(summary, thread_id)
    logger.info(f"S2 检索词生成完成: thread={thread_id}")

    result = await search_async(
        vector=queries.get("vector", summary),
        bm25=queries.get("bm25", ""),
        kg=queries.get("kg", ""),
        query2doc=queries.get("query2doc", ""),
        hyde=queries.get("hyde", ""),
        count=count,
    )

    return {
        "queries": queries,
        "fused": {
            "articles": [a.model_dump() for a in result.articles],
            "cases": [c.model_dump() for c in result.cases],
            "total_articles": result.total_articles,
            "total_cases": result.total_cases,
        },
        "paths": {
            name: {
                "articles": [a.model_dump() for a in path.articles],
                "cases": [c.model_dump() for c in path.cases],
            }
            for name, path in (result.paths or {}).items()
        },
        "elapsed_ms": result.elapsed_ms,
    }
