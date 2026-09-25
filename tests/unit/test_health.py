import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")


def test_health_is_available_without_external_services() -> None:
    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith("application/json")


async def get_home_page():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/")


def test_browser_client_is_served() -> None:
    response = asyncio.run(get_home_page())

    assert response.status_code == 200
    assert "Teste de áudio WebRTC" in response.text
