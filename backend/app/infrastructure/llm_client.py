# DeepSeek LLM 客户端（LangChain ChatOpenAI 封装）
import logging
from functools import lru_cache

import httpx
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 120.0


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    """返回供数据库状态机各阶段使用的 LangChain ChatOpenAI 实例。

    使用 lru_cache 保证全局唯一实例，避免重复初始化。
    trust_env=False 确保不走系统代理，直连 DeepSeek API。
    """
    if not settings.LLM_API_KEY.strip():
        raise ValueError("LLM_API_KEY 未配置，请先设置有效的 LLM 密钥")
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=0.7,
        streaming=True,
        timeout=_LLM_TIMEOUT_SECONDS,
        max_retries=1,
        http_async_client=httpx.AsyncClient(trust_env=False, timeout=_LLM_TIMEOUT_SECONDS),
    )

