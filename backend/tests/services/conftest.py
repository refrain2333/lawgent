"""服务层测试的收集期保护。

依赖 PyTorch、Lawformer 模型与处理后的数据；缺失时整体跳过。
"""
import importlib.util
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_VECTORS_DIR = _BACKEND_DIR.parent / "data" / "processed" / "vectors"

_MISSING = []
if importlib.util.find_spec("torch") is None:
    _MISSING.append("torch")
if not _VECTORS_DIR.exists():
    _MISSING.append("data/processed/vectors")

if _MISSING:
    pytest.skip(
        "缺少运行该测试所需的资源：" + "、".join(_MISSING)
        + "（属预期情况，准备数据与模型后即可运行）",
        allow_module_level=True,
    )

