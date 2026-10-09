# FastAPI 应用入口
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.lifespan import lifespan


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="刑事法律服务助手",
        version="1.0.0",
        description="基于智能体的刑事法律服务助手",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
        )

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        )

    # 注册路由
    app.include_router(router)

    return app


if __name__ == "__main__":
    uvicorn.run(
        "main:create_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=["app"],
        reload_includes=["app/**/*.py", "main.py"],
        reload_excludes=["logs/**/*", "**/*.log", ".pytest_cache/**/*", "data/**/*"],
        log_config=None,
    )
