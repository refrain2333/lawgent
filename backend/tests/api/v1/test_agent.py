# Agent 接口测试
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.models.models import Conversation, ConversationStage, Message, MessageRole, User
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


# ------------------------------------------------------------------ #
# Mock LangGraph 图状态
# ------------------------------------------------------------------ #

def _make_snapshot(stage="s1_collecting", facts=None, interrupted=False):
    snap = MagicMock()
    snap.values = {"stage": stage, "facts": facts or {}}
    snap.next = ["confirm_s1"] if interrupted else []
    task = MagicMock()
    task.interrupts = [MagicMock(value={
        "type": "confirm_request",
        "summary": "案情摘要",
        "facts": facts or {},
    })] if interrupted else []
    snap.tasks = [task]
    return snap


async def _async_iter_impl(items):
    for item in items:
        yield item


def _async_iter(items):
    return _async_iter_impl(items)


def _mock_stream(events: list[dict]):
    async def _gen(*args, **kwargs):
        for e in events:
            yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
    return _gen


# ------------------------------------------------------------------ #
# 一、鉴权测试
# ------------------------------------------------------------------ #

class TestAuth:
    """所有接口的鉴权边界测试"""

    async def test_no_token_create_session(self, client: AsyncClient):
        """无 token 创建会话返回 422"""
        response = await client.post("/api/v1/agent/sessions", json={})
        assert response.status_code == 422

    async def test_invalid_token_create_session(self, client: AsyncClient, invalid_token: str):
        """无效 token 返回 401"""
        response = await client.post(f"/api/v1/agent/sessions?token={invalid_token}", json={})
        assert response.status_code == 401

    async def test_no_token_list_conversations(self, client: AsyncClient):
        """无 token 获取会话列表返回 422"""
        response = await client.get("/api/v1/agent/conversations")
        assert response.status_code == 422

    async def test_invalid_token_list_conversations(self, client: AsyncClient, invalid_token: str):
        """无效 token 获取会话列表返回 401"""
        response = await client.get(f"/api/v1/agent/conversations?token={invalid_token}")
        assert response.status_code == 401

    async def test_no_token_send_message(self, client: AsyncClient):
        """无 token 发消息返回 422"""
        response = await client.post("/api/v1/agent/sessions/some-thread/message", json={"content": "test"})
        assert response.status_code == 422

    async def test_invalid_token_send_message(self, client: AsyncClient, invalid_token: str):
        """无效 token 发消息返回 401"""
        response = await client.post(
            f"/api/v1/agent/sessions/some-thread/message?token={invalid_token}",
            json={"content": "test"},
        )
        assert response.status_code == 401

    async def test_no_token_recall(self, client: AsyncClient):
        """无 token 撤回返回 422"""
        response = await client.post("/api/v1/agent/sessions/some-thread/recall")
        assert response.status_code == 422

    async def test_no_token_rollback(self, client: AsyncClient):
        """无 token 回滚返回 422"""
        response = await client.post("/api/v1/agent/sessions/some-thread/rollback", json={})
        assert response.status_code == 422


# ------------------------------------------------------------------ #
# 二、会话管理测试
# ------------------------------------------------------------------ #

class TestSessionCreate:
    """创建/恢复会话"""

    async def test_create_new_session(self, client: AsyncClient, token: str, test_user: User):
        """创建新会话，返回 thread_id 和初始状态"""
        snap = _make_snapshot()
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions?token={token}",
                json={"conversation_id": None},
            )
        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert data["stage"] == "s1_collecting"
        assert data["interrupted"] is False

    async def test_resume_existing_session(self, client: AsyncClient, token: str, test_user: User):
        """恢复已有会话"""
        thread_id = "existing-thread-123"
        snap = _make_snapshot(stage="s3_collecting", facts={"crimes": ["故意伤害罪"]})
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions?token={token}",
                json={"conversation_id": thread_id},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert data["stage"] == "s3_collecting"

    async def test_resume_interrupted_session(self, client: AsyncClient, token: str, test_user: User):
        """恢复处于 interrupt 状态的会话，返回 interrupt_payload"""
        snap = _make_snapshot(interrupted=True)
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions?token={token}",
                json={"conversation_id": "interrupted-thread"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["interrupted"] is True
        assert data["interrupt_payload"] is not None
        assert data["interrupt_payload"]["type"] == "confirm_request"

    async def test_create_session_saves_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """创建会话后数据库应有对应记录"""
        from sqlmodel import select
        snap = _make_snapshot()
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions?token={token}",
                json={"conversation_id": None},
            )
        thread_id = response.json()["thread_id"]
        result = await db_session.execute(select(Conversation).where(Conversation.title == thread_id))
        conv = result.scalar_one_or_none()
        assert conv is not None
        assert conv.user_id == test_user.id


# ------------------------------------------------------------------ #
# 三、会话状态查询测试
# ------------------------------------------------------------------ #

class TestSessionState:
    """GET /sessions/{thread_id}/state"""

    async def test_get_state_success(self, client: AsyncClient, token: str):
        """查询会话状态"""
        snap = _make_snapshot(stage="s3_collecting", facts={"crimes": ["盗窃罪"]})
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.get(f"/api/v1/agent/sessions/test-thread/state?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "s3_collecting"
        assert "盗窃罪" in data["facts"]["crimes"]

    async def test_get_state_interrupted(self, client: AsyncClient, token: str):
        """查询处于 interrupt 状态的会话"""
        snap = _make_snapshot(interrupted=True)
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.get(f"/api/v1/agent/sessions/test-thread/state?token={token}")
        assert response.status_code == 200
        assert response.json()["interrupted"] is True


# ------------------------------------------------------------------ #
# 四、发送消息测试
# ------------------------------------------------------------------ #

class TestSendMessage:
    """POST /sessions/{thread_id}/message"""

    async def test_send_empty_message(self, client: AsyncClient, token: str):
        """空消息返回 400"""
        snap = _make_snapshot()
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/message?token={token}",
                json={"content": "   "},
            )
        assert response.status_code == 400

    async def test_send_message_returns_sse(self, client: AsyncClient, token: str, test_user: User):
        """发送消息返回 SSE 流"""
        snap = _make_snapshot()
        events = [
            {"type": "token", "content": "根据"},
            {"type": "token", "content": "您的描述"},
            {"type": "end"},
        ]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/message?token={token}",
                json={"content": "我朋友被人打伤了"},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    async def test_send_message_saves_user_msg_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """发送消息后用户消息应写入数据库"""
        from sqlmodel import select
        snap = _make_snapshot()
        events = [{"type": "end"}]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            await client.post(
                f"/api/v1/agent/sessions/thread-user-msg/message?token={token}",
                json={"content": "故意伤害案测试"},
            )
        result = await db_session.execute(
            select(Message).where(Message.role == MessageRole.USER)
        )
        msgs = result.scalars().all()
        assert any(m.content == "故意伤害案测试" for m in msgs)

    async def test_send_message_saves_assistant_msg_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """SSE 流结束后 AI 回复应写入数据库"""
        from sqlmodel import select
        snap = _make_snapshot()
        events = [
            {"type": "token", "content": "您好"},
            {"type": "token", "content": "，请描述案情"},
            {"type": "end"},
        ]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            await client.post(
                f"/api/v1/agent/sessions/thread-assistant/message?token={token}",
                json={"content": "测试消息"},
            )
        result = await db_session.execute(
            select(Message).where(Message.role == MessageRole.ASSISTANT)
        )
        msgs = result.scalars().all()
        assert any("您好" in m.content for m in msgs)

    async def test_send_message_when_interrupted_acts_as_correction(
        self, client: AsyncClient, token: str, test_user: User
    ):
        """处于 interrupt 状态时发消息，自动作为 correction 处理"""
        snap = _make_snapshot(interrupted=True)
        events = [{"type": "end"}]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions/interrupted-thread/message?token={token}",
                json={"content": "不是刀，是玻璃瓶"},
            )
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# 五、确认接口测试
# ------------------------------------------------------------------ #

class TestConfirm:
    """POST /sessions/{thread_id}/confirm"""

    async def test_confirm_accepted_returns_sse(self, client: AsyncClient, token: str, test_user: User):
        """确认后返回 SSE 流"""
        snap = _make_snapshot(stage="s2_searching")
        events = [
            {"type": "stage", "stage": "s2_searching", "label": "正在检索..."},
            {"type": "end"},
        ]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/confirm?token={token}",
                json={"accepted": True},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    async def test_confirm_with_report_saves_to_db(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """确认后生成报告，报告应写入数据库"""
        from sqlmodel import select

        from app.models.models import RiskReport
        snap = _make_snapshot(stage="done")
        report = {"crime_analysis": "故意伤害罪", "risk_level": "高"}
        events = [
            {"type": "report", "content": report},
            {"type": "done", "conversation_id": "report-thread", "report": report},
        ]
        with patch("app.agent.service.get_graph") as mock_graph, \
             patch("app.agent.service.stream_graph", _mock_stream(events)):
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            await client.post(
                f"/api/v1/agent/sessions/report-thread/confirm?token={token}",
                json={"accepted": True},
            )
        result = await db_session.execute(select(RiskReport))
        reports = result.scalars().all()
        assert len(reports) > 0


# ------------------------------------------------------------------ #
# 六、撤回测试
# ------------------------------------------------------------------ #

class TestRecall:
    """POST /sessions/{thread_id}/recall"""

    async def test_recall_success(self, client: AsyncClient, token: str):
        """撤回成功返回更新后状态"""
        snap = _make_snapshot(stage="s1_collecting")
        history = [snap, _make_snapshot()]
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            mock_graph.return_value.aget_state_history = MagicMock(
                return_value=_async_iter(history)
            )
            mock_graph.return_value.aupdate_state = AsyncMock()
            response = await client.post(f"/api/v1/agent/sessions/test-thread/recall?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert "stage" in data

    async def test_recall_nothing_to_recall(self, client: AsyncClient, token: str):
        """无历史可撤回返回 400"""
        snap = _make_snapshot()
        history = [snap]
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            mock_graph.return_value.aget_state_history = MagicMock(
                return_value=_async_iter(history)
            )
            response = await client.post(f"/api/v1/agent/sessions/test-thread/recall?token={token}")
        assert response.status_code == 400
        assert "没有可撤回" in response.json()["detail"]


# ------------------------------------------------------------------ #
# 七、回滚测试
# ------------------------------------------------------------------ #

class TestRollback:
    """POST /sessions/{thread_id}/rollback"""

    async def test_rollback_success(self, client: AsyncClient, token: str):
        """回滚到 s1_collecting 成功"""
        snap_s1 = _make_snapshot(stage="s1_collecting")
        snap_s3 = _make_snapshot(stage="s3_collecting")
        history = [snap_s3, snap_s1]
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap_s1)
            mock_graph.return_value.aget_state_history = MagicMock(
                return_value=_async_iter(history)
            )
            mock_graph.return_value.aupdate_state = AsyncMock()
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/rollback?token={token}",
                json={"target_stage": "s1_collecting"},
            )
        assert response.status_code == 200
        assert response.json()["stage"] == "s1_collecting"

    async def test_rollback_stage_not_found(self, client: AsyncClient, token: str):
        """目标阶段不存在返回 400"""
        snap = _make_snapshot(stage="s1_collecting")
        history = [snap]
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            mock_graph.return_value.aget_state_history = MagicMock(
                return_value=_async_iter(history)
            )
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/rollback?token={token}",
                json={"target_stage": "s3_collecting"},
            )
        assert response.status_code == 400
        assert "未找到阶段" in response.json()["detail"]

    async def test_rollback_default_stage(self, client: AsyncClient, token: str):
        """不传 target_stage 默认回滚到 s1_collecting"""
        snap = _make_snapshot(stage="s1_collecting")
        history = [snap, _make_snapshot()]
        with patch("app.agent.service.get_graph") as mock_graph:
            mock_graph.return_value.aget_state = AsyncMock(return_value=snap)
            mock_graph.return_value.aget_state_history = MagicMock(
                return_value=_async_iter(history)
            )
            mock_graph.return_value.aupdate_state = AsyncMock()
            response = await client.post(
                f"/api/v1/agent/sessions/test-thread/rollback?token={token}",
                json={},
            )
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# 八、历史会话与消息测试
# ------------------------------------------------------------------ #

class TestConversations:
    """会话列表与历史消息"""

    async def test_list_conversations_empty(self, client: AsyncClient, token: str, test_user: User):
        """无历史会话返回空列表"""
        response = await client.get(f"/api/v1/agent/conversations?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_conversations_with_data(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """有历史会话正确返回"""
        conv = Conversation(
            user_id=test_user.id,
            title="thread-history-001",
            stage=ConversationStage.S1_COLLECTING,
            facts_json={},
        )
        db_session.add(conv)
        await db_session.commit()

        response = await client.get(f"/api/v1/agent/conversations?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(c["thread_id"] == "thread-history-001" for c in data)

    async def test_get_messages_empty(self, client: AsyncClient, token: str):
        """不存在的 thread_id 返回空列表"""
        response = await client.get(f"/api/v1/agent/conversations/nonexistent/messages?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_messages_with_data(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """有消息记录正确返回"""
        conv = Conversation(
            user_id=test_user.id,
            title="thread-msg-001",
            stage=ConversationStage.S1_COLLECTING,
            facts_json={},
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        msg1 = Message(conversation_id=conv.id, role=MessageRole.USER, content="我朋友被打了")
        msg2 = Message(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="请描述伤情")
        db_session.add_all([msg1, msg2])
        await db_session.commit()

        response = await client.get(f"/api/v1/agent/conversations/thread-msg-001/messages?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "我朋友被打了"
        assert data[1]["role"] == "assistant"

    async def test_get_messages_excludes_recalled(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """已撤回消息不应出现在历史中"""
        conv = Conversation(
            user_id=test_user.id,
            title="thread-recall-001",
            stage=ConversationStage.S1_COLLECTING,
            facts_json={},
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        msg1 = Message(conversation_id=conv.id, role=MessageRole.USER, content="正常消息")
        msg2 = Message(conversation_id=conv.id, role=MessageRole.USER, content="已撤回消息", is_recalled=True)
        db_session.add_all([msg1, msg2])
        await db_session.commit()

        response = await client.get(f"/api/v1/agent/conversations/thread-recall-001/messages?token={token}")
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "正常消息"

    async def test_conversations_only_own_user(
        self, client: AsyncClient, token: str, db_session: AsyncSession, test_user: User
    ):
        """只返回当前用户的会话，不返回其他用户的"""
        other_user = User(email="other@example.com", password=hash_password("pass123"))
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_conv = Conversation(
            user_id=other_user.id,
            title="other-user-thread",
            stage=ConversationStage.S1_COLLECTING,
            facts_json={},
        )
        db_session.add(other_conv)
        await db_session.commit()

        response = await client.get(f"/api/v1/agent/conversations?token={token}")
        data = response.json()
        assert not any(c["thread_id"] == "other-user-thread" for c in data)
