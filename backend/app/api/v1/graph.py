# 知识图谱接口
from fastapi import APIRouter, Query

from app.schemas.v1.graph import (
    GraphRelationsResponse,
    GraphResponse,
    GraphStatsResponse,
    RelationCasesResponse,
)
from app.services import graph_service

router = APIRouter(tags=["知识图谱"])


@router.get("/graph/stats", response_model=GraphStatsResponse, summary="知识图谱统计")
def get_graph_stats():
    """返回知识图谱整体统计数据。"""
    return graph_service.get_graph_stats()


@router.get("/graph/article_ids", summary="有图谱数据的法条编号列表")
def get_article_ids():
    """返回知识图谱中存在关联数据的法条编号列表。"""
    return graph_service.get_article_ids()


@router.get("/graph/relations/{entity}", response_model=GraphRelationsResponse, summary="实体关系图谱")
def get_entity_relations(
    entity: str,
    top_k: int = Query(default=10, ge=1, le=30, description="返回关联节点数量"),
    ):
    """根据罪名或法条返回其 ego network 可视化数据。"""
    return graph_service.get_entity_relations(entity, top_k)


@router.get("/graph/relation_cases/{crime}/{article}", response_model=RelationCasesResponse, summary="罪名-法条关联案例")
def get_relation_cases(
    crime: str,
    article: str,
    limit: int = Query(default=5, ge=1, le=20, description="返回案例数量"),
    ):
    """返回特定罪名与法条关联的具体案例。"""
    return graph_service.get_relation_cases(crime, article, limit)


@router.get("/graph", response_model=GraphResponse, summary="知识图谱数据（全局）")
def get_graph(
    top_crimes: int = Query(default=20, ge=1, le=100, description="返回高频罪名数量"),
    crime: str = Query(default="", description="按罪名过滤，为空则返回 top_crimes 高频罪名"),
    ):
    """返回罪名-法条知识图谱节点与边，用于前端可视化。"""
    return graph_service.get_full_graph(top_crimes, crime)
