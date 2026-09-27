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
    """Lazy-loaded Whisper recognizer for final utterances."""

    def __init__(
        self,
        model_dir: Path,
        language: str,
        num_threads: int,
        precision: str = "int8",
        normalize_audio: bool = True,
        target_peak: float = 0.8,
        max_gain: float = 12,
    ) -> None:
        self._model_dir = model_dir
        self._language = language
        self._num_threads = num_threads
        self._precision = precision
        self._normalize_audio = normalize_audio
        self._target_peak = target_peak
        self._max_gain = max_gain
        self._recognizer: Any | None = None
        self._decode_lock = asyncio.Lock()

    def _load_recognizer(self) -> Any:
        if self._recognizer is not None:
            return self._recognizer

        token_files = sorted(self._model_dir.glob("*-tokens.txt"))
        tokens = token_files[0] if len(token_files) == 1 else self._model_dir / "tokens"
        prefix = tokens.name.removesuffix("-tokens.txt")
        precision_suffix = ".int8" if self._precision == "int8" else ""
        encoder = self._model_dir / f"{prefix}-encoder{precision_suffix}.onnx"
        decoder = self._model_dir / f"{prefix}-decoder{precision_suffix}.onnx"
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
                "precision": self._precision,
                "seconds": round(perf_counter() - started, 3),
            },
        )
        return self._recognizer

    def _transcribe_sync(self, samples: np.ndarray) -> TranscriptionResult:
        recognizer = self._load_recognizer()
        audio = np.ascontiguousarray(samples, dtype=np.float32)
        audio_seconds = len(audio) / self.sample_rate
        if self._normalize_audio and len(audio):
            input_peak = float(np.max(np.abs(audio)))
            gain = (
                min(self._max_gain, self._target_peak / input_peak)
                if 0 < input_peak < self._target_peak
                else 1.0
            )
            if gain > 1:
                audio = np.clip(audio * gain, -1.0, 1.0)
            logger.info(
                "STT_AUDIO_NORMALIZED",
                extra={
                    "input_peak": round(input_peak, 4),
                    "gain": round(gain, 2),
                    "output_peak": round(float(np.max(np.abs(audio))), 4),
                },
            )
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

    async def warm_up(self) -> None:
        """Load model weights before the first utterance."""
        await asyncio.to_thread(self._load_recognizer)
