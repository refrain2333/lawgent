# 用户服务
import asyncio

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import create_access_token, hash_password, verify_password
from app.models.models import User
from app.schemas.v1.user import LoginRequest, RegisterRequest, TokenResponse, UserUpdateRequest


async def register(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    """用户注册"""
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    hashed = await asyncio.to_thread(hash_password, data.password)
    user = User(
        email=data.email,
        password=hashed,
        nickname=data.nickname,
    )
    db.add(user)
    await db.flush()

    token = create_access_token({"user_id": user.id})
    return TokenResponse(access_token=token)


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    """用户登录"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not await asyncio.to_thread(verify_password, data.password, user.password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误", headers={"WWW-Authenticate": "Bearer"})

    token = create_access_token({"user_id": user.id})
    return TokenResponse(access_token=token)


async def login_form(db: AsyncSession, form_data: OAuth2PasswordRequestForm) -> TokenResponse:
    """OAuth2 表单登录（供 Swagger UI 使用）"""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not await asyncio.to_thread(verify_password, form_data.password, user.password):
        raise HTTPException(status_code=401, detail="邮箱或密码错误", headers={"WWW-Authenticate": "Bearer"})

    token = create_access_token({"user_id": user.id})
    return TokenResponse(access_token=token)


async def update_me(db: AsyncSession, user: User, data: UserUpdateRequest) -> User:
    """更新用户信息"""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.add(user)
    await db.flush()
    return user
