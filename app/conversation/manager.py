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
from app.tts.chunking import split_text_for_speech

logger = logging.getLogger("pi_voice_ai.conversation")
EventHandler = Callable[[str, dict[str, object]], Awaitable[None]]
AudioHandler = Callable[[SynthesisResult], Awaitable[None]]


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
        tts_chunk_characters: int = 240,
    ) -> None:
        self._speech_to_text = speech_to_text
        self._language_model = language_model
        self._text_to_speech = text_to_speech
        self._max_messages = max_turns * 2
        self._tts_chunk_characters = tts_chunk_characters
        self._states: dict[str, ConversationState] = {}

    def forget(self, session_id: str) -> None:
        self._states.pop(session_id, None)

    async def process(
        self,
        session_id: str,
        samples: np.ndarray,
        emit: EventHandler,
        play_audio: AudioHandler | None = None,
    ) -> ConversationResult | None:
        state = self._states.setdefault(session_id, ConversationState())
        async with state.lock:
            await emit("transcribing", {})
            absolute_samples = np.abs(samples)
            audio_peak = float(np.max(absolute_samples)) if len(samples) else 0.0
            audio_rms = (
                float(np.sqrt(np.mean(np.square(samples)))) if len(samples) else 0.0
            )
            clipped_percent = (
                float(np.count_nonzero(absolute_samples >= 0.99) * 100 / len(samples))
                if len(samples)
                else 0.0
            )
            logger.info(
                "CONVERSATION_STT_STARTED",
                extra={
                    "peer_id": session_id,
                    "audio_seconds": round(len(samples) / 16_000, 3),
                    "audio_peak": round(audio_peak, 4),
                    "audio_rms": round(audio_rms, 4),
                    "clipped_percent": round(clipped_percent, 3),
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
            tts_started_at = perf_counter()
            first_audio_seconds: float | None = None
            syntheses: list[SynthesisResult] = []
            text_chunks = split_text_for_speech(
                response_text, self._tts_chunk_characters
            )
            for index, text_chunk in enumerate(text_chunks, start=1):
                synthesis_chunk = await self._text_to_speech.synthesize(text_chunk)
                syntheses.append(synthesis_chunk)
                if play_audio is not None:
                    await play_audio(synthesis_chunk)
                if first_audio_seconds is None:
                    first_audio_seconds = perf_counter() - tts_started_at
                    logger.info(
                        "CONVERSATION_FIRST_AUDIO_QUEUED",
                        extra={
                            "peer_id": session_id,
                            "seconds": round(first_audio_seconds, 3),
                        },
                    )
                await emit(
                    "tts_chunk",
                    {
                        "index": index,
                        "total": len(text_chunks),
                        "audio_seconds": round(synthesis_chunk.audio_seconds, 3),
                        "processing_seconds": round(
                            synthesis_chunk.processing_seconds, 3
                        ),
                    },
                )
            sample_rate = syntheses[0].sample_rate
            if any(item.sample_rate != sample_rate for item in syntheses):
                raise RuntimeError("TTS chunks returned different sample rates")
            synthesis = SynthesisResult(
                samples=np.concatenate([item.samples for item in syntheses]),
                sample_rate=sample_rate,
                processing_seconds=sum(
                    item.processing_seconds for item in syntheses
                ),
            )
            await emit(
                "tts_done",
                {
                    "audio_seconds": round(synthesis.audio_seconds, 3),
                    "processing_seconds": round(synthesis.processing_seconds, 3),
                    "real_time_factor": round(synthesis.real_time_factor, 3),
                    "sample_rate": synthesis.sample_rate,
                    "chunks": len(syntheses),
                    "first_audio_seconds": round(first_audio_seconds or 0, 3),
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
                    "first_audio_seconds": round(first_audio_seconds or 0, 3),
                    "tts_chunks": len(syntheses),
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
