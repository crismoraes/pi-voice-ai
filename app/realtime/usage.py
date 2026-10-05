"""Sanitized Realtime token parsing and persistence."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass

from app.llm.base import TokenUsage
from app.usage.store import UsageStore, UsageTurn


@dataclass(frozen=True, slots=True)
class RealtimeTurnUsage:
    response_id: str
    session_id: str | None
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    text_input_tokens: int
    text_cached_input_tokens: int
    text_output_tokens: int
    audio_input_tokens: int
    audio_cached_input_tokens: int
    audio_output_tokens: int
    first_audio_seconds: float | None = None
    total_seconds: float | None = None


class RealtimeUsageRecorder:
    """Record each Realtime response once without retaining conversation content."""

    def __init__(self, usage_store: UsageStore, max_seen: int = 1000) -> None:
        self._usage_store = usage_store
        self._seen: set[str] = set()
        self._order: deque[str] = deque()
        self._max_seen = max_seen
        self._lock = asyncio.Lock()

    async def record(self, source: str, usage: RealtimeTurnUsage, voice: str) -> bool:
        async with self._lock:
            if usage.response_id in self._seen:
                return False
            token_usage = TokenUsage(
                model=usage.model,
                input_tokens=usage.input_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_output_tokens=0,
                total_tokens=usage.total_tokens,
            )
            await asyncio.to_thread(
                self._usage_store.record,
                UsageTurn(
                    source=source,
                    session_id=usage.session_id,
                    usage=token_usage,
                    first_text_seconds=usage.first_audio_seconds,
                    total_seconds=usage.total_seconds,
                    pipeline="openai-realtime",
                    llm_provider="openai",
                    tts_provider="openai",
                    tts_model=voice,
                    audio_input_tokens=usage.audio_input_tokens,
                    audio_cached_input_tokens=usage.audio_cached_input_tokens,
                    audio_output_tokens=usage.audio_output_tokens,
                    text_input_tokens=usage.text_input_tokens,
                    text_cached_input_tokens=usage.text_cached_input_tokens,
                    text_output_tokens=usage.text_output_tokens,
                ),
            )
            self._seen.add(usage.response_id)
            self._order.append(usage.response_id)
            while len(self._order) > self._max_seen:
                self._seen.discard(self._order.popleft())
        return True
