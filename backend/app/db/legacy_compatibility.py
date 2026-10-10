# pickle 兼容层 - 处理旧版 pkl 文件中的类引用
import logging
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class LegacyDataObject:
    """通用 Legacy 数据对象，支持动态属性"""

    def __init__(self, *args, **kwargs):
        if args and len(args) == 1 and isinstance(args[0], dict):
            for k, v in args[0].items():
                setattr(self, k, v)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name: str) -> Any:
        if name.endswith(("_list", "s")):
            return []
        elif name.endswith(("_id", "_number")):
            return None
        return None

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)
        # pickle 恢复对象时不调用 __init__，旧字段也必须在这里规范化。
        normalize = getattr(self, "_normalize", None)
        if callable(normalize):
            normalize()

    def __reduce__(self):
        return (self.__class__, (), self.__dict__)


class LegacyCase(LegacyDataObject):
    """Legacy 案例数据类"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._normalize()

    def _normalize(self):
        if not getattr(self, "case_id", None):
            for f in ["id", "document_id", "caseId"]:
                if getattr(self, f, None):
                    self.case_id = getattr(self, f)
                    break
        if not getattr(self, "accusations", None):
            self.accusations = []
        elif isinstance(self.accusations, str):
            self.accusations = [a.strip() for a in self.accusations.split(",") if a.strip()]
        if not getattr(self, "relevant_articles", None):
            self.relevant_articles = []
        if not getattr(self, "fact", None):
            for f in ["content", "text", "case_fact", "description"]:
                if getattr(self, f, None):
                    self.fact = getattr(self, f)
                    break
            else:
                self.fact = ""


class LegacyArticle(LegacyDataObject):
    """Legacy 法条数据类"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._normalize()

    def _normalize(self):
        if not getattr(self, "article_number", None):
            for f in ["number", "articleNumber", "id"]:
                val = getattr(self, f, None)
                if val is not None:
                    try:
                        self.article_number = int(val)
                        break
                    except (ValueError, TypeError):
                        continue
        if not getattr(self, "title", None):
            num = getattr(self, "article_number", None)
            self.title = f"第{num}条" if num else "未知条文"
        if not getattr(self, "content", None):
            for f in ["text", "body", "full_text", "article_text"]:
                if getattr(self, f, None):
                    self.content = getattr(self, f)
                    break
            else:
                self.content = ""


# 类名映射表
_CLASS_MAP = {
    "CriminalCase": LegacyCase,
    "Case": LegacyCase,
    "LegalCase": LegacyCase,
    "CriminalArticle": LegacyArticle,
    "CriminalLawArticle": LegacyArticle,
    "Article": LegacyArticle,
    "LegalArticle": LegacyArticle,
}


def _setup_modules():
    """注册兼容性模块到 sys.modules"""
    data_module = SimpleNamespace()
    for name, cls in _CLASS_MAP.items():
        setattr(data_module, name, cls)

    for sub in ["criminal_articles", "criminal_cases", "criminal_law_processor", "data_processor"]:
        submod = SimpleNamespace()
        for name, cls in _CLASS_MAP.items():
            setattr(submod, name, cls)
        sys.modules[f"src.data.{sub}"] = submod

    sys.modules["src.data"] = data_module


_setup_modules()


def safe_load_pickle(file_path: Union[str, Path]) -> Optional[Any]:
    """安全加载 pkl 文件，自动处理旧类引用"""
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    class _Unpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if name in _CLASS_MAP:
                return _CLASS_MAP[name]
            try:
                return super().find_class(module, name)
            except (ImportError, AttributeError):
                return LegacyDataObject

    try:
        with open(file_path, "rb") as f:
            data = _Unpickler(f).load()
        logger.info(f"加载 pkl 成功: {file_path.name} ({len(data) if hasattr(data, '__len__') else '?'} 条)")
        return data
    except Exception as e:
        logger.error(f"加载 pkl 失败 {file_path.name}: {e}")
        return None
