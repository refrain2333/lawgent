# 数据浏览接口
from fastapi import APIRouter, Query

from app.schemas.v1.data import ArticleListResponse, CaseListResponse
from app.services import data_service

router = APIRouter(tags=["数据浏览"])


@router.get("/data/articles", response_model=ArticleListResponse, summary="法条列表")
def list_articles(
    q: str = Query(default="", description="搜索关键词"),
    chapter: str = Query(default="", description="章节筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    article_number: str = Query(default="", pattern=r"^\d*$", description="精确法条编号，使用裸数字，如264"),
    ):
    """返回法条分页列表，支持关键词搜索和章节筛选。"""
    return data_service.list_articles(q, chapter, page, page_size, article_number)


@router.get("/data/cases", response_model=CaseListResponse, summary="案例列表")
def list_cases(
    q: str = Query(default="", description="搜索罪名或案件事实"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    ):
    """返回案例分页列表，支持罪名/事实关键词搜索。"""
    return data_service.list_cases(q, page, page_size)
