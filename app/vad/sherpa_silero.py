"""Silero VAD through sherpa-onnx."""

from pathlib import Path

import numpy as np
import sherpa_onnx

from app.vad.base import VoiceActivityDetectionUnavailableError, VoiceActivityDetector


class SherpaSileroVoiceActivityDetector(VoiceActivityDetector):
    """Detect complete utterances in a continuous 16 kHz audio stream."""

    def __init__(
        self,
        *,
        model_path: Path,
        threshold: float,
        min_silence_seconds: float,
        min_speech_seconds: float,
        max_speech_seconds: float,
        num_threads: int,
    ) -> None:
        if not model_path.is_file():
            raise VoiceActivityDetectionUnavailableError(
                f"VAD model is missing: {model_path}"
            )
        config = sherpa_onnx.VadModelConfig(
            silero_vad=sherpa_onnx.SileroVadModelConfig(
                model=str(model_path),
                threshold=threshold,
                min_silence_duration=min_silence_seconds,
                min_speech_duration=min_speech_seconds,
                window_size=512,
                max_speech_duration=max_speech_seconds,
            ),
            sample_rate=self.sample_rate,
            num_threads=num_threads,
            provider="cpu",
            debug=False,
        )
        if not config.validate():
            raise VoiceActivityDetectionUnavailableError(
                "VAD model configuration is invalid"
            )
        self._detector = sherpa_onnx.VoiceActivityDetector(
            config,
            buffer_size_in_seconds=max_speech_seconds + min_silence_seconds + 1,
        )

    @property
    def is_speech_detected(self) -> bool:
        return self._detector.is_speech_detected()

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        self._detector.accept_waveform(np.asarray(samples, dtype=np.float32))
        segments: list[np.ndarray] = []
        while not self._detector.empty():
            segments.append(np.asarray(self._detector.front.samples).copy())
            self._detector.pop()
        return segments

    def reset(self) -> None:
        self._detector.reset()
