# 数据浏览服务层
import json
from pathlib import Path

from app.db.data_loader import get_data_loader
from app.schemas.v1.data import ArticleItem, ArticleListResponse, CaseItem, CaseListResponse

_cases_cache: list | None = None


def _load_cases_json() -> list:
    global _cases_cache
    if _cases_cache is not None:
        return _cases_cache
    p = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cases" / "legal_cases.json"
    items = []
    with open(p, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                meta = raw.get("meta", {})
                toi = meta.get("term_of_imprisonment", {}) or {}
                items.append({
                    "case_id": f"case_{str(i + 1).zfill(6)}",
                    "fact": raw.get("fact", ""),
                    "accusations": meta.get("accusation", []),
                    "relevant_articles": [str(a) for a in (meta.get("relevant_articles", []) or [])],
                    "criminals": meta.get("criminals", []),
                    "imprisonment_months": toi.get("imprisonment"),
                    "fine_amount": meta.get("punish_of_money") or None,
                    "death_penalty": bool(toi.get("death_penalty", False)),
                    "life_imprisonment": bool(toi.get("life_imprisonment", False)),
                })
            except Exception:
                continue
    _cases_cache = items
    return _cases_cache


def list_articles(q: str, chapter: str, page: int, page_size: int) -> ArticleListResponse:
    loader = get_data_loader()
    raw_list = loader.original_data.get("articles") or loader.get_metadata("articles") or []

    items = []
    for meta in raw_list:
        if isinstance(meta, dict):
            art_num = meta.get("article_number")
            title = str(meta.get("title", "") or "")
            chap = str(meta.get("chapter", "") or "")
            content = str(meta.get("content", "") or "")
        else:
            art_num = getattr(meta, "article_number", None)
            title = str(getattr(meta, "title", "") or "")
            chap = str(getattr(meta, "chapter", "") or "")
            content = str(getattr(meta, "content", "") or "")
        if art_num is None:
            continue
        if q and q not in title and q not in chap and q not in content and q not in str(art_num):
            continue
        if chapter and chapter not in chap:
            continue
        items.append(ArticleItem(article_number=int(art_num), title=title, chapter=chap, content=content))

    items.sort(key=lambda x: x.article_number)
    total = len(items)
    start = (page - 1) * page_size
    return ArticleListResponse(items=items[start:start + page_size], total=total, page=page, page_size=page_size)


def list_cases(q: str, page: int, page_size: int) -> CaseListResponse:
    raw_list = _load_cases_json()

    items = []
    for meta in raw_list:
        accusations = meta.get("accusations", []) or []
        fact = meta.get("fact", "")
        if q:
            acc_str = " ".join(str(a) for a in accusations)
            if q not in acc_str and q not in fact:
                continue
        items.append(CaseItem(
            case_id=meta.get("case_id", ""),
            accusations=[str(a) for a in accusations if a],
            fact=fact,
            relevant_articles=meta.get("relevant_articles", []),
            criminals=[str(c) for c in meta.get("criminals", []) if c],
            imprisonment_months=int(meta["imprisonment_months"]) if meta.get("imprisonment_months") else None,
            fine_amount=float(meta["fine_amount"]) if meta.get("fine_amount") else None,
            death_penalty=meta.get("death_penalty", False),
            life_imprisonment=meta.get("life_imprisonment", False),
            ))

    total = len(items)
    start = (page - 1) * page_size
    return CaseListResponse(items=items[start:start + page_size], total=total, page=page, page_size=page_size)
