# 搜索接口
from fastapi import APIRouter, Query

from app.schemas.v1.search import SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter(tags=["搜索"])


@router.get("/vector", response_model=SearchResponse, summary="向量检索")
async def vector_search(
    q: str = Query(default="", description="搜索关键词"),
    articles_count: int = Query(default=5, ge=0, le=20, description="返回法条数量"),
    cases_count: int = Query(default=5, ge=0, le=20, description="返回案例数量"),
    ):
    """纯向量语义检索，使用微调 Lawformer 编码查询向量"""
    return await search_service.vector_search_async(q, articles_count, cases_count)


@router.get("/bm25", response_model=SearchResponse, summary="BM25检索")
async def bm25_search(
    q: str = Query(default="", description="搜索关键词"),
    articles_count: int = Query(default=5, ge=0, le=20, description="返回法条数量"),
    cases_count: int = Query(default=5, ge=0, le=20, description="返回案例数量"),
    ):
    """BM25 关键词检索，基于法条标题/章节和案例罪名进行稀疏匹配"""
    return await search_service.bm25_search_async(q, articles_count, cases_count)


@router.get("/kg", response_model=SearchResponse, summary="知识图谱检索")
async def kg_search(
    q: str = Query(default="", description="搜索关键词（含罪名）"),
    articles_count: int = Query(default=5, ge=0, le=20, description="返回法条数量"),
    ):
    """知识图谱检索：AC自动机识别查询中的罪名，返回高置信度关联法条（仅法条，无案例）"""
    return await search_service.kg_search_async(q, articles_count)


@router.post("", response_model=SearchResponse, summary="融合搜索")
async def fusion_search(req: SearchRequest):
    """5路可选并行搜索 + RRF 融合。

    响应的 `paths` 字段包含每路独立结果；顶层 `articles`/`cases` 为最终融合结果，数量与 `count` 一致。
    query2doc/hyde 路依赖 `enhanced` 文本，为空时自动跳过。
    """
    return await search_service.search_async(
        vector=req.vector,
        bm25=req.bm25,
        kg=req.kg,
        query2doc=req.query2doc,
        hyde=req.hyde,
        count=req.count,
    )


