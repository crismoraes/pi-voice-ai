"""Runtime-selectable text-to-speech adapter."""

from pathlib import Path

from app.runtime.model_selector import (
    PersistentRuntimeModelSelector,
    RuntimeModelOption,
)
from app.tts.base import SynthesisResult, TextToSpeech


class TextToSpeechSelector(TextToSpeech):
    """Keep every synthesis call on one selected, allowlisted TTS model."""

    def __init__(
        self,
        *,
        providers: dict[str, dict[str, RuntimeModelOption[TextToSpeech]]],
        default_provider: str,
        default_model: str,
        selection_path: Path,
    ) -> None:
        self._selector = PersistentRuntimeModelSelector(
            component="TTS",
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

    async def synthesize(self, text: str) -> SynthesisResult:
        return await self._selector.invoke(lambda adapter: adapter.synthesize(text))

    async def warm_up(self) -> None:
        await self._selector.warm_up()

    async def close(self) -> None:
        await self._selector.close()


__all__ = ["RuntimeModelOption", "TextToSpeechSelector"]
