import json
from types import SimpleNamespace

from app.core import logger as logger_module


def test_log_ai_call_redacts_content_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "BASE_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "_STARTUP_TS", "test")
    monkeypatch.setattr(logger_module, "settings", SimpleNamespace(LOG_AI_CONTENT=False))

    logger_module.log_ai_call(
        stage="s1",
        thread_id="thread-1",
        input_messages=[{"role": "user", "content": "private case facts"}],
        output="private legal report",
    )

    log_file = next(tmp_path.rglob("*.jsonl"))
    raw = log_file.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert "private case facts" not in raw
    assert "private legal report" not in raw
    assert record["input_count"] == 1
    assert record["output_chars"] == len("private legal report")


def test_log_ai_call_keeps_content_when_explicitly_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_module, "BASE_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "_STARTUP_TS", "test")
    monkeypatch.setattr(logger_module, "settings", SimpleNamespace(LOG_AI_CONTENT=True))

    logger_module.log_ai_call(
        stage="s1",
        thread_id="thread-1",
        input_messages=[{"role": "user", "content": "private case facts"}],
        output="private legal report",
    )

    record = json.loads(next(tmp_path.rglob("*.jsonl")).read_text(encoding="utf-8"))
    assert record["input"][0]["content"] == "private case facts"
    assert record["output"] == "private legal report"
