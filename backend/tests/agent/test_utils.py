import pytest

from app.agent.service.utils import parse_json


@pytest.mark.parametrize("raw", ["[]", "null", "42", '"text"'])
def test_parse_json_rejects_non_object_json(raw: str):
    assert parse_json(raw) == {}


def test_parse_json_accepts_object_wrapped_in_prose():
    assert parse_json('prefix {"ok": true} suffix') == {"ok": True}


def test_check_sufficient_rejects_non_object_response(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.agent.service import s1

    class FakeChatModel:
        async def ainvoke(self, _messages):
            return SimpleNamespace(content="[]")

    monkeypatch.setattr(s1, "get_chat_model", lambda: FakeChatModel())
    monkeypatch.setattr(s1, "log_ai_call", lambda **_kwargs: None)

    result = asyncio.run(s1.check_sufficient([]))
    assert result == {
        "sufficient": False,
        "reason": "判断失败，请继续补充案情",
        "summary": "",
    }
