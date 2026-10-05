"""Replaceable speech-to-text contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Text and timing measurements produced for one utterance."""

    text: str
    audio_seconds: float
    processing_seconds: float

    @property
    def real_time_factor(self) -> float:
        if self.audio_seconds == 0:
            return 0.0
        return self.processing_seconds / self.audio_seconds


class SpeechToText(ABC):
    """Convert mono floating-point audio into text."""

    sample_rate = 16_000

    @abstractmethod
    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        """Transcribe a complete utterance without blocking the event loop."""

    async def warm_up(self) -> None:
        """Prepare the selected model before it receives audio."""

    async def close(self) -> None:
        """Release model resources when it is replaced or the app stops."""

    def is_available(self) -> bool:
        """Return whether the configured model files appear usable."""
        return True


class SpeechToTextUnavailableError(RuntimeError):
    """Raised when the configured local model cannot be loaded."""
