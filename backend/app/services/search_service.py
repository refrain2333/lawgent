# 搜索服务 - 5路并行搜索 + RRF融合，返回各路独立结果和综合结果
import asyncio
import logging
import time
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.db.data_loader import get_data_loader
from app.schemas.v1.search import ArticleResult, CaseResult, SearchPathResult, SearchResponse

logger = logging.getLogger(__name__)

RRF_K = 60


# ------------------------------------------------------------------ #
# 工具函数
# ------------------------------------------------------------------ #

def _encode(text: str) -> Optional[np.ndarray]:
    """用 Lawformer 将文本编码为 768 维向量"""
    try:
        from app.infrastructure.lawformer import get_embedder
        vec = get_embedder().encode(text, show_progress_bar=False)
        return vec[0] if vec.ndim == 2 else vec
    except Exception as e:
        logger.error(f"向量编码失败: {e}")
        return None


def _empty_response(query: str) -> SearchResponse:
    """返回空搜索结果（统一构造，避免重复）"""
    return SearchResponse(query=query, articles=[], cases=[], total_articles=0, total_cases=0, elapsed_ms=0)


def _build_meta_index(dtype: str) -> dict[str, dict]:
    """将元数据列表转为 {doc_id: meta} 字典，便于 O(1) 查询"""
    loader = get_data_loader()
    prefix = "article_" if dtype == "articles" else "case_"
    return {
        f"{prefix}{meta.get('article_number') or meta.get('case_id') or meta.get('id')}": meta
        for meta in (loader.get_metadata(dtype) or [])
        if meta.get("article_number") or meta.get("case_id") or meta.get("id")
        }


def _build_article(doc_id: str, score: float, meta_index: dict) -> Optional[ArticleResult]:
    """从元数据和原始内容组装单条法条结果"""
    meta = meta_index.get(doc_id)
    if not meta:
        return None
    loader = get_data_loader()
    article_id = str(meta.get("article_number") or meta.get("id", ""))
    return ArticleResult(
        id=doc_id,
        article_number=meta.get("article_number"),
        title=meta.get("title") or f"第{article_id}条",
        chapter=meta.get("chapter"),
        content=loader.get_article_content(article_id),
        similarity=round(score, 4),
        )


def _build_case(doc_id: str, score: float, meta_index: dict) -> Optional[CaseResult]:
    """从元数据和原始内容组装单条案例结果，含罪名/法条/刑期字段规范化"""
    meta = meta_index.get(doc_id)
    if not meta:
        return None
    loader = get_data_loader()
    case_id = str(meta.get("case_id") or meta.get("id", ""))
    acc = meta.get("accusations", [])
    if isinstance(acc, str):
        acc = [a.strip() for a in acc.split(",") if a.strip()]
    arts = meta.get("relevant_articles", [])
    if isinstance(arts, str):
        try:
            arts = [int(x.strip()) for x in arts.split(",") if x.strip().isdigit()]
        except Exception:
            arts = []
    extra = loader.get_case_extra(case_id)
    return CaseResult(
        id=doc_id,
        case_id=case_id,
        accusations=acc or [],
        relevant_articles=arts or [],
        criminals=extra.get("criminals", []),
        sentence_months=meta["sentence_months"] if meta.get("sentence_months") is not None else extra.get("imprisonment_months"),
        fine_amount=meta["fine_amount"] if meta.get("fine_amount") is not None else extra.get("fine_amount"),
        death_penalty=extra.get("death_penalty", meta.get("death_penalty", False)),
        life_imprisonment=extra.get("life_imprisonment", meta.get("life_imprisonment", False)),
        fact=loader.get_case_content(case_id),
        similarity=round(score, 4),
        )



# ------------------------------------------------------------------ #
# 各路搜索（返回 [(doc_id, score), ...]）
# ------------------------------------------------------------------ #

def _vector_search_raw(query_vec: Optional[np.ndarray], dtype: str, top_k: int) -> list[tuple[str, float]]:
    """向量检索：余弦相似度取 top_k，返回 (doc_id, score) 列表"""
    if top_k <= 0:
        return []
    loader = get_data_loader()
    vectors = loader.get_vectors(dtype)
    metadata = loader.get_metadata(dtype)
    if vectors is None or metadata is None or query_vec is None:
        return []
    sims = cosine_similarity(query_vec.reshape(1, -1), vectors)[0]
    top_idx = sims.argsort()[-top_k:][::-1]
    prefix = "article_" if dtype == "articles" else "case_"
    return [
        (f"{prefix}{metadata[i].get('article_number') or metadata[i].get('case_id') or metadata[i].get('id')}", float(sims[i]))
        for i in top_idx if sims[i] > 0
        ]


def _bm25_search_raw(query: str, dtype: str, top_k: int) -> list[tuple[str, float]]:
    """BM25 关键词检索，按 dtype 独立取 top_k，避免法条/案例互相竞争排名"""
    if top_k <= 0:
        return []
    loader = get_data_loader()
    return [(r["id"], r["score"]) for r in loader.bm25_search(query, top_k, dtype=dtype)]


def _kg_search_raw(query: str, top_k: int) -> list[tuple[str, float]]:
    """知识图谱检索：AC自动机匹配罪名，返回关联法条及归一化评分（仅法条，无案例）"""
    if top_k <= 0:
        return []
    loader = get_data_loader()
    return [(f"article_{art_num}", score) for art_num, score in loader.kg_search(query, top_k)]




# ------------------------------------------------------------------ #
# RRF 融合
# ------------------------------------------------------------------ #

def _rrf_fuse(ranked_lists: list[list[tuple[str, float]]], top_k: int) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion：多路结果按排名倒数求和后取 top_k"""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]


# ------------------------------------------------------------------ #
# 各路独立搜索入口
# ------------------------------------------------------------------ #

async def vector_search_async(query: str, articles_count: int = 5, cases_count: int = 5) -> SearchResponse:
    """纯向量语义检索"""
    t0 = time.time()
    loader = get_data_loader()

    if not query or not query.strip():
        return _empty_response(query)
    if not loader.vectors_loaded:
        return _empty_response(query)

    query_vec = await asyncio.to_thread(_encode, query)
    if query_vec is None:
        return _empty_response(query)

    art_raw, case_raw = await asyncio.gather(
        asyncio.to_thread(_vector_search_raw, query_vec, "articles", articles_count),
        asyncio.to_thread(_vector_search_raw, query_vec, "cases", cases_count),
    )

    art_meta = _build_meta_index("articles")
    case_meta = _build_meta_index("cases")

    articles = [r for r in (_build_article(d, s, art_meta) for d, s in art_raw) if r]
    cases = [r for r in (_build_case(d, s, case_meta) for d, s in case_raw) if r]

    elapsed = round((time.time() - t0) * 1000, 2)
    logger.info(f"向量检索完成: query_len={len(query)} -> {len(articles)} 法条, {len(cases)} 案例, {elapsed}ms")

    return SearchResponse(
        query=query,
        articles=articles,
        cases=cases,
        total_articles=len(articles),
        total_cases=len(cases),
        elapsed_ms=elapsed,
        )


async def kg_search_async(query: str, articles_count: int = 5) -> SearchResponse:
    """知识图谱检索：AC自动机识别查询中的罪名，返回关联法条（归一化频次评分，无案例）"""
    t0 = time.time()
    loader = get_data_loader()

    if not query or not query.strip():
        return _empty_response(query)
    if not loader.kg_loaded:
        return _empty_response(query)

    art_raw = await asyncio.to_thread(_kg_search_raw, query, articles_count)
    art_meta = _build_meta_index("articles")
    articles = [r for r in (_build_article(d, s, art_meta) for d, s in art_raw) if r]

    elapsed = round((time.time() - t0) * 1000, 2)
    logger.info(f"KG检索完成: query_len={len(query)} -> {len(articles)} 法条, {elapsed}ms")

    return SearchResponse(
        query=query,
        articles=articles,
        cases=[],
        total_articles=len(articles),
        total_cases=0,
        elapsed_ms=elapsed,
        )


async def bm25_search_async(query: str, articles_count: int = 5, cases_count: int = 5) -> SearchResponse:
    """BM25 关键词检索，基于元数据文本匹配，无需向量编码"""
    t0 = time.time()
    loader = get_data_loader()

    if not query or not query.strip():
        return _empty_response(query)
    if not loader.bm25_built:
        return _empty_response(query)

    art_raw, case_raw = await asyncio.gather(
        asyncio.to_thread(_bm25_search_raw, query, "articles", articles_count),
        asyncio.to_thread(_bm25_search_raw, query, "cases", cases_count),
    )

    # BM25 原始分无上界，归一化到 [0,1]
    def _normalize(raw: list[tuple[str, float]]) -> list[tuple[str, float]]:
        if not raw:
            return raw
        max_s = max(s for _, s in raw)
        return [(d, s / max_s) for d, s in raw] if max_s > 0 else raw

    art_raw = _normalize(art_raw)
    case_raw = _normalize(case_raw)

    art_meta = _build_meta_index("articles")
    case_meta = _build_meta_index("cases")

    articles = [r for r in (_build_article(d, s, art_meta) for d, s in art_raw) if r]
    cases = [r for r in (_build_case(d, s, case_meta) for d, s in case_raw) if r]

    elapsed = round((time.time() - t0) * 1000, 2)
    logger.info(f"BM25检索完成: query_len={len(query)} -> {len(articles)} 法条, {len(cases)} 案例, {elapsed}ms")

    return SearchResponse(
        query=query,
        articles=articles,
        cases=cases,
        total_articles=len(articles),
        total_cases=len(cases),
        elapsed_ms=elapsed,
        )


# ------------------------------------------------------------------ #
# 多路并行搜索入口（含 RRF 融合）
# ------------------------------------------------------------------ #

async def search_async(
    vector: str = "",
    bm25: str = "",
    kg: str = "",
    query2doc: str = "",
    hyde: str = "",
    count: int = 5,
) -> SearchResponse:
    """5路可选并行搜索 + RRF 融合，每路各自使用独立查询文本，空字符串表示跳过该路。

    响应包含各路独立结果（paths）和最终融合结果（articles/cases）。
    """
    t0 = time.time()
    main_query = vector or bm25 or kg or query2doc or hyde
    top_k = count * 3

    async def _nil() -> list:
        return []

    async def _encode_async(text: str) -> Optional[np.ndarray]:
        """在线程池中执行向量编码，避免阻塞事件循环"""
        return await asyncio.to_thread(_encode, text) if text else None

    # 三路向量编码并行执行（PyTorch 计算释放 GIL，多线程有效）
    vec_enc, q2d_enc, hyde_enc = await asyncio.gather(
        _encode_async(vector),
        _encode_async(query2doc),
        _encode_async(hyde),
    )

    keys = ["vec_art", "vec_case", "bm25_art", "bm25_case", "kg_art", "q2d_art", "q2d_case", "hyde_art", "hyde_case"]
    coros = [
        asyncio.to_thread(_vector_search_raw, vec_enc,  "articles", top_k) if vector    else _nil(),
        asyncio.to_thread(_vector_search_raw, vec_enc,  "cases",    top_k) if vector    else _nil(),
        asyncio.to_thread(_bm25_search_raw,   bm25, "articles", top_k)     if bm25      else _nil(),
        asyncio.to_thread(_bm25_search_raw,   bm25, "cases",    top_k)     if bm25      else _nil(),
        asyncio.to_thread(_kg_search_raw,     kg, top_k)                   if kg        else _nil(),
        asyncio.to_thread(_vector_search_raw, q2d_enc,  "articles", top_k) if query2doc else _nil(),
        asyncio.to_thread(_vector_search_raw, q2d_enc,  "cases",    top_k) if query2doc else _nil(),
        asyncio.to_thread(_vector_search_raw, hyde_enc, "articles", top_k) if hyde      else _nil(),
        asyncio.to_thread(_vector_search_raw, hyde_enc, "cases",    top_k) if hyde      else _nil(),
    ]
    res = dict(zip(keys, await asyncio.gather(*coros)))

    art_meta  = _build_meta_index("articles")
    case_meta = _build_meta_index("cases")

    def _to_arts(raw):
        return [r for r in (_build_article(d, s, art_meta) for d, s in raw) if r][:count]

    def _to_cases(raw):
        return [r for r in (_build_case(d, s, case_meta) for d, s in raw) if r][:count]

    paths: dict[str, SearchPathResult] = {
        "vector":    SearchPathResult(articles=_to_arts(res["vec_art"]),  cases=_to_cases(res["vec_case"])),
        "bm25":      SearchPathResult(articles=_to_arts(res["bm25_art"]), cases=_to_cases(res["bm25_case"])),
        "kg":        SearchPathResult(articles=_to_arts(res["kg_art"]),   cases=[]),
        "query2doc": SearchPathResult(articles=_to_arts(res["q2d_art"]),  cases=_to_cases(res["q2d_case"])),
        "hyde":      SearchPathResult(articles=_to_arts(res["hyde_art"]), cases=_to_cases(res["hyde_case"])),
    }

    art_raws  = [r for r in [res["vec_art"],  res["bm25_art"],  res["kg_art"], res["q2d_art"],  res["hyde_art"]]  if r]
    case_raws = [r for r in [res["vec_case"], res["bm25_case"],               res["q2d_case"], res["hyde_case"]] if r]

    def _to_arts_fused(rrf_result):
        return [r for r in (
            _build_article(d, s, art_meta)
            for d, s in rrf_result
        ) if r][:count]

    def _to_cases_fused(rrf_result):
        return [r for r in (
            _build_case(d, s, case_meta)
            for d, s in rrf_result
        ) if r][:count]

    articles = _to_arts_fused(_rrf_fuse(art_raws,  count))
    cases    = _to_cases_fused(_rrf_fuse(case_raws, count))

    active = sum(bool(t) for t in [vector, bm25, kg, query2doc, hyde])
    elapsed = round((time.time() - t0) * 1000, 2)
    logger.info(f"融合检索({active}路)完成: query_len={len(main_query)} -> {len(articles)} 法条, {len(cases)} 案例, {elapsed}ms")

    return SearchResponse(
        query=main_query,
        articles=articles,
        cases=cases,
        total_articles=len(articles),
        total_cases=len(cases),
        elapsed_ms=elapsed,
        paths=paths,
    )
