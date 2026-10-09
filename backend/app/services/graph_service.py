# 知识图谱服务层
import re

from fastapi import HTTPException

from app.db.data_loader import get_data_loader
from app.schemas.v1.graph import (
    CaseItem,
    GraphEdge,
    GraphNode,
    GraphRelationsResponse,
    GraphResponse,
    GraphStatsResponse,
    RelationCasesResponse,
)


def _get_crime_map() -> dict:
    loader = get_data_loader()
    kg = loader.knowledge_graph
    if kg is None:
        return {}
    return getattr(kg, "crime_article_map", None) or (
        kg.get("crime_article_mapping", {}) if isinstance(kg, dict) else {}
    )


def _get_article_map() -> dict:
    loader = get_data_loader()
    kg = loader.knowledge_graph
    if kg is None:
        return {}
    return getattr(kg, "article_crime_map", None) or (
        kg.get("article_crime_mapping", {}) if isinstance(kg, dict) else {}
    )


def _normalize_crime(crime: str) -> str:
    return crime.strip().replace("罪", "").replace("犯罪", "")


def _normalize_article(article: str) -> str:
    m = re.search(r"(\d+)", str(article))
    return m.group(1) if m else ""


def get_graph_stats() -> GraphStatsResponse:
    crime_map = _get_crime_map()
    article_map = _get_article_map()
    total_relations = sum(
        sum(v.values()) if isinstance(v, dict) else len(v)
        for v in crime_map.values()
    )
    return GraphStatsResponse(
        total_crimes=len(crime_map),
        total_articles=len(article_map),
        total_relations=total_relations,
        )


def get_article_ids() -> dict:
    article_map = _get_article_map()
    return {"ids": [int(k) for k in article_map.keys() if k.isdigit()]}


def get_entity_relations(entity: str, top_k: int) -> GraphRelationsResponse:
    crime_map = _get_crime_map()
    article_map = _get_article_map()

    if not crime_map:
        raise HTTPException(status_code=503, detail="知识图谱未加载")

    crime_normalized = _normalize_crime(entity)
    article_normalized = _normalize_article(entity)

    if crime_normalized and crime_normalized in crime_map:
        entity_type = "crime"
        articles = crime_map[crime_normalized]
        art_map = articles if isinstance(articles, dict) else {str(a): 1 for a in articles}
        total_cases = sum(art_map.values()) or 1
        sorted_arts = sorted(art_map.items(), key=lambda x: x[1], reverse=True)[:top_k]

        center = GraphNode(
            id=f"crime_{crime_normalized}", label=f"{crime_normalized}罪",
            type="center", weight=total_cases, confidence=1.0,
            )
        nodes = [center]
        edges = []
        for art_num, cnt in sorted_arts:
            confidence = round(cnt / total_cases, 3)
            nodes.append(GraphNode(
                id=f"article_{art_num}", label=f"第{art_num}条",
                type="article", weight=cnt, confidence=confidence,
                ))
            edges.append(GraphEdge(
                source=center.id, target=f"article_{art_num}",
                weight=cnt, label=f"{cnt}案例",
                ))

    elif article_normalized and article_normalized in article_map:
        entity_type = "article"
        crimes = article_map[article_normalized]
        crime_cnt_map = crimes if isinstance(crimes, dict) else {str(c): 1 for c in crimes}
        total_cases = sum(crime_cnt_map.values()) or 1
        sorted_crimes = sorted(crime_cnt_map.items(), key=lambda x: x[1], reverse=True)[:top_k]

        center = GraphNode(
            id=f"article_{article_normalized}", label=f"第{article_normalized}条",
            type="center", weight=total_cases, confidence=1.0,
            )
        nodes = [center]
        edges = []
        for crime_name, cnt in sorted_crimes:
            confidence = round(cnt / total_cases, 3)
            nodes.append(GraphNode(
                id=f"crime_{crime_name}", label=f"{crime_name}罪",
                type="crime", weight=cnt, confidence=confidence,
                ))
            edges.append(GraphEdge(
                source=center.id, target=f"crime_{crime_name}",
                weight=cnt, label=f"{cnt}案例",
                ))

    else:
        raise HTTPException(status_code=404, detail=f"未找到实体：{entity}")

    return GraphRelationsResponse(
        center_node=center, nodes=nodes, edges=edges, entity_type=entity_type,
        )


def get_relation_cases(crime: str, article: str, limit: int) -> RelationCasesResponse:
    loader = get_data_loader()
    crime_normalized = _normalize_crime(crime)
    article_normalized = _normalize_article(article)

    cases_data = loader.original_data.get("cases", [])
    matching: list[CaseItem] = []

    for case in cases_data:
        if len(matching) >= limit:
            break
        try:
            if isinstance(case, dict):
                accusations = case.get("accusations", [])
                articles = case.get("relevant_articles", [])
                fact = case.get("fact", "")
                case_id = str(case.get("case_id", ""))
                si = case.get("sentence_info", {}) or {}
                si.get("imprisonment_months") if isinstance(si, dict) else None
                si.get("fine_amount") if isinstance(si, dict) else None
                bool(si.get("death_penalty", False)) if isinstance(si, dict) else False
                bool(si.get("life_imprisonment", False)) if isinstance(si, dict) else False
            else:
                accusations = getattr(case, "accusations", []) or []
                articles = getattr(case, "relevant_articles", []) or []
                fact = getattr(case, "fact", "") or ""
                case_id = str(getattr(case, "case_id", ""))
                si = getattr(case, "sentence_info", None)
                getattr(si, "imprisonment_months", None) if si else getattr(case, "imprisonment_months", None)
                getattr(si, "fine_amount", None) if si else getattr(case, "punish_of_money", None)
                bool(getattr(si, "death_penalty", False) if si else getattr(case, "death_penalty", False))
                bool(getattr(si, "life_imprisonment", False) if si else getattr(case, "life_imprisonment", False))

            crime_match = any(
                crime_normalized in str(acc).replace("罪", "") or str(acc).replace("罪", "") in crime_normalized
                for acc in accusations if acc
            )
            article_match = any(
                _normalize_article(str(art)) == article_normalized
                for art in articles if art
            )

            if crime_match and article_match:
                extra = loader.get_case_extra(case_id)
                matching.append(CaseItem(
                    case_id=case_id,
                    fact=fact,
                    accusations=[str(a) for a in accusations if a],
                    relevant_articles=[str(a) for a in articles if a],
                    criminals=extra.get("criminals", []),
                    imprisonment_months=int(extra["imprisonment_months"]) if extra.get("imprisonment_months") else None,
                    fine_amount=float(extra["fine_amount"]) if extra.get("fine_amount") else None,
                    death_penalty=extra.get("death_penalty", False),
                    life_imprisonment=extra.get("life_imprisonment", False),
                    ))
        except Exception:
            continue

    return RelationCasesResponse(
        crime=crime_normalized,
        article=article_normalized,
        total_found=len(matching),
        cases=matching,
        )


def get_full_graph(top_crimes: int, crime: str) -> GraphResponse:
    crime_map = _get_crime_map()

    if not crime_map:
        return GraphResponse(nodes=[], edges=[], total_crimes=0, total_articles=0, total_edges=0)

    if crime.strip():
        selected = {c: v for c, v in crime_map.items() if crime in c}
    else:
        sorted_crimes = sorted(
            crime_map.items(),
            key=lambda x: sum(x[1].values() if isinstance(x[1], dict) else [len(x[1])]),
            reverse=True,
            )
        selected = dict(sorted_crimes[:top_crimes])

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    article_weights: dict[str, int] = {}

    for crime_name, articles in selected.items():
        art_map = articles if isinstance(articles, dict) else {str(a): 1 for a in articles}
        total_weight = sum(art_map.values())
        nodes.append(GraphNode(id=f"crime_{crime_name}", label=crime_name, type="crime", weight=total_weight))
        for art_num, cnt in art_map.items():
            edge_weight = int(cnt) if isinstance(cnt, (int, float)) else 1
            edges.append(GraphEdge(source=f"crime_{crime_name}", target=f"article_{art_num}", weight=edge_weight))
            article_weights[art_num] = article_weights.get(art_num, 0) + edge_weight

    for art_num, weight in article_weights.items():
        nodes.append(GraphNode(id=f"article_{art_num}", label=f"第{art_num}条", type="article", weight=weight))

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_crimes=len([n for n in nodes if n.type == "crime"]),
        total_articles=len([n for n in nodes if n.type == "article"]),
        total_edges=len(edges),
        )
