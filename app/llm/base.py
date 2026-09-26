"""Replaceable language model contract."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass


class LanguageModelError(RuntimeError):
    """Raised when a language model request cannot be completed."""


class LanguageModelUnavailableError(LanguageModelError):
    """Raised when the language model is not configured."""


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Provider-reported token counts for one completed model request."""

    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int


UsageHandler = Callable[[TokenUsage], None]


class LanguageModel(ABC):
    """Stream text responses without coupling callers to one provider."""

    @abstractmethod
    def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
        on_usage: UsageHandler | None = None,
    ) -> AsyncIterator[str]:
        """Yield response text as it becomes available."""

    async def close(self) -> None:
        """Release provider resources when the application stops."""
