# 安全工具
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings

_PASSWORD_HASH_PREFIX = "bcrypt-sha256$"


def _bcrypt_input(password: str) -> bytes:
    """预哈希后编码，避免 bcrypt 的 72 字节输入上限。"""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def _legacy_bcrypt_input(password: str) -> bytes:
    """旧版哈希曾直接截断至 72 字节，登录时保留兼容。"""
    return password.encode("utf-8")[:72]


def needs_password_rehash(hashed_password: str) -> bool:
    """判断是否仍使用旧版 bcrypt 哈希格式。"""
    return not hashed_password.startswith(_PASSWORD_HASH_PREFIX)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证新格式及旧版 bcrypt 密码哈希。"""
    is_current = hashed_password.startswith(_PASSWORD_HASH_PREFIX)
    encoded_hash = hashed_password[len(_PASSWORD_HASH_PREFIX):] if is_current else hashed_password
    password_bytes = _bcrypt_input(plain_password) if is_current else _legacy_bcrypt_input(plain_password)
    try:
        return bcrypt.checkpw(password_bytes, encoded_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def hash_password(password: str) -> str:
    """使用 SHA-256 + Base64 预处理后再生成 bcrypt 哈希。"""
    hashed = bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt(rounds=10)).decode("utf-8")
    return f"{_PASSWORD_HASH_PREFIX}{hashed}"


def create_access_token(data: dict[str, Any]) -> str:
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码 JWT Token，失败返回 None。

    强制要求 Token 携带 exp，避免出现永不过期的凭据。
    （python-jose 的 options={"require": [...]} 不生效，这里手动校验。）
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.JWTError:
        return None
    if "exp" not in payload:
        return None
    return payload
