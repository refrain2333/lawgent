# 向量检索问题排查测试
import logging
import pickle

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logging.disable(logging.CRITICAL)


class TestVectorSearchDebug:
    """排查向量检索问题"""

    def test_article_234_vector_exists(self):
        """验证第234条向量数据存在"""
        with open('../data/vectors/criminal_articles_vectors_finetuned.pkl', 'rb') as f:
            data = pickle.load(f)

        metadata = data['metadata']
        vectors = data['vectors']

        # 找到第234条
        found = False
        for i, meta in enumerate(metadata):
            if meta.get('article_number') == 234:
                found = True
                print(f"第234条索引: {i}")
                print(f"向量维度: {vectors[i].shape}")
                print(f"向量范数: {np.linalg.norm(vectors[i])}")
                break

        assert found, "第234条向量数据不存在"

    def test_query_vector_similarity(self):
        """验证查询向量与第234条的相似度"""
        from app.db.data_loader import get_data_loader
        from app.infrastructure.lawformer import get_embedder

        loader = get_data_loader()
        loader.load_all()
        embedder = get_embedder()

        # 获取查询向量
        query_vec = embedder.encode('故意伤害')
        print(f"查询向量范数: {np.linalg.norm(query_vec)}")

        # 获取向量数据
        vectors = loader.get_vectors('articles')
        metadata = loader.get_metadata('articles')

        # 计算相似度
        sims = cosine_similarity([query_vec], vectors)[0]

        # 找到第234条
        target_idx = None
        for i, meta in enumerate(metadata):
            if meta.get('article_number') == 234:
                target_idx = i
                break

        print(f"第234条索引: {target_idx}")
        print(f"第234条与查询相似度: {sims[target_idx]}")

        # top10
        top_idx = sims.argsort()[::-1][:10]
        print("\n=== Top10 相似度 ===")
        for i in top_idx:
            meta = metadata[i]
            print(f"第{meta.get('article_number')}条: {sims[i]:.4f}")

        # 验证234在top5
        assert 234 in [metadata[i].get('article_number') for i in top_idx[:5]]

    def test_search_service_result(self):
        """验证搜索服务返回结果"""
        import asyncio

        from app.db.data_loader import get_data_loader
        from app.infrastructure.lawformer import get_embedder
        from app.services.search_service import vector_search_async

        loader = get_data_loader()
        loader.load_all()
        get_embedder()

        result = asyncio.run(vector_search_async('故意伤害', articles_count=5, cases_count=0))

        print("\n=== API 返回结果 ===")
        for a in result.articles:
            print(f"第{a.article_number}条: {a.similarity:.4f}")

        # 验证返回结构
        assert len(result.articles) > 0
        assert result.articles[0].article_number is not None
