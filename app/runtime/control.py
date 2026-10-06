"""Persistent global on/off control for voice processing."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

StateHandler = Callable[[bool], Awaitable[None]]
InterruptHandler = Callable[[], Awaitable[bool]]


class AssistantControl:
    """Persist state and notify transports when voice processing changes."""

    def __init__(self, *, enabled: bool, state_path: Path) -> None:
        self._enabled = enabled
        self._state_path = state_path
        self._handlers: list[StateHandler] = []
        self._lock = asyncio.Lock()
        self._load()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def register(self, handler: StateHandler) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    async def set_enabled(self, enabled: bool) -> None:
        async with self._lock:
            if enabled == self._enabled:
                return
            self._enabled = enabled
            await asyncio.to_thread(self._save)
            for handler in self._handlers:
                await handler(enabled)

    def _load(self) -> None:
        try:
            saved = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(saved.get("enabled"), bool):
                self._enabled = saved["enabled"]
        except (OSError, AttributeError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"enabled": self._enabled}, separators=(",", ":")),
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(self._state_path)


class VoiceInterruptControl:
    """Route a manual stop request to the active local audio transport."""

    def __init__(self) -> None:
        self._handler: InterruptHandler | None = None

    @property
    def available(self) -> bool:
        return self._handler is not None

    def register(self, handler: InterruptHandler) -> None:
        self._handler = handler

    async def interrupt(self) -> bool:
        if self._handler is None:
            return False
        return await self._handler()
