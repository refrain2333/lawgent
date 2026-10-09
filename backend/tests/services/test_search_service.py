# 搜索服务测试
import asyncio

import pytest

from app.db.data_loader import get_data_loader
from app.infrastructure.lawformer import get_embedder
from app.schemas.v1.search import SearchResponse
from app.services.search_service import search_async


@pytest.fixture(scope="module")
def prepared():
    loader = get_data_loader()
    loader.load_all()
    get_embedder().encode("预热")
    return loader


class TestSearchResponse:
    def test_response_structure(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=3, cases_count=3))
        assert isinstance(result, SearchResponse)
        assert result.query == "故意伤害"
        assert result.total_articles == len(result.articles)
        assert result.total_cases == len(result.cases)
        assert result.elapsed_ms > 0

    def test_five_paths_present(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=3, cases_count=3))
        assert set(result.paths.keys()) == {"vector", "bm25", "kg", "query2doc", "hyde"}

    def test_kg_finds_article_234(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=5, cases_count=3))
        kg_article_ids = [a.id for a in result.paths["kg"].articles]
        assert "article_234" in kg_article_ids

    def test_fused_result_contains_article_234(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=5, cases_count=3))
        fused_ids = [a.id for a in result.articles]
        assert "article_234" in fused_ids

    def test_article_has_content(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=3, cases_count=3))
        for a in result.articles:
            if a.article_number == 234:
                assert a.content is not None
                break

    def test_case_has_accusations(self, prepared):
        result = asyncio.run(search_async("故意伤害", articles_count=3, cases_count=3))
        assert all(isinstance(c.accusations, list) for c in result.cases)
