# 系统接口
from fastapi import APIRouter, Request

from app.schemas.system import SystemInfo

router = APIRouter(tags=["系统"])


@router.get("/", response_model=SystemInfo, summary="系统信息")
def root(request: Request):
    """返回系统基本信息"""
    app = request.app
    return {
        "name": app.title,
        "version": app.version,
        "description": app.description,
        "status": "running"
    }
