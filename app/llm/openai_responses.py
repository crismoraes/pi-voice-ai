"""OpenAI Responses API adapter."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.llm.base import (
    ConversationMessage,
    LanguageModel,
    LanguageModelError,
    LanguageModelUnavailableError,
)


class OpenAIResponsesLanguageModel(LanguageModel):
    """Generate streaming text with the OpenAI Responses API."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        instructions: str,
        max_output_tokens: int,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._instructions = instructions
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._request_lock = asyncio.Lock()

    def _get_client(self) -> AsyncOpenAI:
        if not self._api_key:
            raise LanguageModelUnavailableError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                timeout=self._timeout_seconds,
                max_retries=1,
            )
        return self._client

    async def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
    ) -> AsyncIterator[str]:
        model_input: str | list[dict[str, str]] = text
        if history:
            model_input = [
                {"role": message.role, "content": message.content}
                for message in history
            ]
            model_input.append({"role": "user", "content": text})
        try:
            async with self._request_lock:
                stream = await self._get_client().responses.create(
                    model=self.model,
                    instructions=self._instructions,
                    input=model_input,
                    max_output_tokens=self._max_output_tokens,
                    store=False,
                    stream=True,
                )
                async for event in stream:
                    if event.type == "response.output_text.delta" and event.delta:
                        yield event.delta
                    elif event.type == "error":
                        raise LanguageModelError("OpenAI stream failed")
        except LanguageModelUnavailableError:
            raise
        except OpenAIError as exc:
            raise LanguageModelError("OpenAI request failed") from exc

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
