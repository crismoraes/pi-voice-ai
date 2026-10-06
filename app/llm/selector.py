"""Persistent, allowlisted runtime language model selection."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

from app.llm.base import (
    ConversationMessage,
    LanguageModel,
    LanguageModelUnavailableError,
    UsageHandler,
)


class LanguageModelSelector(LanguageModel):
    """Delegate each complete request to the selected provider and model."""

    def __init__(
        self,
        *,
        providers: dict[str, dict[str, LanguageModel]],
        default_provider: str,
        default_model: str,
        selection_path: Path,
    ) -> None:
        self._providers = providers
        self._selection_path = selection_path
        self._lock = asyncio.Lock()
        self._provider = default_provider
        self._model = default_model
        self._load_selection()

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def options(self) -> dict[str, tuple[str, ...]]:
        return {
            provider: tuple(models.keys())
            for provider, models in self._providers.items()
        }

    def _load_selection(self) -> None:
        try:
            saved = json.loads(self._selection_path.read_text(encoding="utf-8"))
            provider = saved["provider"]
            model = saved["model"]
            if provider in self._providers and model in self._providers[provider]:
                self._provider, self._model = provider, model
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return

    async def select(self, provider: str, model: str) -> None:
        if provider not in self._providers or model not in self._providers[provider]:
            raise ValueError("Unsupported LLM provider or model")
        candidate = self._providers[provider][model]
        readiness = getattr(candidate, "is_ready", None)
        if readiness is not None and not await readiness():
            raise LanguageModelUnavailableError(
                f"{provider} is not ready; keep the current selection and check its service"
            )
        async with self._lock:
            self._provider, self._model = provider, model
            await asyncio.to_thread(self._save_selection)

    def _save_selection(self) -> None:
        self._selection_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._selection_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"provider": self._provider, "model": self._model},
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(self._selection_path)

    async def status(self) -> dict[str, bool]:
        availability: dict[str, bool] = {}
        for provider, models in self._providers.items():
            candidate = next(iter(models.values()))
            readiness = getattr(candidate, "is_ready", None)
            availability[provider] = True if readiness is None else await readiness()
        return availability

    def metric(self, provider: str, name: str) -> object | None:
        candidate = next(iter(self._providers[provider].values()))
        return getattr(candidate, name, None)

    async def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
        on_usage: UsageHandler | None = None,
    ) -> AsyncIterator[str]:
        async with self._lock:
            selected = self._providers[self._provider][self._model]
            async for delta in selected.stream_response(
                text, history=history, on_usage=on_usage
            ):
                yield delta

    async def stream_response_for(
        self, provider: str, model: str, text: str, *, history: tuple[ConversationMessage, ...] = (), on_usage: UsageHandler | None = None
    ) -> AsyncIterator[str]:
        """Run one request on an explicit provider without changing dashboard state."""
        if provider not in self._providers or model not in self._providers[provider]:
            raise LanguageModelUnavailableError("Requested story model is unavailable")
        async with self._lock:
            async for delta in self._providers[provider][model].stream_response(text, history=history, on_usage=on_usage):
                yield delta

    async def close(self) -> None:
        seen: set[int] = set()
        for models in self._providers.values():
            for model in models.values():
                if id(model) not in seen:
                    seen.add(id(model))
                    await model.close()
