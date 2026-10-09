# 配置文件
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    """应用配置"""
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # 服务配置
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 5006

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lawgent"

    # JWT 配置
    JWT_SECRET: str = "lawgent-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # 数据路径配置
    DATA_VECTORS_PATH: str = "data/vectors"
    DATA_CRIMINAL_PATH: str = "data/criminal"
    DATA_KG_PATH: str = "data/knowledge_graph"
    ARTICLES_VECTORS_FILE: str = "criminal_articles_vectors_finetuned.pkl"
    CASES_VECTORS_FILE: str = "criminal_cases_vectors_finetuned.pkl"

    # LLM 配置 (DeepSeek)
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LOCAL_MODEL_PATH: str = ""
    FINETUNED_MODEL_PATH: str = ""
    MODEL_OFFLINE_MODE: bool = True
    HF_HOME: str = ""
    EMBEDDING_DIM: int = 768
    CACHE_SIZE_LIMIT: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
