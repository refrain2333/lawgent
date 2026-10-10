# DeepSeek LLM 客户端（AsyncOpenAI 直调 + LangChain ChatOpenAI 封装）
import logging
from functools import lru_cache
from typing import Optional

import httpx
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional["LLMClient"] = None
_LLM_TIMEOUT_SECONDS = 120.0


class LLMClient:
    """DeepSeek LLM 客户端（OpenAI 兼容接口）"""

    def __init__(self):
        if not settings.LLM_API_KEY.strip():
            logger.warning("LLM_API_KEY 未配置，LLM 功能将不可用")
            self._client = None
        else:
            self._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_API_BASE,
                timeout=_LLM_TIMEOUT_SECONDS,
                max_retries=1,
            )
            logger.info(f"LLM 客户端初始化完成: {settings.LLM_MODEL}")

    @property
    def available(self) -> bool:
        return self._client is not None

    async def generate(self, prompt: str, max_tokens: int = 300, temperature: float = 0.3) -> str:
        """调用 LLM 生成文本（非流式）"""
        if not self._client:
            return ""
        try:
            resp = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = resp.choices[0].message.content if resp.choices else None
            return content.strip() if isinstance(content, str) else ""
        except Exception as e:
            logger.error("LLM 调用失败: %s", type(e).__name__)
            return ""


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


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
