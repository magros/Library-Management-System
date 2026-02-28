"""
Unit tests for app.main – health check endpoint, request middleware.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def test_client():
    """Simple test client without DB overrides (for endpoints that don't need DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, test_client):
        resp = await test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_includes_version(self, test_client):
        resp = await test_client.get("/health")
        assert "version" in resp.json()


class TestRequestMiddleware:
    @pytest.mark.asyncio
    async def test_response_has_request_id_header(self, test_client):
        resp = await test_client.get("/health")
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio
    async def test_request_id_is_string(self, test_client):
        resp = await test_client.get("/health")
        req_id = resp.headers.get("x-request-id")
        assert isinstance(req_id, str)
        assert len(req_id) > 0


class TestOpenAPISpec:
    @pytest.mark.asyncio
    async def test_docs_endpoint_accessible(self, test_client):
        resp = await test_client.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc_endpoint_accessible(self, test_client):
        resp = await test_client.get("/redoc")
        assert resp.status_code == 200

