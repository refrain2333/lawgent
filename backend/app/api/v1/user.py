# 认证接口
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models.models import User
from app.schemas.v1.user import LoginRequest, RegisterRequest, TokenResponse, UserResponse, UserUpdateRequest
from app.services import user_service

router = APIRouter(tags=["用户"])


@router.post("/register", response_model=TokenResponse, summary="用户注册")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户并返回 Token"""
    return await user_service.register(db, data)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """验证邮箱密码并返回 Token"""
    return await user_service.login(db, data)


@router.post("/access-token", response_model=TokenResponse, summary="OAuth2 登录")
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    ):
    """OAuth2 标准登录接口（专为 Swagger UI 设计），username 填邮箱"""
    return await user_service.login_form(db, form_data)


@router.get("/me", response_model=UserResponse, summary="获取当前用户")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@router.put("/me", response_model=UserResponse, summary="更新用户信息")
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ):
    """更新当前用户的昵称或头像"""
    return await user_service.update_me(db, current_user, data)
