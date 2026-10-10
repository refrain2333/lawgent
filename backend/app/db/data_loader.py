# 数据加载器 - 加载向量数据、原始数据，构建 BM25 索引
import logging
import pickle
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import ahocorasick
import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.db.legacy_compatibility import safe_load_pickle

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r'[^\u4e00-\u9fa5a-zA-Z0-9]')


def _tokenize(text: str, use_ngram: bool = False) -> list[str]:
    """jieba 精确模式分词，短文本可开启 2/3-gram 扩充。

    use_ngram=True  适用于罪名、法条标题等短文本
    use_ngram=False 适用于案件事实等长文本，避免 token 爆炸
    """
    if not text:
        return []
    words = [w for w in jieba.cut(text, cut_all=False) if w.strip()]
    if not use_ngram:
        return words
    tokens = set(words)
    pure = _PUNCT_RE.sub('', text)
    for n in (2, 3):
        for i in range(len(pure) - n + 1):
            tokens.add(pure[i: i + n])
    return list(tokens)


class DataLoader:
    """统一数据加载管理器"""

    def __init__(self):
        project_root = Path(__file__).parent.parent.parent.parent

        self.vectors_dir = self._resolve(settings.DATA_VECTORS_PATH, project_root)
        self.criminal_dir = self._resolve(settings.DATA_CRIMINAL_PATH, project_root)
        self.kg_dir = self._resolve(settings.DATA_KG_PATH, project_root)
        self.cases_json_path = project_root / "data" / "cases" / "legal_cases.json"

        # 向量数据
        self.vectors_data: dict[str, Any] = {}
        self.vectors_loaded = False

        # 原始数据
        self.original_data: dict[str, Any] = {}
        self.original_loaded = False

        # BM25
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_doc_ids: list[str] = []
        self.bm25_built = False

        # 知识图谱
        self.knowledge_graph: Optional[Any] = None
        self.kg_loaded = False
        # AC 自动机（罪名多模式匹配）
        self.kg_automaton: Optional[ahocorasick.Automaton] = None
        # 罪名 -> {法条编号: 频次} 的扁平化映射
        self._kg_crime_map: dict[str, dict[str, int]] = {}

        # 内容缓存
        self.content_cache: dict[str, str] = {}
        self._lock = Lock()

        # JSON 案例扩展字段索引 {case_id: {criminals, death_penalty, life_imprisonment}}
        self._cases_json_index: dict[str, dict] = {}
        self._cases_json_loaded = False

        logger.info("DataLoader 初始化完成")
        logger.info(f"  向量目录: {self.vectors_dir}")
        logger.info(f"  原始数据目录: {self.criminal_dir}")
        logger.info(f"  知识图谱目录: {self.kg_dir}")

    def _resolve(self, path_str: str, root: Path) -> Path:
        p = Path(path_str)
        return p if p.is_absolute() else (root / p).resolve()

    # ------------------------------------------------------------------ #
    # 公开加载入口
    # ------------------------------------------------------------------ #

    def load_all(self) -> dict[str, Any]:
        """启动时一次性加载所有数据：向量 + 原始数据 + BM25索引 + 知识图谱"""
        t0 = time.time()
        v = self.load_vectors()
        o = self.load_original_data()
        b = self.build_bm25_index()
        kg = self.load_knowledge_graph()
        return {
            "vectors": v,
            "original_data": o,
            "bm25_index": b,
            "knowledge_graph": kg,
            "total_documents": self.get_total_count(),
            "elapsed": round(time.time() - t0, 2),
            }

    def load_vectors(self) -> dict[str, Any]:
        """加载法条和案例向量 pkl"""
        if self.vectors_loaded:
            return {"status": "already_loaded"}

        t0 = time.time()
        errors = []

        for dtype, fname in [("articles", settings.ARTICLES_VECTORS_FILE),
                              ("cases", settings.CASES_VECTORS_FILE)]:
            fpath = self.vectors_dir / fname
            if not fpath.exists():
                errors.append(f"文件不存在: {fpath}")
                continue
            try:
                with open(fpath, "rb") as f:
                    data = pickle.load(f)
                if not isinstance(data, dict):
                    raise ValueError("向量包必须是字典")
                vectors = np.asarray(data.get("vectors"))
                metadata = data.get("metadata")
                if (
                    vectors.ndim != 2
                    or vectors.shape[0] == 0
                    or vectors.shape[1] != settings.EMBEDDING_DIM
                    or not np.issubdtype(vectors.dtype, np.number)
                    or not np.isfinite(vectors).all()
                    or not isinstance(metadata, list)
                    or len(metadata) != vectors.shape[0]
                    or not all(isinstance(meta, dict) for meta in metadata)
                ):
                    raise ValueError("向量维度或元数据数量不匹配")
                data["vectors"] = vectors
                data["total_count"] = len(metadata)
                self.vectors_data[dtype] = data
                count = len(metadata)
                logger.info(f"加载 {dtype} 向量: {count} 条")
            except Exception as e:
                self.vectors_data.pop(dtype, None)
                errors.append(f"加载 {fname} 失败: {e}")

        self.vectors_loaded = len(errors) == 0
        status = "success" if self.vectors_loaded else "error"
        result = {"status": status, "elapsed": round(time.time() - t0, 2)}
        if errors:
            result["errors"] = errors
        return result

    def load_original_data(self) -> dict[str, Any]:
        """启动时加载法条和案例原始 pkl，供内容检索和 BM25 索引构建使用"""
        if self.original_loaded:
            return {"status": "already_loaded"}

        with self._lock:
            self.content_cache.clear()
        self.bm25_built = False

        t0 = time.time()
        errors = []
        for dtype, fname in [("articles", "criminal_articles.pkl"),
                              ("cases", "criminal_cases.pkl")]:
            fpath = self.criminal_dir / fname
            if not fpath.exists():
                self.original_data.pop(dtype, None)
                errors.append(f"文件不存在: {fpath}")
                continue
            if not self._load_original(dtype):
                errors.append(f"加载 {fname} 失败，原始数据不可用")
                continue
            logger.info(f"加载原始数据 {dtype}: {len(self.original_data.get(dtype, []))} 条")

        self.original_loaded = len(errors) == 0
        result = {
            "status": "success" if self.original_loaded else "error",
            "elapsed": round(time.time() - t0, 2),
            }
        if errors:
            result["errors"] = errors
        return result

    def build_bm25_index(self) -> dict[str, Any]:
        """基于向量元数据构建 BM25 索引，支持磁盘缓存"""
        if self.bm25_built:
            return {"status": "already_built"}
        if not self.vectors_loaded:
            return {"status": "error", "error": "向量未加载，无法构建 BM25"}

        # 尝试从缓存加载
        cache_path = self.vectors_dir / "bm25_index.pkl"
        source_signature = self._bm25_source_signature()
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    cached = pickle.load(f)
                if cached.get("source_signature") != source_signature:
                    raise ValueError("BM25 来源数据已变化")
                if not isinstance(cached.get("index"), BM25Okapi):
                    raise ValueError("BM25 缓存格式不正确")
                if cached["index"].corpus_size != len(cached["doc_ids"]):
                    raise ValueError("BM25 缓存文档数量不匹配")
                self.bm25_index = cached["index"]
                self.bm25_doc_ids = cached["doc_ids"]
                self.bm25_built = True
                logger.info(f"BM25 索引从缓存加载: {len(self.bm25_doc_ids)} 条文档")
                return {"status": "success", "source": "cache", "total_documents": len(self.bm25_doc_ids)}
            except Exception as e:
                logger.warning(f"BM25 缓存加载失败，重新构建: {e}")

        t0 = time.time()
        corpus: list[list[str]] = []
        doc_ids: list[str] = []

        # 法条：短文本，开启 n-gram
        for meta in self.vectors_data.get("articles", {}).get("metadata", []):
            parts = []
            if meta.get("title"):
                parts.append(str(meta["title"]))
            if meta.get("article_number"):
                parts.append(f"第{meta['article_number']}条")
                parts.append(str(meta["article_number"]))
            if meta.get("chapter"):
                parts.append(str(meta["chapter"]))
            article_id = str(meta.get("article_number") or meta.get("id", ""))
            content = self.get_article_content(article_id)
            if content:
                parts.append(content)
            corpus.append(_tokenize(" ".join(parts), use_ngram=True))
            doc_ids.append(f"article_{meta.get('article_number', len(doc_ids))}")

        # 案例：预建 fact 索引
        case_fact_index: dict[str, str] = {}
        for item in self.original_data.get("cases", []):
            if isinstance(item, dict):
                cid = str(item.get("case_id") or item.get("id", ""))
                fact = item.get("fact", "") or ""
            else:
                cid = str(getattr(item, "case_id", None) or getattr(item, "id", ""))
                fact = getattr(item, "fact", "") or ""
            if cid and fact:
                case_fact_index[cid] = fact

        for meta in self.vectors_data.get("cases", {}).get("metadata", []):
            tokens: list[str] = []
            acc = meta.get("accusations", [])
            acc_list = acc if isinstance(acc, list) else ([str(acc)] if acc else [])
            # 罪名、法条编号：短文本，开启 n-gram
            for a in acc_list:
                tokens.extend(_tokenize(a, use_ngram=True))
            for art in (meta.get("relevant_articles") or []):
                tokens.extend(_tokenize(f"第{art}条", use_ngram=True))
            # 案件事实：长文本，关闭 n-gram
            case_id = meta.get("case_id", meta.get("id", len(doc_ids)))
            fact = case_fact_index.get(str(case_id), "")
            if fact:
                tokens.extend(_tokenize(fact, use_ngram=False))
            corpus.append(tokens if tokens else ["案例"])
            doc_ids.append(f"case_{case_id}")

        if not corpus:
            return {"status": "error", "error": "没有可用文档"}

        self.bm25_index = BM25Okapi(corpus)
        self.bm25_doc_ids = doc_ids
        self.bm25_built = True

        # 写入缓存
        try:
            with open(cache_path, "wb") as f:
                pickle.dump({
                    "index": self.bm25_index,
                    "doc_ids": doc_ids,
                    "source_signature": source_signature,
                }, f)
            logger.info(f"BM25 索引已缓存到 {cache_path}")
        except Exception as e:
            logger.warning(f"BM25 缓存写入失败: {e}")

        elapsed = round(time.time() - t0, 2)
        logger.info(f"BM25 索引构建完成: {len(corpus)} 条文档，耗时 {elapsed}s")
        return {
            "status": "success",
            "source": "built",
            "total_documents": len(corpus),
            "articles_count": sum(1 for d in doc_ids if d.startswith("article_")),
            "cases_count": sum(1 for d in doc_ids if d.startswith("case_")),
            "elapsed": elapsed,
            }

    def _bm25_source_signature(self) -> tuple:
        """数据或分词规则更新后，旧索引不能继续使用。"""
        sources = [
            self.vectors_dir / settings.ARTICLES_VECTORS_FILE,
            self.vectors_dir / settings.CASES_VECTORS_FILE,
            self.criminal_dir / "criminal_articles.pkl",
            self.criminal_dir / "criminal_cases.pkl",
        ]
        signature = []
        for source in sources:
            try:
                stat = source.stat()
                signature.append((str(source), stat.st_size, stat.st_mtime_ns))
            except OSError:
                signature.append((str(source), None, None))
        return (2, self.original_loaded, tuple(signature))

    # ------------------------------------------------------------------ #
    # 数据访问
    # ------------------------------------------------------------------ #

    def get_vectors(self, dtype: str) -> Optional[np.ndarray]:
        if not self.vectors_loaded or dtype not in self.vectors_data:
            return None
        return self.vectors_data[dtype]["vectors"]

    def get_metadata(self, dtype: str) -> Optional[list[dict]]:
        if not self.vectors_loaded or dtype not in self.vectors_data:
            return None
        return self.vectors_data[dtype]["metadata"]

    def get_total_count(self) -> int:
        if not self.vectors_loaded:
            return 0
        return sum(v.get("total_count", 0) for v in self.vectors_data.values())

    def get_crime_article_map(self) -> dict[str, dict[str, int]]:
        """返回规范化后的罪名与法条频次映射。"""
        return self._kg_crime_map if self.kg_loaded else {}

    def load_knowledge_graph(self) -> dict[str, Any]:
        """加载知识图谱 pkl"""
        if self.kg_loaded:
            return {"status": "already_loaded"}

        t0 = time.time()
        fpath = self.kg_dir / "knowledge_graph.pkl"
        if not fpath.exists():
            return {"status": "error", "error": f"文件不存在: {fpath}"}

        try:
            with open(fpath, "rb") as f:
                self.knowledge_graph = pickle.load(f)
            self._build_kg_automaton()
            self.kg_loaded = True
            elapsed = round(time.time() - t0, 2)
            logger.info(f"知识图谱加载完成，AC自动机罪名数={len(self._kg_crime_map)}，耗时 {elapsed}s")
            return {"status": "success", "elapsed": elapsed, "crime_count": len(self._kg_crime_map)}
        except Exception as e:
            self.kg_loaded = False
            self.knowledge_graph = None
            self.kg_automaton = None
            self._kg_crime_map = {}
            logger.error(f"知识图谱加载失败: {e}")
            return {"status": "error", "error": str(e)}

    def _build_kg_automaton(self) -> None:
        """从知识图谱构建 AC 自动机 + 罪名映射，支持 O(|query|) 多模式匹配。"""
        kg = self.knowledge_graph
        crime_article_map = getattr(kg, "crime_article_map", None) or (
            kg.get("crime_article_mapping", {}) if isinstance(kg, dict) else {}
        )
        if not crime_article_map:
            raise ValueError("知识图谱中未找到罪名映射字段")

        # 规范化为 {crime: {art_num_str: count}}
        normalized: dict[str, dict[str, int]] = {}
        for crime, articles in crime_article_map.items():
            art_map: dict[str, int] = {}
            if isinstance(articles, dict):
                for art_num, cnt in articles.items():
                    count = int(cnt) if isinstance(cnt, (int, float)) else 1
                    if count > 0:
                        art_map[str(art_num)] = count
            elif isinstance(articles, list):
                for art_num in articles:
                    art_map[str(art_num)] = art_map.get(str(art_num), 0) + 1
            if art_map:
                name = str(crime).strip().removesuffix("罪")
                if not name:
                    continue
                existing = normalized.setdefault(name, {})
                for art_num, count in art_map.items():
                    existing[art_num] = existing.get(art_num, 0) + count

        if not normalized:
            raise ValueError("知识图谱中没有有效的罪名关系")

        self._kg_crime_map = normalized

        # 构建 AC 自动机
        automaton = ahocorasick.Automaton()
        for crime in normalized:
            automaton.add_word(crime, crime)
            automaton.add_word(f"{crime}罪", crime)
        automaton.make_automaton()
        self.kg_automaton = automaton

    def kg_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """知识图谱搜索：AC自动机识别罪名 → 聚合法条频次 → 归一化评分，返回 [(法条编号, 归一化分)] 列表。
        AC 无命中时降级为前缀模糊匹配。"""
        if not query.strip() or top_k <= 0 or not self.kg_loaded or self.kg_automaton is None:
            return []

        # AC 自动机多模式匹配，O(|query|)
        matched_articles: dict[str, int] = {}
        matched_crimes: set[str] = set()
        for _, crime in self.kg_automaton.iter(query):
            if crime in matched_crimes:
                continue
            matched_crimes.add(crime)
            for art_num, count in self._kg_crime_map.get(crime, {}).items():
                matched_articles[art_num] = matched_articles.get(art_num, 0) + count

        # AC 无命中时，前缀模糊匹配罪名
        if not matched_articles:
            q = query.strip()
            for crime, art_map in self._kg_crime_map.items():
                if q in crime:
                    for art_num, count in art_map.items():
                        matched_articles[art_num] = matched_articles.get(art_num, 0) + count

        if not matched_articles:
            return []

        max_freq = max(matched_articles.values())
        normalized = {art: cnt / max_freq for art, cnt in matched_articles.items()}
        return sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def bm25_search(self, query: str, top_k: int = 20, dtype: str | None = None) -> list[dict]:
        """BM25 关键词搜索。dtype 可选 'articles'/'cases'，按类型独立取 top_k，避免两类互相竞争排名。"""
        if not self.bm25_built:
            return []
        scores = self.bm25_index.get_scores(_tokenize(query, use_ngram=True))
        prefix = {"articles": "article_", "cases": "case_"}.get(dtype or "", "")
        # 按 prefix 过滤候选索引
        candidates = [
            i for i, did in enumerate(self.bm25_doc_ids)
            if scores[i] > 0 and (not prefix or did.startswith(prefix))
            ]
        candidates.sort(key=lambda i: scores[i], reverse=True)
        return [
            {"id": self.bm25_doc_ids[i], "score": float(scores[i]), "source": "bm25"}
            for i in candidates[:top_k]
            ]

    def get_article_content(self, article_id: str) -> Optional[str]:
        return self._get_content("articles", article_id, "content")

    def get_case_content(self, case_id: str) -> Optional[str]:
        return self._get_content("cases", case_id, "fact")

    def _get_content(self, dtype: str, item_id: str, field: str) -> Optional[str]:
        cache_key = f"{dtype}_{item_id}"
        if cache_key in self.content_cache:
            return self.content_cache[cache_key]

        with self._lock:
            if cache_key in self.content_cache:
                return self.content_cache[cache_key]

            content = None
            for item in self.original_data.get(dtype, []):
                if isinstance(item, dict):
                    actual_id = item.get("case_id") or item.get("article_number") or item.get("id")
                else:
                    actual_id = (
                        getattr(item, "case_id", None)
                        or getattr(item, "article_number", None)
                        or getattr(item, "document_id", None)
                        )
                if actual_id is not None and self._ids_match(str(actual_id), item_id):
                    content = getattr(item, field, None) or (item.get(field) if isinstance(item, dict) else None)
                    break

            if content:
                if len(self.content_cache) >= settings.CACHE_SIZE_LIMIT:
                    # 简单 LRU：删除前 10%
                    drop = list(self.content_cache.keys())[: max(1, len(self.content_cache) // 10)]
                    for k in drop:
                        del self.content_cache[k]
                self.content_cache[cache_key] = content

            return content

    def _load_original(self, dtype: str) -> bool:
        fname = "criminal_articles.pkl" if dtype == "articles" else "criminal_cases.pkl"
        data = safe_load_pickle(self.criminal_dir / fname)
        if not isinstance(data, (list, tuple)):
            self.original_data.pop(dtype, None)
            return False
        self.original_data[dtype] = data
        return True

    def load_cases_json_index(self) -> None:
        """加载 legal_cases.json 构建 {case_id: extra_fields} 索引"""
        if self._cases_json_loaded:
            return
        import json
        p = self.cases_json_path
        if not p.exists():
            logger.warning(f"legal_cases.json 不存在: {p}")
            return
        idx: dict[str, dict] = {}
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    meta = raw.get("meta", {})
                    toi = meta.get("term_of_imprisonment", {}) or {}
                    case_id = f"case_{str(i + 1).zfill(6)}"
                    idx[case_id] = {
                        "criminals": meta.get("criminals", []),
                        "death_penalty": bool(toi.get("death_penalty", False)),
                        "life_imprisonment": bool(toi.get("life_imprisonment", False)),
                        "imprisonment_months": toi.get("imprisonment"),
                        "fine_amount": meta.get("punish_of_money"),
                    }
                except Exception:
                    continue
        self._cases_json_index = idx
        self._cases_json_loaded = True
        logger.info(f"JSON 案例索引加载完成: {len(idx)} 条")

    def get_case_extra(self, case_id: str) -> dict:
        """获取案例扩展字段（criminals/death_penalty/life_imprisonment）"""
        if not self._cases_json_loaded:
            self.load_cases_json_index()
        return self._cases_json_index.get(case_id, {})

    @staticmethod
    def _ids_match(a: str, b: str) -> bool:
        if a == b or a.lower() == b.lower():
            return True
        # 处理重复前缀 case_case_xxx
        if b.startswith("case_case_") and a.startswith("case_"):
            return a == b.replace("case_case_", "case_")
        # 数字匹配
        import re
        am = re.search(r"(\d+)", a)
        bm = re.search(r"(\d+)", b)
        if am and bm and int(am.group(1)) == int(bm.group(1)):
            return True
        return False


# 全局单例
_data_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader
