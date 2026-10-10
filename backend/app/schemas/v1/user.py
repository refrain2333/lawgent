# 认证相关 Schema
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr = Field(max_length=255, description="用户邮箱", examples=["user@example.com"])
    password: str = Field(min_length=6, description="密码(至少6位)", examples=["password123"])
    nickname: str | None = Field(default=None, max_length=100, description="用户昵称", examples=["张三"])


class LoginRequest(BaseModel):
    """登录请求"""
    email: EmailStr = Field(description="用户邮箱", examples=["user@example.com"])
    password: str = Field(description="密码", examples=["password123"])


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(description="JWT Token", examples=["eyJhbGciOiJIUzI1NiJ9..."])
    token_type: str = Field(default="bearer", description="Token 类型", examples=["bearer"])


class UserUpdateRequest(BaseModel):
    """更新用户信息请求"""
    nickname: str | None = Field(default=None, max_length=100, description="用户昵称", examples=["张三"])
    avatar: str | None = Field(default=None, max_length=500, description="头像URL", examples=["https://example.com/avatar.png"])


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int = Field(description="用户ID", examples=[1])
    email: str = Field(description="用户邮箱", examples=["user@example.com"])
    nickname: str | None = Field(default=None, description="用户昵称", examples=["张三"])
    avatar: str | None = Field(default=None, description="头像URL", examples=["https://example.com/avatar.png"])
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
