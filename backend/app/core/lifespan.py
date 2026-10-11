# 应用生命周期管理
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logger import init_file_logging, logger

if settings.HF_HOME:
    os.environ["HF_HOME"] = settings.HF_HOME
    os.environ["TRANSFORMERS_CACHE"] = f"{settings.HF_HOME}/transformers"
    os.environ["HF_DATASETS_CACHE"] = f"{settings.HF_HOME}/datasets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_file_logging()
    logger.info("应用正在启动...")

    # 数据与模型的加载失败不应阻断服务启动：
    # 开源仓库不含处理后的数据与模型权重，缺资源时相关检索能力不可用，
    # 但其余接口（会话、鉴权、数据浏览）仍可正常提供。
    try:
        from app.db.data_loader import get_data_loader
        stats = get_data_loader().load_all()
        logger.info(f"数据加载完成: {stats['total_documents']} 条文档，耗时 {stats['elapsed']}s")
    except Exception as e:
        logger.warning(f"数据加载失败，检索相关能力不可用: {e}")

    try:
        from app.infrastructure.lawformer import get_embedder
        vec = get_embedder().encode("法律")
        logger.info(f"Lawformer 预热完成，向量维度: {vec.shape}")
    except Exception as e:
        logger.warning(f"Lawformer 预热失败，向量检索不可用: {e}")

    logger.info(f"启动完成，文档: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    logger.info("应用正在关闭...")
