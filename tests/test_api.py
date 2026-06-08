"""Basic health and smoke tests for OASIS-X API."""
import pytest
from httpx import AsyncClient, ASGITransport

from api.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_status(client):
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "SWIFT FHS"


@pytest.mark.asyncio
async def test_login_unauthorized(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_llm_status(client):
    resp = await client.get("/api/llm-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data


@pytest.mark.asyncio
async def test_login_page(client):
    resp = await client.get("/login")
    assert resp.status_code == 200
    assert "OASIS-X" in resp.text


@pytest.mark.asyncio
async def test_docs_page(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200
