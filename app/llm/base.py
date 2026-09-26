"""Replaceable language model contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


class LanguageModelError(RuntimeError):
    """Raised when a language model request cannot be completed."""


class LanguageModelUnavailableError(LanguageModelError):
    """Raised when the language model is not configured."""


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str


class LanguageModel(ABC):
    """Stream text responses without coupling callers to one provider."""

    @abstractmethod
    def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
    ) -> AsyncIterator[str]:
        """Yield response text as it becomes available."""

    async def close(self) -> None:
        """Release provider resources when the application stops."""
