"""Persistent runtime selection between chained and native audio pipelines."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

PipelineHandler = Callable[[str], Awaitable[None]]


class VoicePipelineUnavailableError(RuntimeError):
    """Raised when a configured voice pipeline cannot be used."""


class VoicePipelineControl:
    """Persist an allowlisted voice pipeline, Realtime model, and voice."""

    pipelines = ("chained", "openai-realtime")

    def __init__(
        self,
        *,
        default_pipeline: str,
        selection_path: Path,
        realtime_available: bool,
        realtime_model: str,
        realtime_models: tuple[str, ...],
        realtime_voice: str,
        realtime_voices: tuple[str, ...],
    ) -> None:
        self._pipeline = default_pipeline
        self._selection_path = selection_path
        self._realtime_available = realtime_available
        self._realtime_model = realtime_model
        self._realtime_models = realtime_models
        self._realtime_voice = realtime_voice
        self._realtime_voices = realtime_voices
        self._handlers: list[PipelineHandler] = []
        self._lock = asyncio.Lock()
        self._load()

    @property
    def pipeline(self) -> str:
        return self._pipeline

    @property
    def realtime_model(self) -> str:
        return self._realtime_model

    @property
    def realtime_voice(self) -> str:
        return self._realtime_voice

    @property
    def realtime_models(self) -> tuple[str, ...]:
        return self._realtime_models

    @property
    def realtime_voices(self) -> tuple[str, ...]:
        return self._realtime_voices

    @property
    def realtime_available(self) -> bool:
        return self._realtime_available

    def register(self, handler: PipelineHandler) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    async def select(self, pipeline: str, model: str, voice: str) -> None:
        if pipeline not in self.pipelines:
            raise ValueError("Unsupported voice pipeline")
        if model not in self._realtime_models:
            raise ValueError("Unsupported Realtime model")
        if voice not in self._realtime_voices:
            raise ValueError("Unsupported Realtime voice")
        if pipeline == "openai-realtime" and not self._realtime_available:
            raise VoicePipelineUnavailableError(
                "OpenAI Realtime is unavailable; configure OPENAI_API_KEY first"
            )
        async with self._lock:
            changed = pipeline != self._pipeline
            self._pipeline = pipeline
            self._realtime_model = model
            self._realtime_voice = voice
            await asyncio.to_thread(self._save)
            if changed:
                for handler in self._handlers:
                    await handler(pipeline)

    def _load(self) -> None:
        try:
            saved = json.loads(self._selection_path.read_text(encoding="utf-8"))
            pipeline = saved["pipeline"]
            model = saved["realtime_model"]
            voice = saved["realtime_voice"]
            if (
                pipeline in self.pipelines
                and model in self._realtime_models
                and voice in self._realtime_voices
                and (pipeline != "openai-realtime" or self._realtime_available)
            ):
                self._pipeline = pipeline
                self._realtime_model = model
                self._realtime_voice = voice
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._selection_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._selection_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "pipeline": self._pipeline,
                    "realtime_model": self._realtime_model,
                    "realtime_voice": self._realtime_voice,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(self._selection_path)
