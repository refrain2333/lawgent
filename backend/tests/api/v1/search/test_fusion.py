# 融合搜索接口测试 POST /api/v1/search
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestFusionSearchAPI:
    """融合搜索接口 POST /api/v1/search"""

    def test_returns_200(self, client):
        """接口返回200"""
        response = client.post("/api/v1/search", json={"vector": "故意伤害"})
        assert response.status_code == 200

    def test_all_empty_rejected(self, client):
        """所有路均为空时被拒绝（422）"""
        response = client.post("/api/v1/search", json={"count": 3})
        assert response.status_code == 422

    def test_response_top_level_fields(self, client):
        """顶层融合结果字段完整"""
        data = client.post("/api/v1/search", json={"vector": "故意伤害", "count": 3}).json()
        for field in ("query", "articles", "cases", "total_articles", "total_cases", "elapsed_ms", "paths"):
            assert field in data

    def test_paths_has_five_keys(self, client):
        """paths 包含5条路"""
        data = client.post("/api/v1/search", json={"vector": "故意伤害"}).json()
        for key in ("vector", "bm25", "kg", "query2doc", "hyde"):
            assert key in data["paths"]

    def test_each_path_has_articles_and_cases(self, client):
        """每路结果都有 articles 和 cases 字段"""
        data = client.post("/api/v1/search", json={"vector": "故意伤害"}).json()
        for _name, path in data["paths"].items():
            assert "articles" in path and "cases" in path

    def test_count_limits_fusion_results(self, client):
        """融合结果不超过 count"""
        data = client.post("/api/v1/search", json={"vector": "故意伤害", "count": 3}).json()
        assert data["total_articles"] <= 3
        assert data["total_cases"] <= 3

    def test_count_limits_per_path(self, client):
        """每路结果也不超过 count"""
        data = client.post("/api/v1/search", json={
            "vector": "故意伤害", "bm25": "故意伤害", "count": 3
        }).json()
        for _name, path in data["paths"].items():
            assert len(path["articles"]) <= 3
            assert len(path["cases"]) <= 3

    def test_empty_path_returns_empty(self, client):
        """未提供文本的路结果为空"""
        data = client.post("/api/v1/search", json={"vector": "故意伤害"}).json()
        assert data["paths"]["bm25"]["articles"] == []
        assert data["paths"]["kg"]["articles"] == []

    def test_kg_path_no_cases(self, client):
        """kg路不返回案例"""
        data = client.post("/api/v1/search", json={"kg": "故意伤害罪", "count": 5}).json()
        assert data["paths"]["kg"]["cases"] == []

    def test_multi_path_fusion(self, client):
        """多路同时激活时融合结果不为空"""
        data = client.post("/api/v1/search", json={
            "vector": "故意伤害",
            "bm25": "故意伤害",
            "kg": "故意伤害罪",
            "count": 5,
        }).json()
        assert data["total_articles"] > 0 or data["total_cases"] > 0

    def test_query2doc_path(self, client):
        """query2doc路使用拼接文本时有结果"""
        data = client.post("/api/v1/search", json={
            "query2doc": "故意伤害罪 使用器械造成轻伤 刑法第234条",
            "count": 5,
        }).json()
        q2d = data["paths"]["query2doc"]
        assert len(q2d["articles"]) > 0 or len(q2d["cases"]) > 0

    def test_hyde_path(self, client):
        """hyde路使用假设性回答时有结果"""
        data = client.post("/api/v1/search", json={
            "hyde": "依据刑法第234条，故意伤害他人身体，造成轻伤处三年以下有期徒刑",
            "count": 5,
        }).json()
        hyde = data["paths"]["hyde"]
        assert len(hyde["articles"]) > 0 or len(hyde["cases"]) > 0

    def test_all_five_paths(self, client):
        """五路全部激活时融合结果最充分"""
        data = client.post("/api/v1/search", json={
            "vector": "我朋友被人拿刀划伤了",
            "bm25": "故意伤害 刀伤",
            "kg": "故意伤害罪",
            "query2doc": "故意伤害罪 使用器械造成轻伤",
            "hyde": "依据第234条，故意伤害他人身体处三年以下有期徒刑",
            "count": 5,
        }).json()
        assert data["total_articles"] + data["total_cases"] > 0
