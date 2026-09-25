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
