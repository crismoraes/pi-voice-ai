"""Persistent allowlisted selection for replaceable runtime models."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Generic, Protocol, TypeVar


class RuntimeModel(Protocol):
    async def warm_up(self) -> None: ...

    async def close(self) -> None: ...

    def is_available(self) -> bool: ...


ModelT = TypeVar("ModelT", bound=RuntimeModel)
ResultT = TypeVar("ResultT")
logger = logging.getLogger("pi_voice_ai.model_selector")


class RuntimeModelUnavailableError(RuntimeError):
    """Raised when a requested runtime model cannot be prepared."""


@dataclass(frozen=True, slots=True)
class RuntimeModelOption(Generic[ModelT]):
    adapter: ModelT
    label: str


class PersistentRuntimeModelSelector(Generic[ModelT]):
    """Warm, swap, persist and delegate to one allowlisted model at a time."""

    def __init__(
        self,
        *,
        component: str,
        providers: dict[str, dict[str, RuntimeModelOption[ModelT]]],
        default_provider: str,
        default_model: str,
        selection_path: Path,
    ) -> None:
        self._component = component
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
    def model_label(self) -> str:
        return self._selected_option.label

    @property
    def options(self) -> dict[str, tuple[str, ...]]:
        return {
            provider: tuple(models.keys())
            for provider, models in self._providers.items()
        }

    def label(self, provider: str, model: str) -> str:
        return self._providers[provider][model].label

    @property
    def _selected_option(self) -> RuntimeModelOption[ModelT]:
        return self._providers[self._provider][self._model]

    def _load_selection(self) -> None:
        try:
            saved = json.loads(self._selection_path.read_text(encoding="utf-8"))
            provider = saved["provider"]
            model = saved["model"]
            if (
                provider in self._providers
                and model in self._providers[provider]
                and self._providers[provider][model].adapter.is_available()
            ):
                self._provider, self._model = provider, model
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return

    async def select(self, provider: str, model: str) -> None:
        if provider not in self._providers or model not in self._providers[provider]:
            raise ValueError(f"Unsupported {self._component} provider or model")
        candidate = self._providers[provider][model].adapter
        if not candidate.is_available():
            raise RuntimeModelUnavailableError(
                f"{self._component} model {model} is not installed"
            )
        async with self._lock:
            if (provider, model) == (self._provider, self._model):
                if not self._selection_path.is_file():
                    await asyncio.to_thread(self._save_selection, provider, model)
                return
            previous = self._selected_option.adapter
            try:
                await candidate.warm_up()
                await asyncio.to_thread(self._save_selection, provider, model)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if candidate is not previous:
                    await candidate.close()
                raise RuntimeModelUnavailableError(
                    f"Unable to prepare {self._component} model {model}"
                ) from exc
            self._provider, self._model = provider, model
            if previous is not candidate:
                await previous.close()
            logger.info(
                "RUNTIME_MODEL_SELECTED",
                extra={
                    "component": self._component,
                    "provider": provider,
                    "model": model,
                },
            )

    def _save_selection(self, provider: str, model: str) -> None:
        self._selection_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._selection_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"provider": provider, "model": model},
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(self._selection_path)

    async def status(self) -> dict[str, dict[str, bool]]:
        return {
            provider: {
                model: option.adapter.is_available()
                for model, option in models.items()
            }
            for provider, models in self._providers.items()
        }

    async def warm_up(self) -> None:
        async with self._lock:
            await self._selected_option.adapter.warm_up()

    async def invoke(
        self, operation: Callable[[ModelT], Awaitable[ResultT]]
    ) -> ResultT:
        """Run one operation while preventing a model swap."""
        async with self._lock:
            return await operation(self._selected_option.adapter)

    async def close(self) -> None:
        async with self._lock:
            seen: set[int] = set()
            for models in self._providers.values():
                for option in models.values():
                    if id(option.adapter) not in seen:
                        seen.add(id(option.adapter))
                        await option.adapter.close()
