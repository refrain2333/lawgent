# Agent 接口测试
#
# 针对当前的「FastAPI + 数据库状态机」实现（不使用 LangGraph）。
# 覆盖：鉴权边界、会话创建、状态查询、消息落库、会话列表与删除。
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.models.models import Conversation, ConversationStage, Message, User
from main import create_app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession):
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    user = User(email="agent@example.com", password=hash_password("password123"), nickname="测试用户")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def token(test_user: User):
    return create_access_token({"user_id": test_user.id})


@pytest.fixture
def invalid_token():
    return "invalid.token.here"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ #
# 一、鉴权边界
# ------------------------------------------------------------------ #

class TestAuth:
    """所有接口的鉴权边界：无 token 返回 401，无效 token 返回 401"""

    async def test_no_token_create_session(self, client: AsyncClient):
        response = await client.post("/api/v1/agent/sessions", json={})
        assert response.status_code == 401

    async def test_invalid_token_create_session(self, client: AsyncClient, invalid_token: str):
        response = await client.post(
            "/api/v1/agent/sessions", json={}, headers=_auth(invalid_token)
        )
        assert response.status_code == 401

    async def test_no_token_list_conversations(self, client: AsyncClient):
        response = await client.get("/api/v1/agent/conversations")
        assert response.status_code == 401

    async def test_invalid_token_list_conversations(self, client: AsyncClient, invalid_token: str):
        response = await client.get(
            "/api/v1/agent/conversations", headers=_auth(invalid_token)
        )
        assert response.status_code == 401

    async def test_no_token_send_message(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/agent/sessions/some-thread/message", json={"content": "test"}
        )
        assert response.status_code == 401

    async def test_token_via_query_still_supported(self, client: AsyncClient, token: str):
        """SSE 场景下仍支持 query 参数传 token"""
        response = await client.get(f"/api/v1/agent/conversations?token={token}")
        assert response.status_code == 200

    async def test_hardcoded_debug_token_rejected(self, client: AsyncClient):
        """历史调试 token 不应再被接受"""
        response = await client.get("/api/v1/agent/conversations?token=admin")
        assert response.status_code == 401


# ------------------------------------------------------------------ #
# 二、会话创建与恢复
# ------------------------------------------------------------------ #

class TestSessionCreate:

    async def test_create_new_session(self, client: AsyncClient, token: str):
        response = await client.post(
            "/api/v1/agent/sessions", json={"conversation_id": None}, headers=_auth(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert data["stage"] == ConversationStage.S1_COLLECTING

    async def test_create_session_saves_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        response = await client.post(
            "/api/v1/agent/sessions", json={}, headers=_auth(token)
        )
        thread_id = response.json()["thread_id"]
        result = await db_session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        conv = result.scalar_one_or_none()
        assert conv is not None
        assert conv.user_id == test_user.id


# ------------------------------------------------------------------ #
# 三、状态查询
# ------------------------------------------------------------------ #

class TestSessionState:

    async def test_get_state_success(self, client: AsyncClient, token: str):
        create = await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        thread_id = create.json()["thread_id"]
        response = await client.get(
            f"/api/v1/agent/sessions/{thread_id}/state", headers=_auth(token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert data["stage"] == ConversationStage.S1_COLLECTING


# ------------------------------------------------------------------ #
# 四、消息
# ------------------------------------------------------------------ #

class TestSendMessage:

    async def test_send_empty_message_rejected(self, client: AsyncClient, token: str):
        create = await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        thread_id = create.json()["thread_id"]
        response = await client.post(
            f"/api/v1/agent/sessions/{thread_id}/message",
            json={"content": "   "},
            headers=_auth(token),
        )
        assert response.status_code == 400

    async def test_send_message_saves_user_msg_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, monkeypatch
    ):
        """用户消息应在请求处理阶段（调用 LLM 之前）落库。"""
        from app.api.v1 import agent as agent_api

        async def _fake_stream(*args, **kwargs):
            yield 'data: {"type": "token", "content": "你好"}\n\n'
            yield 'data: {"type": "done"}\n\n'

        monkeypatch.setattr(agent_api, "chat_s1", _fake_stream)

        create = await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        thread_id = create.json()["thread_id"]

        async with client.stream(
            "POST",
            f"/api/v1/agent/sessions/{thread_id}/message",
            json={"content": "我朋友被人打伤了"},
            headers=_auth(token),
        ) as resp:
            assert resp.status_code == 200
            async for _ in resp.aiter_lines():
                pass

        msgs = await db_session.execute(select(Message))
        saved = msgs.scalars().all()
        assert any(m.content == "我朋友被人打伤了" and m.role == "user" for m in saved)


# ------------------------------------------------------------------ #
# 五、会话列表 / 历史消息 / 删除
# ------------------------------------------------------------------ #

class TestConversations:

    async def test_list_conversations_empty(self, client: AsyncClient, token: str):
        response = await client.get("/api/v1/agent/conversations", headers=_auth(token))
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_conversations_after_create(self, client: AsyncClient, token: str):
        await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        response = await client.get("/api/v1/agent/conversations", headers=_auth(token))
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_get_messages_empty(self, client: AsyncClient, token: str):
        create = await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        thread_id = create.json()["thread_id"]
        response = await client.get(
            f"/api/v1/agent/conversations/{thread_id}/messages", headers=_auth(token)
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_delete_conversation(self, client: AsyncClient, token: str):
        create = await client.post("/api/v1/agent/sessions", json={}, headers=_auth(token))
        thread_id = create.json()["thread_id"]
        response = await client.delete(
            f"/api/v1/agent/conversations/{thread_id}", headers=_auth(token)
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    async def test_conversations_only_own_user(
        self, client: AsyncClient, token: str, db_session: AsyncSession
    ):
        """只返回当前用户自己的会话"""
        other = User(email="other@example.com", password=hash_password("password123"))
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)

        from app.services import conversation_service
        await conversation_service.upsert_conversation(
            other.id, "other-thread", ConversationStage.S1_COLLECTING
        )

        response = await client.get("/api/v1/agent/conversations", headers=_auth(token))
        thread_ids = [c["thread_id"] for c in response.json()]
        assert "other-thread" not in thread_ids

