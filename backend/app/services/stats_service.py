# 统计服务层
from app.db.data_loader import get_data_loader
from app.schemas.v1.stats import StatsResponse


def get_stats() -> StatsResponse:
    loader = get_data_loader()

    top_crimes: list = []
    top_articles: list = []
    total_crimes = 0
    total_articles_kg = 0
    total_relations = 0

    kg = loader.knowledge_graph
    if kg is not None:
        crime_map = getattr(kg, "crime_article_map", None) or (
            kg.get("crime_article_mapping", {}) if isinstance(kg, dict) else {}
        )
        total_crimes = len(crime_map)

        crime_counts = [(c, sum(v.values()) if isinstance(v, dict) else len(v)) for c, v in crime_map.items()]
        crime_counts.sort(key=lambda x: x[1], reverse=True)
        top_crimes = crime_counts[:10]

        art_freq: dict[str, int] = {}
        for arts in crime_map.values():
            if isinstance(arts, dict):
                for art, cnt in arts.items():
                    art_freq[str(art)] = art_freq.get(str(art), 0) + (int(cnt) if isinstance(cnt, (int, float)) else 1)
            elif isinstance(arts, list):
                for art in arts:
                    art_freq[str(art)] = art_freq.get(str(art), 0) + 1
        top_articles = sorted(art_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        total_relations = sum(art_freq.values())
        total_articles_kg = len(art_freq)

    total_cases = 0
    total_articles_vec = 0
    if loader.vectors_loaded:
        cases_meta = loader.get_metadata("cases")
        total_cases = len(cases_meta) if cases_meta else 0
        arts_meta = loader.get_metadata("articles")
        total_articles_vec = len(arts_meta) if arts_meta else 0

    return StatsResponse(
        total_crimes=total_crimes,
        total_articles=total_articles_vec or total_articles_kg,
        total_relations=total_relations,
        total_cases=total_cases,
        top_crimes=top_crimes,
        top_articles=top_articles,
        kg_loaded=loader.kg_loaded,
        vectors_loaded=loader.vectors_loaded,
        )
