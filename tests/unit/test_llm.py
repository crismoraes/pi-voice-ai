import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import assistant as assistant_api
from app.llm.base import ConversationMessage, LanguageModel, LanguageModelUnavailableError
from app.llm.openai_responses import OpenAIResponsesLanguageModel
from app.main import app


class FakeStream:
    def __init__(self, events: list[object]) -> None:
        self._events = events

    def __aiter__(self):
        self._iterator = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeResponses:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

    async def create(self, **kwargs):
        self.arguments = kwargs
        return FakeStream(
            [
                SimpleNamespace(type="response.created"),
                SimpleNamespace(type="response.output_text.delta", delta="Olá"),
                SimpleNamespace(type="response.output_text.delta", delta="!"),
                SimpleNamespace(
                    type="response.completed",
                    response=SimpleNamespace(
                        model="test-model-2026-09-01",
                        usage=SimpleNamespace(
                            input_tokens=120,
                            input_tokens_details=SimpleNamespace(cached_tokens=20),
                            output_tokens=30,
                            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
                            total_tokens=150,
                        ),
                    ),
                ),
            ]
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeLanguageModel(LanguageModel):
    model = "fake-model"

    async def stream_response(self, text: str, *, history=(), on_usage=None):
        assert text == "Como você está?"
        yield "Estou "
        yield "bem."


async def collect_model_response(model: LanguageModel, text: str) -> str:
    return "".join([chunk async for chunk in model.stream_response(text)])


def test_openai_adapter_streams_only_text_deltas() -> None:
    client = FakeOpenAIClient()
    model = OpenAIResponsesLanguageModel(
        api_key="test-key",
        model="test-model",
        instructions="Seja breve.",
        max_output_tokens=100,
        timeout_seconds=10,
        client=client,
    )

    result = asyncio.run(collect_model_response(model, "teste"))

    assert result == "Olá!"
    assert client.responses.arguments == {
        "model": "test-model",
        "instructions": "Seja breve.",
        "input": "teste",
        "max_output_tokens": 100,
        "store": False,
        "stream": True,
    }


def test_openai_adapter_requires_api_key() -> None:
    model = OpenAIResponsesLanguageModel(
        api_key=None,
        model="test-model",
        instructions="Seja breve.",
        max_output_tokens=100,
        timeout_seconds=10,
    )

    with pytest.raises(LanguageModelUnavailableError, match="OPENAI_API_KEY"):
        asyncio.run(collect_model_response(model, "teste"))


def test_openai_adapter_reports_provider_token_usage() -> None:
    client = FakeOpenAIClient()
    model = OpenAIResponsesLanguageModel(
        api_key="test-key",
        model="test-model",
        instructions="Seja breve.",
        max_output_tokens=100,
        timeout_seconds=10,
        client=client,
    )
    reported = []

    async def collect() -> str:
        return "".join(
            [
                chunk
                async for chunk in model.stream_response(
                    "teste", on_usage=reported.append
                )
            ]
        )

    assert asyncio.run(collect()) == "Olá!"
    assert reported[0].model == "test-model-2026-09-01"
    assert reported[0].input_tokens == 120
    assert reported[0].cached_input_tokens == 20
    assert reported[0].output_tokens == 30
    assert reported[0].reasoning_output_tokens == 5
    assert reported[0].total_tokens == 150


def test_openai_adapter_sends_bounded_conversation_history() -> None:
    client = FakeOpenAIClient()
    model = OpenAIResponsesLanguageModel(
        api_key="test-key",
        model="test-model",
        instructions="Seja breve.",
        max_output_tokens=100,
        timeout_seconds=10,
        client=client,
    )

    async def collect() -> str:
        history = (
            ConversationMessage(role="user", content="Meu nome é Ana."),
            ConversationMessage(role="assistant", content="Olá, Ana."),
        )
        return "".join(
            [
                chunk
                async for chunk in model.stream_response(
                    "Qual é meu nome?",
                    history=history,
                )
            ]
        )

    assert asyncio.run(collect()) == "Olá!"
    assert client.responses.arguments["input"] == [
        {"role": "user", "content": "Meu nome é Ana."},
        {"role": "assistant", "content": "Olá, Ana."},
        {"role": "user", "content": "Qual é meu nome?"},
    ]


async def request_streaming_response() -> str:
    original_model = assistant_api.language_model
    assistant_api.language_model = FakeLanguageModel()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/assistant/responses",
                json={"text": "Como você está?"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            return response.text
    finally:
        assistant_api.language_model = original_model


def test_assistant_endpoint_streams_deltas_and_metrics() -> None:
    body = asyncio.run(request_streaming_response())

    assert 'event: delta\ndata: {"text":"Estou "}' in body
    assert 'event: delta\ndata: {"text":"bem."}' in body
    assert 'event: done\ndata: {"model":"fake-model"' in body
