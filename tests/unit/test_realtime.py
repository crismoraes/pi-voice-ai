import asyncio
import base64
import json
from types import SimpleNamespace

import httpx
import numpy as np
from httpx import ASGITransport, AsyncClient

from app.api import realtime as realtime_api
from app.main import app
from app.realtime.usb import OpenAIRealtimeUsbPipeline


def test_browser_realtime_call_uses_unified_interface(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeHttpClient:
        def __init__(self, **kwargs) -> None:
            observed["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, files):
            observed.update(url=url, headers=headers, files=files)
            return httpx.Response(201, content=b"v=0\r\ns=realtime\r\n")

    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/realtime/calls",
                content="v=0\r\ns=browser\r\n",
                headers={"Content-Type": "application/sdp"},
            )

    monkeypatch.setattr(realtime_api.httpx, "AsyncClient", FakeHttpClient)
    monkeypatch.setattr(realtime_api.assistant_control, "_enabled", True)
    monkeypatch.setattr(realtime_api.voice_pipeline, "_pipeline", "openai-realtime")
    response = asyncio.run(exercise())

    assert response.status_code == 200
    assert response.text.startswith("v=0")
    assert observed["url"] == "https://api.openai.com/v1/realtime/calls"
    session = json.loads(observed["files"]["session"][1])
    assert session["model"] == "gpt-realtime-2.1"
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["turn_detection"]["type"] == "semantic_vad"
    assert "OpenAI-Safety-Identifier" in observed["headers"]


def test_browser_realtime_call_is_blocked_while_assistant_is_off(monkeypatch) -> None:
    async def exercise():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/realtime/calls",
                content="v=0\r\n",
                headers={"Content-Type": "application/sdp"},
            )

    monkeypatch.setattr(realtime_api.assistant_control, "_enabled", False)
    monkeypatch.setattr(realtime_api.voice_pipeline, "_pipeline", "openai-realtime")
    response = asyncio.run(exercise())

    assert response.status_code == 409


def test_usb_realtime_resamples_streams_audio_and_records_numeric_usage(
    monkeypatch,
) -> None:
    class AsyncAction:
        def __init__(self) -> None:
            self.audio = None

        async def clear(self):
            return None

        async def append(self, *, audio):
            self.audio = audio

        async def commit(self):
            return None

        async def create(self):
            return None

    class Event:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return self.payload

    pcm = (np.ones(240, dtype="<i2") * 1000).tobytes()
    response = {
        "id": "resp_test",
        "model": "gpt-realtime-2.1",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 8,
            "total_tokens": 20,
            "input_token_details": {
                "audio_tokens": 10,
                "text_tokens": 2,
                "cached_tokens": 4,
                "cached_tokens_details": {"audio_tokens": 3, "text_tokens": 1},
            },
            "output_token_details": {"audio_tokens": 6, "text_tokens": 2},
        },
    }
    events = [
        Event({"type": "session.created", "session": {"id": "sess_test"}}),
        Event({"type": "response.output_audio.delta", "delta": base64.b64encode(pcm).decode()}),
        Event({"type": "response.done", "response": response}),
    ]

    class Connection:
        def __init__(self) -> None:
            self.input_audio_buffer = AsyncAction()
            self.response = AsyncAction()

        def __aiter__(self):
            async def iterator():
                for event in events:
                    yield event
            return iterator()

        async def close(self):
            return None

    class Recorder:
        def __init__(self) -> None:
            self.calls = []

        async def record(self, *args):
            self.calls.append(args)
            return True

    async def exercise():
        pipeline = OpenAIRealtimeUsbPipeline(
            api_key="test",
            model_getter=lambda: "gpt-realtime-2.1",
            voice_getter=lambda: "marin",
            instructions="Be concise.",
            max_output_tokens=100,
            timeout_seconds=5,
        )
        connection = Connection()
        pipeline._client = SimpleNamespace(close=lambda: None)
        pipeline._connection_model = "gpt-realtime-2.1"
        pipeline._connection_voice = "marin"

        async def ensure_connection():
            return connection

        pipeline._ensure_connection = ensure_connection
        played = []

        async def play(synthesis):
            played.append(synthesis)

        result = await pipeline.process(
            "usb", np.ones(160, dtype=np.float32) * 0.1, lambda *_: None,
            play_audio=play,
        )
        return pipeline, connection, played, result

    recorder = Recorder()
    monkeypatch.setattr("app.realtime.usb.realtime_usage_recorder", recorder)
    pipeline, connection, played, result = asyncio.run(exercise())

    assert len(base64.b64decode(connection.input_audio_buffer.audio)) == 480
    assert played[0].sample_rate == 24_000
    assert played[0].audio_seconds == 0.01
    assert result.audio_seconds == 0.01
    assert recorder.calls[0][1].audio_input_tokens == 10
    assert recorder.calls[0][1].audio_cached_input_tokens == 3
