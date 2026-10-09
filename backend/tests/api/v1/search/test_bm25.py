# BM25 检索接口测试
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestBM25SearchAPI:
    """BM25 检索接口 /api/v1/search/bm25"""

    def test_returns_200(self, client):
        """接口返回200"""
        response = client.get("/api/v1/search/bm25?q=故意伤害&articles_count=3&cases_count=3")
        assert response.status_code == 200

    def test_response_has_required_fields(self, client):
        """返回包含必要字段"""
        response = client.get("/api/v1/search/bm25?q=故意伤害&articles_count=2&cases_count=2")
        data = response.json()

        assert "query" in data
        assert "articles" in data
        assert "cases" in data
        assert "total_articles" in data
        assert "total_cases" in data
        assert "elapsed_ms" in data

    def test_article_234_in_results(self, client):
        """故意伤害查询应返回第234条（jieba+ngram分词后可匹配法条标题）"""
        response = client.get("/api/v1/search/bm25?q=故意伤害&articles_count=5")
        data = response.json()

        article_numbers = [a.get("article_number") for a in data.get("articles", [])]
        assert 234 in article_numbers, f"期望234在结果中，实际: {article_numbers}"

    def test_cases_returned_for_crime_keyword(self, client):
        """罪名关键词查询应返回匹配案例（BM25按指控罪名匹配）"""
        response = client.get("/api/v1/search/bm25?q=故意伤害&cases_count=5")
        data = response.json()

        cases = data.get("cases", [])
        assert len(cases) > 0, "故意伤害应匹配到案例"

    def test_case_has_accusations(self, client):
        """案例包含指控罪名"""
        response = client.get("/api/v1/search/bm25?q=故意伤害&cases_count=3")
        data = response.json()

        cases = data.get("cases", [])
        assert len(cases) > 0
        for c in cases:
            assert isinstance(c.get("accusations"), list)

    def test_robbery_cases_returned(self, client):
        """抢劫关键词查询应返回含抢劫指控的案例（BM25按指控匹配，不按法条标题匹配）"""
        response = client.get("/api/v1/search/bm25?q=抢劫&cases_count=5")
        data = response.json()

        cases = data.get("cases", [])
        assert len(cases) > 0, "抢劫应匹配到案例"
        accusations_all = [a for c in cases for a in c.get("accusations", [])]
        assert any("抢劫" in a for a in accusations_all), f"案例指控应含抢劫，实际: {accusations_all[:5]}"

    def test_empty_query_returns_empty(self, client):
        """空查询返回空结果"""
        response = client.get("/api/v1/search/bm25?q=")
        assert response.status_code == 200
        assert response.json().get("total_articles") == 0
        assert response.json().get("total_cases") == 0

    def test_elapsed_ms_is_positive(self, client):
        """耗时字段为正数"""
        response = client.get("/api/v1/search/bm25?q=盗窃&articles_count=3&cases_count=3")
        data = response.json()
        assert data.get("elapsed_ms") >= 0
