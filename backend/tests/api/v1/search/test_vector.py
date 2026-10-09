# 向量检索接口测试
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestVectorSearchAPI:
    """向量检索接口 /api/v1/search/vector"""

    def test_returns_200(self, client):
        """接口返回200"""
        response = client.get("/api/v1/search/vector?q=故意伤害&articles_count=3&cases_count=3")
        assert response.status_code == 200

    def test_response_has_required_fields(self, client):
        """返回包含必要字段"""
        response = client.get("/api/v1/search/vector?q=故意伤害&articles_count=2&cases_count=2")
        data = response.json()

        assert "query" in data
        assert "articles" in data
        assert "cases" in data
        assert "total_articles" in data
        assert "total_cases" in data
        assert "elapsed_ms" in data

    def test_article_234_in_results(self, client):
        """故意伤害查询应返回第234条"""
        response = client.get("/api/v1/search/vector?q=故意伤害&articles_count=5")
        data = response.json()

        article_numbers = [a.get("article_number") for a in data.get("articles", [])]
        assert 234 in article_numbers, f"期望234在结果中，实际: {article_numbers}"

    def test_case_has_accusations(self, client):
        """案例包含指控罪名"""
        response = client.get("/api/v1/search/vector?q=故意伤害&cases_count=3")
        data = response.json()

        cases = data.get("cases", [])
        assert len(cases) > 0
        for c in cases:
            assert c.get("accusations") is not None
            assert isinstance(c.get("accusations"), list)

    def test_case_has_case_id_and_articles(self, client):
        """案例包含 case_id 和相关法条"""
        response = client.get("/api/v1/search/vector?q=故意伤害&cases_count=2")
        data = response.json()

        for c in data.get("cases", []):
            assert c.get("case_id") is not None
            assert c.get("relevant_articles") is not None

    def test_case_has_sentence_and_fine(self, client):
        """案例包含刑期和罚金"""
        response = client.get("/api/v1/search/vector?q=故意伤害&cases_count=3")
        data = response.json()

        cases = data.get("cases", [])
        has_info = any(
            c.get("sentence_months") is not None or c.get("fine_amount") is not None
            for c in cases
        )
        assert has_info

    def test_empty_query_returns_empty(self, client):
        """空查询返回空结果"""
        response = client.get("/api/v1/search/vector?q=&articles_count=2&cases_count=2")
        assert response.status_code == 200
        assert response.json().get("total_articles") == 0
