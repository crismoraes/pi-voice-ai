"""Runtime-selectable speech-to-text adapter."""

from pathlib import Path

import numpy as np

from app.runtime.model_selector import (
    PersistentRuntimeModelSelector,
    RuntimeModelOption,
)
from app.stt.base import SpeechToText, TranscriptionResult


class SpeechToTextSelector(SpeechToText):
    """Keep every transcription on one selected, allowlisted STT model."""

    def __init__(
        self,
        *,
        providers: dict[str, dict[str, RuntimeModelOption[SpeechToText]]],
        default_provider: str,
        default_model: str,
        selection_path: Path,
    ) -> None:
        self._selector = PersistentRuntimeModelSelector(
            component="STT",
            providers=providers,
            default_provider=default_provider,
            default_model=default_model,
            selection_path=selection_path,
        )

    @property
    def provider(self) -> str:
        return self._selector.provider

    @property
    def model(self) -> str:
        return self._selector.model

    @property
    def model_label(self) -> str:
        return self._selector.model_label

    @property
    def options(self) -> dict[str, tuple[str, ...]]:
        return self._selector.options

    def label(self, provider: str, model: str) -> str:
        return self._selector.label(provider, model)

    async def status(self) -> dict[str, dict[str, bool]]:
        return await self._selector.status()

    async def select(self, provider: str, model: str) -> None:
        await self._selector.select(provider, model)

    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        return await self._selector.invoke(lambda adapter: adapter.transcribe(samples))

    async def warm_up(self) -> None:
        await self._selector.warm_up()

    async def close(self) -> None:
        await self._selector.close()


__all__ = ["RuntimeModelOption", "SpeechToTextSelector"]
