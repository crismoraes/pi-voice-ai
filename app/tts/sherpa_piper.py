"""Local Piper voice through sherpa-onnx."""

from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter

import numpy as np
import sherpa_onnx

from app.tts.base import SynthesisResult, TextToSpeech, TextToSpeechUnavailableError


class SherpaPiperTextToSpeech(TextToSpeech):
    """Lazy-loading Portuguese Piper synthesizer."""

    def __init__(
        self,
        *,
        model_dir: Path,
        num_threads: int,
        speed: float,
        max_text_characters: int,
    ) -> None:
        self._model_dir = model_dir
        self._num_threads = num_threads
        self._speed = speed
        self._max_text_characters = max_text_characters
        self._tts: sherpa_onnx.OfflineTts | None = None
        self._load_lock = asyncio.Lock()
        self._synthesis_lock = asyncio.Lock()

    def _load(self) -> sherpa_onnx.OfflineTts:
        model = self._model_dir / "pt_BR-jeff-medium.onnx"
        tokens = self._model_dir / "tokens.txt"
        data_dir = self._model_dir / "espeak-ng-data"
        missing = [path for path in (model, tokens, data_dir) if not path.exists()]
        if missing:
            raise TextToSpeechUnavailableError(
                f"TTS model is incomplete in {self._model_dir}"
            )
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model),
                    tokens=str(tokens),
                    data_dir=str(data_dir),
                ),
                num_threads=self._num_threads,
                provider="cpu",
                debug=False,
            )
        )
        if not config.validate():
            raise TextToSpeechUnavailableError("TTS model configuration is invalid")
        return sherpa_onnx.OfflineTts(config)

    async def _get_tts(self) -> sherpa_onnx.OfflineTts:
        if self._tts is None:
            async with self._load_lock:
                if self._tts is None:
                    self._tts = await asyncio.to_thread(self._load)
        return self._tts

    async def synthesize(self, text: str) -> SynthesisResult:
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text to synthesize is empty")
        if len(normalized) > self._max_text_characters:
            raise ValueError(
                f"Text exceeds {self._max_text_characters} characters"
            )
        tts = await self._get_tts()
        async with self._synthesis_lock:
            started_at = perf_counter()
            audio = await asyncio.to_thread(
                tts.generate,
                normalized,
                0,
                self._speed,
            )
            processing_seconds = perf_counter() - started_at
        samples = np.asarray(audio.samples, dtype=np.float32)
        if len(samples) == 0:
            raise TextToSpeechUnavailableError("TTS generated no audio")
        return SynthesisResult(
            samples=samples,
            sample_rate=audio.sample_rate,
            processing_seconds=processing_seconds,
        )
