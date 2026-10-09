# 知识图谱检索接口测试
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestKGSearchAPI:
    """知识图谱检索接口 /api/v1/search/kg"""

    def test_returns_200(self, client):
        """接口返回200"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=3")
        assert response.status_code == 200

    def test_response_has_required_fields(self, client):
        """返回包含必要字段"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=2")
        data = response.json()

        assert "query" in data
        assert "articles" in data
        assert "cases" in data
        assert "total_articles" in data
        assert "total_cases" in data
        assert "elapsed_ms" in data

    def test_no_cases_returned(self, client):
        """KG检索只返回法条，不返回案例"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=5")
        data = response.json()

        assert data.get("cases") == [], "KG检索不应返回案例"
        assert data.get("total_cases") == 0

    def test_crime_name_matches_articles(self, client):
        """含罪名的查询应返回关联法条"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=5")
        data = response.json()

        articles = data.get("articles", [])
        assert len(articles) > 0, "故意伤害罪应匹配到关联法条"

    def test_article_234_matched_by_crime(self, client):
        """故意伤害罪应关联到第234条"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=10")
        data = response.json()

        article_numbers = [a.get("article_number") for a in data.get("articles", [])]
        assert 234 in article_numbers, f"期望234在KG结果中，实际: {article_numbers}"

    def test_similarity_normalized(self, client):
        """归一化评分应在 (0, 1] 之间"""
        response = client.get("/api/v1/search/kg?q=故意伤害罪&articles_count=5")
        data = response.json()

        articles = data.get("articles", [])
        for art in articles:
            score = art.get("similarity", -1)
            assert 0 < score <= 1.0, f"归一化评分应在(0,1]，实际: {score}"

    def test_suffix_stem_matching(self, client):
        """查询含'故意伤害'（不含'罪'后缀）也应命中"""
        response = client.get("/api/v1/search/kg?q=故意伤害&articles_count=5")
        data = response.json()

        articles = data.get("articles", [])
        assert len(articles) > 0, "去掉'罪'后缀仍应命中"

    def test_empty_query_returns_empty(self, client):
        """空查询返回空结果"""
        response = client.get("/api/v1/search/kg?q=")
        assert response.status_code == 200
        assert response.json().get("total_articles") == 0
        assert response.json().get("total_cases") == 0

    def test_unrelated_query_returns_empty(self, client):
        """无关查询（无罪名）应返回空"""
        response = client.get("/api/v1/search/kg?q=今天天气不错")
        data = response.json()

        assert data.get("total_articles") == 0, "无罪名的查询不应返回结果"
