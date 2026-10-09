# 安全工具
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    """生成密码哈希（bcrypt 限制 72 字节，超出截断）"""
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        encoded = encoded[:72]
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=10)).decode("utf-8")


def create_access_token(data: dict[str, Any]) -> str:
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码 JWT Token，失败返回 None"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.JWTError:
        return None
