# 数据库配置（异步）
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 异步引擎
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    pool_size=5,
    max_overflow=10,
    )

# 异步会话工厂
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（含事务管理）"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
