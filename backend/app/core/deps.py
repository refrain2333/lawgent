# 依赖注入
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user/access-token")


async def _get_authenticated_user(token: str, db: AsyncSession) -> User:
    """校验 Token 中的用户标识，并确认账号仍存在。"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id = payload.get("user_id")
    # bool 是 int 的子类；不要接受布尔值、字符串、浮点数或超出数据库范围的 ID。
    if type(user_id) is not int or not 0 < user_id <= 2_147_483_647:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    ) -> User:
    """从 Authorization header Token 获取当前用户。"""
    return await _get_authenticated_user(token, db)


async def get_user_id(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    ) -> int:
    """从 Authorization header 解析 user_id。

    只接受标准的 Bearer Token，不再支持 query 参数传 Token，
    避免凭据被写入访问日志或代理日志。
    """
    user = await _get_authenticated_user(token, db)
    return user.id

