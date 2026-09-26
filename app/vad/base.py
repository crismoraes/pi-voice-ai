"""Replaceable voice activity detection contract."""

from abc import ABC, abstractmethod

import numpy as np


class VoiceActivityDetectionUnavailableError(RuntimeError):
    """Raised when voice activity detection cannot run."""


class VoiceActivityDetector(ABC):
    """Split a continuous 16 kHz mono stream into speech segments."""

    sample_rate = 16_000

    @property
    @abstractmethod
    def is_speech_detected(self) -> bool:
        """Return whether the current stream position contains speech."""

    @abstractmethod
    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        """Accept float32 samples and return newly completed utterances."""

    @abstractmethod
    def reset(self) -> None:
        """Discard buffered samples and start a fresh stream."""
