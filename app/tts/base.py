"""Replaceable local text-to-speech contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class TextToSpeechUnavailableError(RuntimeError):
    """Raised when local speech synthesis cannot run."""


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    samples: np.ndarray
    sample_rate: int
    processing_seconds: float

    @property
    def audio_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    @property
    def real_time_factor(self) -> float:
        if self.audio_seconds == 0:
            return 0.0
        return self.processing_seconds / self.audio_seconds


class TextToSpeech(ABC):
    """Synthesize mono float32 audio from text."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesisResult:
        """Generate speech without blocking the event loop."""

    async def warm_up(self) -> None:
        """Prepare the selected voice before it receives text."""

    async def close(self) -> None:
        """Release model resources when it is replaced or the app stops."""

    def is_available(self) -> bool:
        """Return whether the configured voice files appear usable."""
        return True
