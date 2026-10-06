import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.runtime.prompt import PromptControl


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
    assert 'id="avatar"' in response.text
    assert 'id="avatar-mouth"' in response.text
    assert 'id="avatar-state"' in response.text


def test_system_info_exposes_models_without_secrets_or_paths() -> None:
    async def get_system_info():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/system/info")

    response = asyncio.run(get_system_info())
    payload = response.json()
    serialized = response.text.lower()

    assert response.status_code == 200
    assert isinstance(payload["assistant"]["enabled"], bool)
    assert isinstance(payload["assistant"]["interrupt_available"], bool)
    assert isinstance(payload["prompt"]["revision"], int)
    assert isinstance(payload["prompt"]["is_default"], bool)
    assert payload["prompt"]["max_characters"] == 8000
    assert "instructions" not in payload["prompt"]
    assert payload["pipeline"]["id"] in {"chained", "openai-realtime"}
    assert payload["pipeline"]["realtime_model"] == "gpt-realtime-2.1"
    assert payload["pipeline"]["realtime_models"] == [
        "gpt-realtime-2.1",
        "gpt-realtime-2.1-mini",
    ]
    assert payload["pipeline"]["max_output_tokens"] == 2048
    assert "marin" in payload["pipeline"]["realtime_voices"]
    assert payload["llm"]["model"]
    assert payload["llm"]["provider"] in {"openai", "llama.cpp"}
    assert {item["provider"] for item in payload["llm"]["options"]} == {
        "openai",
        "llama.cpp",
    }
    assert payload["stt"]["model_label"].startswith("Whisper ")
    assert payload["stt"]["provider"] == "sherpa-onnx"
    assert len(payload["stt"]["options"][0]["models"]) == 2
    assert payload["tts"]["model_label"]
    assert payload["tts"]["provider"] == "sherpa-onnx"
    assert payload["tts"]["options"][0]["models"]
    assert payload["audio"]["mode"] in {"usb", "webrtc"}
    assert isinstance(payload["audio"]["barge_in"], bool)
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
    assert "STT provider" in response.text
    assert "TTS provider" in response.text
    assert 'id="turn-list"' in response.text
    assert "without horizontal scrolling" in response.text
    assert "Voice pipeline" in response.text
    assert 'id="apply-pipeline"' in response.text
    assert "Voice assistant" in response.text
    assert 'id="assistant-enabled"' in response.text
    assert 'id="interrupt-assistant"' in response.text
    assert 'id="assistant-prompt"' in response.text
    assert 'id="behavior-template"' in response.text
    assert "Storyteller in Portuguese" in response.text
    assert "English teacher" in response.text
    assert 'id="save-prompt"' in response.text
    assert 'id="reset-prompt"' in response.text
    assert "Consumo" not in response.text
    assert 'id="tech-llm"' in response.text
    assert 'id="tech-stt"' in response.text
    assert 'id="tech-tts"' in response.text
    assert 'id="apply-stt"' in response.text
    assert 'id="apply-tts"' in response.text


def test_prompt_api_updates_and_resets_persistent_behavior(monkeypatch, tmp_path) -> None:
    control = PromptControl(
        default_instructions="Default behavior.",
        state_path=tmp_path / "prompt.json",
        max_characters=100,
    )
    monkeypatch.setattr("app.api.system.prompt_control", control)

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            initial = await client.get("/api/system/prompt")
            updated = await client.put(
                "/api/system/prompt", json={"instructions": "Custom behavior."}
            )
            reset = await client.post("/api/system/prompt/reset")
            invalid = await client.put(
                "/api/system/prompt", json={"instructions": "x" * 101}
            )
            return initial, updated, reset, invalid

    initial, updated, reset, invalid = asyncio.run(exercise())

    assert initial.json()["instructions"] == "Default behavior."
    assert updated.json() == {
        "instructions": "Custom behavior.",
        "revision": 1,
        "is_default": False,
        "max_characters": 100,
    }
    assert reset.json()["instructions"] == "Default behavior."
    assert reset.json()["revision"] == 2
    assert invalid.status_code == 422


def test_manual_interrupt_endpoint_reports_active_response(monkeypatch) -> None:
    async def interrupt() -> bool:
        return True

    monkeypatch.setattr("app.api.system.voice_interrupt_control._handler", interrupt)

    async def request_interrupt():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/api/system/assistant/interrupt")

    response = asyncio.run(request_interrupt())

    assert response.status_code == 200
    assert response.json() == {"interrupted": True}


def test_system_rejects_unlisted_voice_models(monkeypatch) -> None:
    monkeypatch.setattr("app.api.system.voice_pipeline._pipeline", "chained")

    async def select_invalid_models():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            stt = await client.put(
                "/api/system/stt",
                json={"provider": "unknown", "model": "unknown"},
            )
            tts = await client.put(
                "/api/system/tts",
                json={"provider": "unknown", "model": "unknown"},
            )
            return stt, tts

    stt, tts = asyncio.run(select_invalid_models())

    assert stt.status_code == 422
    assert tts.status_code == 422
