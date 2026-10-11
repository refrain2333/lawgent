# 数据加载测试
import pytest

from app.db.data_loader import get_data_loader


@pytest.fixture(scope="module")
def loader():
    dl = get_data_loader()
    dl.load_all()
    if not dl.vectors_loaded:
        pytest.skip("本地缺少处理后的数据文件（data/processed/），跳过数据加载测试。")
    return dl


class TestVectors:
    def test_articles_loaded(self, loader):
        assert loader.vectors_loaded
        vecs = loader.get_vectors("articles")
        assert vecs is not None
        assert vecs.shape == (416, 768)

    def test_cases_loaded(self, loader):
        vecs = loader.get_vectors("cases")
        assert vecs is not None
        assert vecs.shape[1] == 768
        assert vecs.shape[0] > 0

    def test_finetuned_vectors(self, loader):
        """确认使用的是微调向量"""
        import pickle
        from pathlib import Path
        fpath = Path(__file__).parent.parent.parent.parent / "data/vectors/criminal_articles_vectors.pkl"
        with open(fpath, "rb") as f:
            data = pickle.load(f)
        assert data.get("model_info", {}).get("fine_tuned") is True


class TestBM25:
    def test_bm25_built(self, loader):
        assert loader.bm25_built

    def test_bm25_search(self, loader):
        results = loader.bm25_search("故意伤害", top_k=5)
        assert len(results) > 0
        assert all("id" in r and "score" in r for r in results)

    def test_bm25_returns_cases(self, loader):
        results = loader.bm25_search("故意伤害", top_k=10)
        case_results = [r for r in results if r["id"].startswith("case_")]
        assert len(case_results) > 0


class TestKnowledgeGraph:
    def test_kg_loaded(self, loader):
        assert loader.kg_loaded
        assert loader.knowledge_graph is not None

    def test_kg_search_returns_articles(self, loader):
        articles = loader.kg_search("故意伤害", top_k=5)
        assert len(articles) > 0
        assert "234" in articles  # 故意伤害对应第234条


class TestContentLoad:
    def test_article_content(self, loader):
        content = loader.get_article_content("234")
        assert content is not None
        assert len(content) > 10

    def test_case_content(self, loader):
        meta = loader.get_metadata("cases")
        assert meta is not None
        case_id = str(meta[0].get("case_id", ""))
        content = loader.get_case_content(case_id)
        assert content is not None
