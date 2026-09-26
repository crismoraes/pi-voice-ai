"""Offline multilingual Whisper inference through sherpa-onnx."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from app.stt.base import (
    SpeechToText,
    SpeechToTextUnavailableError,
    TranscriptionResult,
)

logger = logging.getLogger("pi_voice_ai.stt")


class SherpaWhisperSpeechToText(SpeechToText):
    """Lazy-loaded Whisper Tiny recognizer for final utterances."""

    def __init__(self, model_dir: Path, language: str, num_threads: int) -> None:
        self._model_dir = model_dir
        self._language = language
        self._num_threads = num_threads
        self._recognizer: Any | None = None
        self._decode_lock = asyncio.Lock()

    def _load_recognizer(self) -> Any:
        if self._recognizer is not None:
            return self._recognizer

        encoder = self._model_dir / "tiny-encoder.int8.onnx"
        decoder = self._model_dir / "tiny-decoder.int8.onnx"
        tokens = self._model_dir / "tiny-tokens.txt"
        missing = [path for path in (encoder, decoder, tokens) if not path.is_file()]
        if missing:
            names = ", ".join(path.name for path in missing)
            raise SpeechToTextUnavailableError(
                f"STT model is incomplete in {self._model_dir}: {names}"
            )

        started = perf_counter()
        try:
            import sherpa_onnx

            self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(encoder),
                decoder=str(decoder),
                tokens=str(tokens),
                language=self._language,
                task="transcribe",
                num_threads=self._num_threads,
                provider="cpu",
            )
        except Exception as exc:
            raise SpeechToTextUnavailableError(
                f"Unable to load STT model from {self._model_dir}"
            ) from exc

        logger.info(
            "STT_MODEL_LOADED",
            extra={
                "engine": "sherpa-whisper",
                "language": self._language,
                "seconds": round(perf_counter() - started, 3),
            },
        )
        return self._recognizer

    def _transcribe_sync(self, samples: np.ndarray) -> TranscriptionResult:
        recognizer = self._load_recognizer()
        audio = np.ascontiguousarray(samples, dtype=np.float32)
        audio_seconds = len(audio) / self.sample_rate
        started = perf_counter()
        stream = recognizer.create_stream()
        stream.accept_waveform(self.sample_rate, audio)
        recognizer.decode_stream(stream)
        processing_seconds = perf_counter() - started
        return TranscriptionResult(
            text=stream.result.text.strip(),
            audio_seconds=audio_seconds,
            processing_seconds=processing_seconds,
        )

    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        async with self._decode_lock:
            return await asyncio.to_thread(self._transcribe_sync, samples)
