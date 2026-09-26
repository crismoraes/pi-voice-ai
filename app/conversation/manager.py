"""Transport-independent STT, LLM and TTS conversation pipeline."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from app.llm.base import ConversationMessage, LanguageModel
from app.stt.base import SpeechToText, TranscriptionResult
from app.tts.base import SynthesisResult, TextToSpeech

logger = logging.getLogger("pi_voice_ai.conversation")
EventHandler = Callable[[str, dict[str, object]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ConversationResult:
    transcription: TranscriptionResult
    response_text: str
    first_text_seconds: float
    total_text_seconds: float
    synthesis: SynthesisResult


@dataclass(slots=True)
class ConversationState:
    history: list[ConversationMessage] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConversationManager:
    """Run complete turns while keeping bounded context for each audio session."""

    def __init__(
        self,
        *,
        speech_to_text: SpeechToText,
        language_model: LanguageModel,
        text_to_speech: TextToSpeech,
        max_turns: int,
    ) -> None:
        self._speech_to_text = speech_to_text
        self._language_model = language_model
        self._text_to_speech = text_to_speech
        self._max_messages = max_turns * 2
        self._states: dict[str, ConversationState] = {}

    def forget(self, session_id: str) -> None:
        self._states.pop(session_id, None)

    async def process(
        self,
        session_id: str,
        samples: np.ndarray,
        emit: EventHandler,
    ) -> ConversationResult | None:
        state = self._states.setdefault(session_id, ConversationState())
        async with state.lock:
            await emit("transcribing", {})
            logger.info(
                "CONVERSATION_STT_STARTED",
                extra={
                    "peer_id": session_id,
                    "audio_seconds": round(len(samples) / 16_000, 3),
                },
            )
            transcription = await self._speech_to_text.transcribe(samples)
            await emit(
                "transcript",
                {
                    "text": transcription.text,
                    "audio_seconds": round(transcription.audio_seconds, 3),
                    "processing_seconds": round(transcription.processing_seconds, 3),
                    "real_time_factor": round(transcription.real_time_factor, 3),
                },
            )
            if not transcription.text.strip():
                logger.info("CONVERSATION_EMPTY_TRANSCRIPT", extra={"peer_id": session_id})
                return None

            started_at = perf_counter()
            first_text_seconds: float | None = None
            logger.info(
                "CONVERSATION_LLM_STARTED",
                extra={
                    "peer_id": session_id,
                    "input_characters": len(transcription.text),
                    "history_messages": len(state.history),
                },
            )
            response_text = ""
            for attempt in range(2):
                response_parts: list[str] = []
                async for delta in self._language_model.stream_response(
                    transcription.text,
                    history=tuple(state.history),
                ):
                    if first_text_seconds is None and delta.strip():
                        first_text_seconds = perf_counter() - started_at
                    response_parts.append(delta)
                    await emit("assistant_delta", {"text": delta})
                response_text = "".join(response_parts).strip()
                if response_text:
                    break
                if attempt == 0:
                    logger.warning(
                        "CONVERSATION_LLM_EMPTY_RETRY",
                        extra={"peer_id": session_id},
                    )

            total_text_seconds = perf_counter() - started_at
            first_text_seconds = first_text_seconds or total_text_seconds
            if not response_text:
                raise RuntimeError("The language model returned no text")
            await emit(
                "assistant_done",
                {
                    "model": getattr(self._language_model, "model", "configured-model"),
                    "first_text_seconds": round(first_text_seconds, 3),
                    "total_seconds": round(total_text_seconds, 3),
                },
            )
            state.history.extend(
                (
                    ConversationMessage(role="user", content=transcription.text),
                    ConversationMessage(role="assistant", content=response_text),
                )
            )
            del state.history[: max(0, len(state.history) - self._max_messages)]

            logger.info(
                "CONVERSATION_TTS_STARTED",
                extra={"peer_id": session_id, "input_characters": len(response_text)},
            )
            synthesis = await self._text_to_speech.synthesize(response_text)
            await emit(
                "tts_done",
                {
                    "audio_seconds": round(synthesis.audio_seconds, 3),
                    "processing_seconds": round(synthesis.processing_seconds, 3),
                    "real_time_factor": round(synthesis.real_time_factor, 3),
                    "sample_rate": synthesis.sample_rate,
                },
            )
            logger.info(
                "CONVERSATION_TURN_COMPLETED",
                extra={
                    "peer_id": session_id,
                    "audio_seconds": round(transcription.audio_seconds, 3),
                    "stt_seconds": round(transcription.processing_seconds, 3),
                    "first_text_seconds": round(first_text_seconds, 3),
                    "llm_seconds": round(total_text_seconds, 3),
                    "tts_seconds": round(synthesis.processing_seconds, 3),
                    "response_audio_seconds": round(synthesis.audio_seconds, 3),
                    "history_messages": len(state.history),
                },
            )
            return ConversationResult(
                transcription=transcription,
                response_text=response_text,
                first_text_seconds=first_text_seconds,
                total_text_seconds=total_text_seconds,
                synthesis=synthesis,
            )
