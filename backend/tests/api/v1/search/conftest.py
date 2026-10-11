"""检索相关测试的收集期保护。

这些测试需要 PyTorch、Lawformer 模型与处理后的数据（data/processed/）。
开源仓库不包含这些资源，因此在本机缺少依赖时整体跳过，
而不是让 pytest 收集失败。
"""
import importlib.util
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_VECTORS_DIR = _BACKEND_DIR.parent / "data" / "processed" / "vectors"

_MISSING = []
if importlib.util.find_spec("torch") is None:
    _MISSING.append("torch")
if not _VECTORS_DIR.exists():
    _MISSING.append("data/processed/vectors")

if _MISSING:
    pytest.skip(
        "缺少运行检索测试所需的资源：" + "、".join(_MISSING)
        + "（属预期情况，准备数据与模型后即可运行）",
        allow_module_level=True,
    )

