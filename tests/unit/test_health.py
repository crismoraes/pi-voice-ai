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
    assert "Assistente de voz" in response.text


def test_system_info_exposes_models_without_secrets_or_paths() -> None:
    async def get_system_info():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/system/info")

    response = asyncio.run(get_system_info())
    payload = response.json()
    serialized = response.text.lower()

    assert response.status_code == 200
    assert payload["llm"]["model"]
    assert payload["llm"]["provider"] in {"openai", "llama.cpp"}
    assert {item["provider"] for item in payload["llm"]["options"]} == {
        "openai",
        "llama.cpp",
    }
    assert payload["stt"]["model"].startswith("Whisper ")
    assert payload["tts"]["model"]
    assert payload["audio"]["mode"] in {"usb", "webrtc"}
    assert "api_key" not in serialized
    assert "openai_api_key" not in serialized
    assert "/home/" not in serialized
    assert "c:\\" not in serialized


def test_dashboard_contains_active_technology_panel() -> None:
    async def get_dashboard():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/dashboard.html")

    response = asyncio.run(get_dashboard())

    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    assert "Active technology" in response.text
    assert "LLM provider" in response.text
    assert "Consumo" not in response.text
    assert 'id="tech-llm"' in response.text
    assert 'id="tech-stt"' in response.text
    assert 'id="tech-tts"' in response.text
