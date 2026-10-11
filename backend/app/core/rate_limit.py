# 轻量级内存限流
#
# 目的：防止单个用户在短时间内大量创建会话或发送消息，
# 消耗部署者配置的 LLM 额度（前端的冷却只存在于浏览器，容易被绕过）。
#
# 说明：使用进程内滑动窗口，单实例部署足够；
# 若将来多实例部署，应替换为 Redis 等共享存储。
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """在 window_seconds 内最多允许 limit 次命中，超出抛 429。

    key 用于区分限流维度（如 f"msg:{user_id}"）。
    """
    if limit <= 0:
        return
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        bucket = _hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"操作过于频繁，请 {retry_after} 秒后重试",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    """清空计数（供测试使用）。"""
    with _lock:
        _hits.clear()

