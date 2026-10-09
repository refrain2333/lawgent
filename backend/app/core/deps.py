# 依赖注入
from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user/access-token")


def _extract_token(request: Request, token: str | None) -> str:
    """优先从 Authorization header 取 Token，其次回退到 query 参数。

    query 回退仅为兼容浏览器 SSE（fetch 流）场景，header 是推荐方式。
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if token:
        return token
    raise HTTPException(
        status_code=401,
        detail="缺少 Token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    ) -> User:
    """从 Authorization header Token 获取当前用户"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def get_user_id(
    request: Request,
    token: str | None = Query(None, description="JWT Token（可选，兼容 SSE；推荐使用 Authorization header）"),
    ) -> int:
    """从请求中解析 user_id。

    优先读取 Authorization: Bearer <token>，其次读取 query 参数 token。
    不再接受任何硬编码的调试 Token。
    """
    raw = _extract_token(request, token)
    payload = decode_access_token(raw)
    if not payload or not payload.get("user_id"):
        raise HTTPException(status_code=401, detail="Token 无效")
    return int(payload["user_id"])

