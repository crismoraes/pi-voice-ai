"""Streaming adapter for a loopback-only llama.cpp server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import (
    ConversationMessage,
    LanguageModel,
    LanguageModelError,
    LanguageModelUnavailableError,
    TokenUsage,
    UsageHandler,
)


class LlamaCppLanguageModel(LanguageModel):
    """Use llama-server's OpenAI-compatible chat completions endpoint."""

    provider = "llama.cpp"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        instructions: str,
        max_output_tokens: int,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._instructions = instructions
        self._max_output_tokens = max_output_tokens
        self._request_lock = asyncio.Lock()
        normalized = base_url.rstrip("/")
        self._server_url = normalized.removesuffix("/v1")
        self._client = client or httpx.AsyncClient(
            base_url=f"{normalized}/",
            timeout=httpx.Timeout(timeout_seconds, connect=3),
            trust_env=False,
        )
        self._owns_client = client is None
        self.last_tokens_per_second: float | None = None

    async def is_ready(self) -> bool:
        try:
            response = await self._client.get(f"{self._server_url}/health", timeout=2)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
        on_usage: UsageHandler | None = None,
    ) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": self._instructions}]
        messages.extend(
            {"role": message.role, "content": message.content} for message in history
        )
        messages.append({"role": "user", "content": text})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self._max_output_tokens,
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "presence_penalty": 1.5,
            "stream": True,
            "stream_options": {"include_usage": True},
            "cache_prompt": True,
            "reasoning_effort": "none",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            async with self._request_lock:
                async with self._client.stream(
                    "POST", "chat/completions", json=payload
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        raise LanguageModelError(
                            f"Local LLM returned HTTP {response.status_code}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        chunk = json.loads(data)
                        timings = chunk.get("timings") or {}
                        if "predicted_per_second" in timings:
                            self.last_tokens_per_second = float(
                                timings["predicted_per_second"]
                            )
                        usage = chunk.get("usage")
                        if usage and on_usage is not None:
                            prompt_details = usage.get("prompt_tokens_details") or {}
                            on_usage(
                                TokenUsage(
                                    model=chunk.get("model", self.model),
                                    input_tokens=int(usage.get("prompt_tokens", 0)),
                                    cached_input_tokens=int(
                                        prompt_details.get("cached_tokens", 0)
                                    ),
                                    output_tokens=int(
                                        usage.get("completion_tokens", 0)
                                    ),
                                    reasoning_output_tokens=0,
                                    total_tokens=int(usage.get("total_tokens", 0)),
                                )
                            )
                        choices = chunk.get("choices") or []
                        if choices:
                            content = (choices[0].get("delta") or {}).get("content")
                            if content:
                                yield content
        except LanguageModelError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LanguageModelUnavailableError(
                "The local llama.cpp server is unavailable"
            ) from exc

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
