# 用户接口测试
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.security import hash_password
from app.db.database import get_db
from app.models.models import User
from main import create_app

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    """创建内存测试数据库会话"""
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
    """创建测试客户端"""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(email="test@example.com", password=hash_password("password123"), nickname="测试用户")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestRegister:
    """测试用户注册"""

    async def test_register_success(self, client: AsyncClient):
        """注册成功"""
        response = await client.post("/api/v1/user/register", json={"email": "new@example.com", "password": "password123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """邮箱重复注册"""
        response = await client.post("/api/v1/user/register", json={"email": "test@example.com", "password": "password123"})
        assert response.status_code == 400
        assert "该邮箱已注册" in response.json()["detail"]

    async def test_register_invalid_email(self, client: AsyncClient):
        """无效邮箱格式"""
        response = await client.post("/api/v1/user/register", json={"email": "not-an-email", "password": "password123"})
        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        """密码过短"""
        response = await client.post("/api/v1/user/register", json={"email": "new@example.com", "password": "123"})
        assert response.status_code == 422


class TestLogin:
    """测试用户登录"""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """登录成功"""
        response = await client.post("/api/v1/user/login", json={"email": "test@example.com", "password": "password123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """密码错误"""
        response = await client.post("/api/v1/user/login", json={"email": "test@example.com", "password": "wrongpassword"})
        assert response.status_code == 401
        assert "邮箱或密码错误" in response.json()["detail"]

    async def test_login_user_not_exist(self, client: AsyncClient):
        """用户不存在"""
        response = await client.post("/api/v1/user/login", json={"email": "noone@example.com", "password": "password123"})
        assert response.status_code == 401

    async def test_login_invalid_email(self, client: AsyncClient):
        """无效邮箱格式"""
        response = await client.post("/api/v1/user/login", json={"email": "invalid", "password": "password123"})
        assert response.status_code == 422


class TestOAuth2Login:
    """测试 OAuth2 表单登录"""

    async def test_access_token_success(self, client: AsyncClient, test_user: User):
        """Swagger UI 表单登录成功"""
        response = await client.post("/api/v1/user/access-token", data={"username": "test@example.com", "password": "password123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_access_token_wrong_password(self, client: AsyncClient, test_user: User):
        """Swagger UI 表单登录密码错误"""
        response = await client.post("/api/v1/user/access-token", data={"username": "test@example.com", "password": "wrong"})
        assert response.status_code == 401


class TestUpdateMe:
    """测试更新用户信息"""

    async def test_update_me_success(self, client: AsyncClient, test_user: User):
        """更新昵称和头像"""
        login = await client.post("/api/v1/user/login", json={"email": "test@example.com", "password": "password123"})
        token = login.json()["access_token"]
        response = await client.put("/api/v1/user/me", json={"nickname": "新昵称", "avatar": "https://example.com/new.png"}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["nickname"] == "新昵称"
        assert data["avatar"] == "https://example.com/new.png"

    async def test_update_me_partial(self, client: AsyncClient, test_user: User):
        """只更新昵称"""
        login = await client.post("/api/v1/user/login", json={"email": "test@example.com", "password": "password123"})
        token = login.json()["access_token"]
        response = await client.put("/api/v1/user/me", json={"nickname": "只改昵称"}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["nickname"] == "只改昵称"

    async def test_update_me_no_token(self, client: AsyncClient):
        """无 Token 更新"""
        response = await client.put("/api/v1/user/me", json={"nickname": "test"})
        assert response.status_code == 401


class TestGetMe:
    """测试获取当前用户"""

    async def test_get_me_success(self, client: AsyncClient, test_user: User):
        """携带有效 Token 获取用户信息"""
        login = await client.post("/api/v1/user/login", json={"email": "test@example.com", "password": "password123"})
        token = login.json()["access_token"]
        response = await client.get("/api/v1/user/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_get_me_no_token(self, client: AsyncClient):
        """无 Token 访问"""
        response = await client.get("/api/v1/user/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        """无效 Token"""
        response = await client.get("/api/v1/user/me", headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == 401
