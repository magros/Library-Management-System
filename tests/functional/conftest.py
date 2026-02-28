"""
Shared fixtures for functional tests.
Uses httpx.AsyncClient against the real FastAPI app with an in-memory SQLite DB.
"""
from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base, User, UserRole
from app.core.security import hash_password
from app.db import session as db_session_module
from app.main import app


# ─── DB override ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine for functional testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(test_session_factory):
    """Provide an httpx.AsyncClient with DB overridden to use the test DB."""

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[db_session_module.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Auth helpers ───────────────────────────────────────────────

@pytest_asyncio.fixture
async def registered_member(client: AsyncClient):
    """Register a member user and return (user_data, token)."""
    data = {
        "email": f"member-{uuid4().hex[:6]}@test.com",
        "password": "password123",
        "full_name": "Test Member",
    }
    resp = await client.post("/api/v1/auth/register", json=data)
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {**data, "token": token}


@pytest_asyncio.fixture
async def admin_user(client: AsyncClient, test_session_factory):
    """Create an admin user directly in DB and return (user_data, token)."""
    async with test_session_factory() as session:
        admin = User(
            id=str(uuid4()),
            email=f"admin-{uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("adminpass123"),
            full_name="Test Admin",
            role=UserRole.ADMIN,
            is_built_in=False,
            is_active=True,
        )
        session.add(admin)
        await session.commit()

    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": admin.email, "password": "adminpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"id": admin.id, "email": admin.email, "token": token, "role": "admin"}


@pytest_asyncio.fixture
async def librarian_user(client: AsyncClient, test_session_factory):
    """Create a librarian user directly in DB and return (user_data, token)."""
    async with test_session_factory() as session:
        librarian = User(
            id=str(uuid4()),
            email=f"librarian-{uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("libpass123"),
            full_name="Test Librarian",
            role=UserRole.LIBRARIAN,
            is_built_in=False,
            is_active=True,
        )
        session.add(librarian)
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": librarian.email, "password": "libpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"id": librarian.id, "email": librarian.email, "token": token, "role": "librarian"}


@pytest_asyncio.fixture
async def built_in_admin(client: AsyncClient, test_session_factory):
    """Create the built-in admin user (cannot be deleted)."""
    async with test_session_factory() as session:
        admin = User(
            id=str(uuid4()),
            email="builtin-admin@library.com",
            hashed_password=hash_password("builtinpass123"),
            full_name="Built-in Admin",
            role=UserRole.ADMIN,
            is_built_in=True,
            is_active=True,
        )
        session.add(admin)
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "builtin-admin@library.com", "password": "builtinpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"id": admin.id, "email": admin.email, "token": token, "is_built_in": True}


def auth_header(token: str) -> dict:
    """Return an Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}

