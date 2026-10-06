"""Persistent runtime instructions shared by every language model pipeline."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path


class PromptControl:
    """Validate and persist the assistant instructions and their revision."""

    def __init__(
        self,
        *,
        default_instructions: str,
        state_path: Path,
        max_characters: int,
    ) -> None:
        self._default_instructions = default_instructions.strip()
        self._instructions = self._default_instructions
        self._state_path = state_path
        self._max_characters = max_characters
        self._revision = 0
        self._lock = asyncio.Lock()
        self._load()

    @property
    def instructions(self) -> str:
        return self._instructions

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def is_default(self) -> bool:
        return self._instructions == self._default_instructions

    @property
    def max_characters(self) -> int:
        return self._max_characters

    async def set_instructions(self, instructions: str) -> None:
        normalized = instructions.strip()
        if not normalized:
            raise ValueError("Assistant behavior cannot be empty")
        if len(normalized) > self._max_characters:
            raise ValueError(
                f"Assistant behavior cannot exceed {self._max_characters} characters"
            )
        async with self._lock:
            if normalized == self._instructions:
                return
            revision = self._revision + 1
            await asyncio.to_thread(self._save, normalized, revision)
            self._instructions = normalized
            self._revision = revision

    async def reset(self) -> None:
        await self.set_instructions(self._default_instructions)

    def _load(self) -> None:
        try:
            saved = json.loads(self._state_path.read_text(encoding="utf-8"))
            instructions = saved.get("instructions")
            revision = saved.get("revision")
            if (
                isinstance(instructions, str)
                and instructions.strip()
                and len(instructions.strip()) <= self._max_characters
                and isinstance(revision, int)
                and not isinstance(revision, bool)
                and revision >= 0
            ):
                self._instructions = instructions.strip()
                self._revision = revision
        except (OSError, AttributeError, json.JSONDecodeError):
            return

    def _save(self, instructions: str, revision: int) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "instructions": instructions,
                    "revision": revision,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(self._state_path)
