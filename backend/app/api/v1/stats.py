# 统计接口
from fastapi import APIRouter

from app.schemas.v1.stats import StatsResponse
from app.services import stats_service

router = APIRouter(tags=["统计"])


@router.get("/stats", response_model=StatsResponse, summary="数据统计概览")
def get_stats():
    """返回知识图谱、法条、案例等数据统计信息"""
    return stats_service.get_stats()
