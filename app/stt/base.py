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


class SpeechToTextUnavailableError(RuntimeError):
    """Raised when the configured local model cannot be loaded."""
