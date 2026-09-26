"""Lifecycle management for WebRTC audio and local transcription."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from fractions import Fraction
from uuid import uuid4

import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame
from av.audio.resampler import AudioResampler

from app.config import get_settings
from app.conversation.manager import ConversationManager
from app.stt.base import SpeechToText, TranscriptionResult
from app.stt.sherpa_whisper import SherpaWhisperSpeechToText
from app.tts.base import SynthesisResult, TextToSpeech
from app.tts.sherpa_piper import SherpaPiperTextToSpeech
from app.vad.base import VoiceActivityDetector

logger = logging.getLogger("pi_voice_ai.webrtc")


class PeerNotFoundError(LookupError):
    """Raised when a transcription targets an unknown peer."""


class AudioTrackUnavailableError(RuntimeError):
    """Raised when capture starts before an audio track arrives."""


class CaptureStateError(RuntimeError):
    """Raised when capture start/finish calls are out of order."""


class AudioDurationError(ValueError):
    """Raised when captured audio is too short to transcribe."""


class AssistantAudioTrack(MediaStreamTrack):
    """Send loopback, silence or queued assistant speech on one WebRTC track."""

    kind = "audio"
    sample_rate = 48_000

    def __init__(self, source: MediaStreamTrack) -> None:
        super().__init__()
        self._source = source
        self._source_resampler = AudioResampler(
            format="s16", layout="mono", rate=self.sample_rate
        )
        self._loopback_enabled = False
        self._speech_samples = np.empty(0, dtype=np.int16)
        self._speech_offset = 0
        self._timestamp = 0

    def set_loopback(self, enabled: bool) -> None:
        self._loopback_enabled = enabled

    def queue_speech(self, samples: np.ndarray, sample_rate: int) -> None:
        clipped = np.clip(samples, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16).reshape(1, -1)
        source_frame = AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        source_frame.sample_rate = sample_rate
        resampler = AudioResampler(
            format="s16", layout="mono", rate=self.sample_rate
        )
        frames = list(resampler.resample(source_frame))
        frames.extend(resampler.resample(None))
        new_samples = np.concatenate(
            [frame.to_ndarray().reshape(-1) for frame in frames]
        ).astype(np.int16, copy=False)
        remaining = self._speech_samples[self._speech_offset :]
        self._speech_samples = np.concatenate((remaining, new_samples))
        self._speech_offset = 0

    def interrupt_speech(self) -> float:
        """Discard queued assistant speech and return its remaining duration."""
        remaining_samples = max(0, len(self._speech_samples) - self._speech_offset)
        self._speech_samples = np.empty(0, dtype=np.int16)
        self._speech_offset = 0
        return remaining_samples / self.sample_rate

    def _take_speech(self, sample_count: int) -> np.ndarray | None:
        if self._speech_offset >= len(self._speech_samples):
            return None
        end = min(self._speech_offset + sample_count, len(self._speech_samples))
        chunk = self._speech_samples[self._speech_offset:end]
        self._speech_offset = end
        if len(chunk) < sample_count:
            chunk = np.pad(chunk, (0, sample_count - len(chunk)))
        return chunk

    async def recv(self) -> AudioFrame:
        while True:
            source_frame = await self._source.recv()
            frames = self._source_resampler.resample(source_frame)
            if frames:
                break

        loopback_frame = frames[0]
        sample_count = loopback_frame.samples
        speech = self._take_speech(sample_count)
        if speech is not None:
            output_frame = AudioFrame.from_ndarray(
                speech.reshape(1, -1), format="s16", layout="mono"
            )
            output_frame.sample_rate = self.sample_rate
        elif self._loopback_enabled:
            output_frame = loopback_frame
        else:
            output_frame = AudioFrame.from_ndarray(
                np.zeros((1, sample_count), dtype=np.int16),
                format="s16",
                layout="mono",
            )
            output_frame.sample_rate = self.sample_rate

        output_frame.pts = self._timestamp
        output_frame.time_base = Fraction(1, self.sample_rate)
        self._timestamp += sample_count
        return output_frame


@dataclass(slots=True)
class PeerSession:
    connection: RTCPeerConnection
    capture_task: asyncio.Task[None] | None = None
    audio_track_ready: bool = False
    capturing: bool = False
    chunks: list[np.ndarray] = field(default_factory=list)
    sample_count: int = 0
    truncated: bool = False
    output_track: AssistantAudioTrack | None = None
    automatic_conversation: bool = False
    conversation_busy: bool = False
    conversation_phase: str | None = None
    vad: VoiceActivityDetector | None = None
    conversation_task: asyncio.Task[None] | None = None
    event_queue: asyncio.Queue[tuple[str, dict[str, object]] | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=100)
    )


class PeerConnectionManager:
    """Create, track and close WebRTC peers and their audio captures."""

    sample_rate = 16_000

    def __init__(
        self,
        speech_to_text: SpeechToText,
        text_to_speech: TextToSpeech,
        min_audio_seconds: float,
        max_audio_seconds: float,
    ) -> None:
        self._sessions: dict[str, PeerSession] = {}
        self._relay = MediaRelay()
        self._speech_to_text = speech_to_text
        self._text_to_speech = text_to_speech
        self._min_samples = int(min_audio_seconds * self.sample_rate)
        self._max_samples = int(max_audio_seconds * self.sample_rate)
        self._conversation_manager: ConversationManager | None = None
        self._vad_factory: Callable[[], VoiceActivityDetector] | None = None
        self._barge_in_enabled = False

    def configure_conversations(
        self,
        conversation_manager: ConversationManager,
        vad_factory: Callable[[], VoiceActivityDetector],
        *,
        enable_barge_in: bool = False,
    ) -> None:
        self._conversation_manager = conversation_manager
        self._vad_factory = vad_factory
        self._barge_in_enabled = enable_barge_in

    @property
    def active_peer_count(self) -> int:
        return len(self._sessions)

    def has_peer(self, peer_id: str) -> bool:
        return peer_id in self._sessions

    async def accept_offer(
        self,
        session_description: RTCSessionDescription,
    ) -> tuple[str, RTCSessionDescription]:
        peer_id = uuid4().hex
        peer_connection = RTCPeerConnection()
        session = PeerSession(connection=peer_connection)
        self._sessions[peer_id] = session

        @peer_connection.on("track")
        def on_track(track: MediaStreamTrack) -> None:
            logger.info(
                "WEBRTC_TRACK_RECEIVED",
                extra={"peer_id": peer_id, "kind": track.kind},
            )
            if track.kind == "audio":
                session.audio_track_ready = True
                session.output_track = AssistantAudioTrack(
                    self._relay.subscribe(track, buffered=False)
                )
                peer_connection.addTrack(session.output_track)
                capture_track = self._relay.subscribe(track)
                session.capture_task = asyncio.create_task(
                    self._consume_audio(peer_id, session, capture_track)
                )

        @peer_connection.on("connectionstatechange")
        async def on_connection_state_change() -> None:
            state = peer_connection.connectionState
            logger.info(
                "WEBRTC_CONNECTION_STATE",
                extra={"peer_id": peer_id, "state": state},
            )
            if state == "connected":
                logger.info("WEBRTC_CONNECTED", extra={"peer_id": peer_id})
            elif state in {"failed", "closed"}:
                await self.close(peer_id)

        try:
            await peer_connection.setRemoteDescription(session_description)
            answer = await peer_connection.createAnswer()
            await peer_connection.setLocalDescription(answer)
        except Exception:
            logger.exception("WEBRTC_NEGOTIATION_FAILED", extra={"peer_id": peer_id})
            await self.close(peer_id)
            raise

        local_description = peer_connection.localDescription
        if local_description is None:
            await self.close(peer_id)
            raise RuntimeError("WebRTC answer was not created")
        return peer_id, local_description

    async def _consume_audio(
        self,
        peer_id: str,
        session: PeerSession,
        track: MediaStreamTrack,
    ) -> None:
        resampler = AudioResampler(format="s16", layout="mono", rate=self.sample_rate)
        try:
            while True:
                frame = await track.recv()
                for resampled_frame in resampler.resample(frame):
                    samples = (
                        resampled_frame.to_ndarray()
                        .reshape(-1)
                        .astype(np.float32)
                        / 32768.0
                    )
                    if session.capturing and session.sample_count < self._max_samples:
                        remaining = self._max_samples - session.sample_count
                        capture_samples = samples[:remaining]
                        if len(samples) > remaining:
                            session.truncated = True
                        session.chunks.append(capture_samples.copy())
                        session.sample_count += len(capture_samples)
                    self._feed_automatic_conversation(peer_id, session, samples)
        except (MediaStreamError, asyncio.CancelledError):
            pass
        except Exception:
            logger.exception("WEBRTC_AUDIO_CAPTURE_FAILED", extra={"peer_id": peer_id})

    def start_transcription(self, peer_id: str) -> None:
        session = self._get_session(peer_id)
        if not session.audio_track_ready:
            raise AudioTrackUnavailableError("Audio track is not ready")
        if session.capturing:
            raise CaptureStateError("Audio capture is already active")
        if session.automatic_conversation:
            raise CaptureStateError("Automatic conversation is active")
        session.chunks.clear()
        session.sample_count = 0
        session.truncated = False
        session.capturing = True
        logger.info("STT_CAPTURE_STARTED", extra={"peer_id": peer_id})

    async def finish_transcription(self, peer_id: str) -> TranscriptionResult:
        session = self._get_session(peer_id)
        if not session.capturing:
            raise CaptureStateError("Audio capture is not active")
        session.capturing = False
        sample_count = session.sample_count
        chunks = session.chunks
        session.chunks = []
        session.sample_count = 0
        if sample_count < self._min_samples:
            raise AudioDurationError("Captured audio is too short")

        audio = np.concatenate(chunks)
        logger.info(
            "STT_STARTED",
            extra={
                "peer_id": peer_id,
                "audio_seconds": round(len(audio) / self.sample_rate, 3),
                "truncated": session.truncated,
            },
        )
        result = await self._speech_to_text.transcribe(audio)
        logger.info(
            "STT_COMPLETED",
            extra={
                "peer_id": peer_id,
                "audio_seconds": round(result.audio_seconds, 3),
                "processing_seconds": round(result.processing_seconds, 3),
                "real_time_factor": round(result.real_time_factor, 3),
            },
        )
        return result

    def set_loopback(self, peer_id: str, enabled: bool) -> None:
        session = self._get_session(peer_id)
        if session.output_track is None:
            raise AudioTrackUnavailableError("Audio track is not ready")
        session.output_track.set_loopback(enabled)
        logger.info(
            "WEBRTC_LOOPBACK_CHANGED",
            extra={"peer_id": peer_id, "enabled": enabled},
        )

    async def synthesize_speech(self, peer_id: str, text: str) -> SynthesisResult:
        session = self._get_session(peer_id)
        if session.output_track is None:
            raise AudioTrackUnavailableError("Audio track is not ready")
        logger.info(
            "TTS_STARTED",
            extra={"peer_id": peer_id, "input_characters": len(text)},
        )
        result = await self._text_to_speech.synthesize(text)
        session.output_track.queue_speech(result.samples, result.sample_rate)
        logger.info(
            "TTS_COMPLETED",
            extra={
                "peer_id": peer_id,
                "audio_seconds": round(result.audio_seconds, 3),
                "processing_seconds": round(result.processing_seconds, 3),
                "real_time_factor": round(result.real_time_factor, 3),
            },
        )
        return result

    async def configure_automatic_conversation(
        self,
        peer_id: str,
        enabled: bool,
    ) -> None:
        session = self._get_session(peer_id)
        if not session.audio_track_ready:
            raise AudioTrackUnavailableError("Audio track is not ready")
        if self._conversation_manager is None or self._vad_factory is None:
            raise RuntimeError("Automatic conversation is unavailable")
        if enabled and session.vad is None:
            session.vad = await asyncio.to_thread(self._vad_factory)
        if session.vad is not None:
            session.vad.reset()
        session.automatic_conversation = enabled
        await self._emit(
            session,
            "ready" if enabled else "manual",
            {},
        )
        logger.info(
            "CONVERSATION_MODE_CHANGED",
            extra={"peer_id": peer_id, "automatic": enabled},
        )

    async def conversation_events(
        self,
        peer_id: str,
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        session = self._get_session(peer_id)
        while True:
            event = await session.event_queue.get()
            if event is None:
                return
            yield event

    def _feed_automatic_conversation(
        self,
        peer_id: str,
        session: PeerSession,
        samples: np.ndarray,
    ) -> None:
        vad = session.vad
        if not session.automatic_conversation or vad is None:
            return
        if session.conversation_busy and not self._barge_in_enabled:
            return
        speech_was_detected = vad.is_speech_detected
        segments = vad.accept(samples)
        if not speech_was_detected and vad.is_speech_detected:
            if session.conversation_busy:
                self._interrupt_conversation(peer_id, session)
            self._emit_nowait(session, "speech_started", {})
            logger.info("VAD_SPEECH_STARTED", extra={"peer_id": peer_id})
        for segment in segments:
            if len(segment) < self._min_samples:
                logger.info(
                    "VAD_SEGMENT_SKIPPED",
                    extra={
                        "peer_id": peer_id,
                        "audio_seconds": round(len(segment) / self.sample_rate, 3),
                    },
                )
                self._emit_nowait(session, "ready", {})
                continue
            vad.reset()
            session.conversation_busy = True
            session.conversation_phase = "processing"
            self._emit_nowait(
                session,
                "speech_ended",
                {"audio_seconds": round(len(segment) / self.sample_rate, 3)},
            )
            logger.info(
                "VAD_SPEECH_ENDED",
                extra={
                    "peer_id": peer_id,
                    "audio_seconds": round(len(segment) / self.sample_rate, 3),
                },
            )
            session.conversation_task = asyncio.create_task(
                self._run_automatic_conversation(peer_id, session, segment)
            )
            break

    def _interrupt_conversation(self, peer_id: str, session: PeerSession) -> None:
        phase = session.conversation_phase or "processing"
        task = session.conversation_task
        if task is not None and not task.done():
            task.cancel()
        session.conversation_task = None
        session.conversation_busy = False
        session.conversation_phase = None
        remaining_audio_seconds = 0.0
        if session.output_track is not None:
            remaining_audio_seconds = session.output_track.interrupt_speech()
        payload: dict[str, object] = {
            "phase": phase,
            "remaining_audio_seconds": round(remaining_audio_seconds, 3),
        }
        self._emit_nowait(session, "interrupted", payload)
        logger.info(
            "CONVERSATION_INTERRUPTED",
            extra={"peer_id": peer_id, **payload},
        )

    async def _run_automatic_conversation(
        self,
        peer_id: str,
        session: PeerSession,
        samples: np.ndarray,
    ) -> None:
        current_task = asyncio.current_task()
        try:
            if self._conversation_manager is None or session.output_track is None:
                raise RuntimeError("Automatic conversation is unavailable")
            result = await self._conversation_manager.process(
                peer_id,
                samples,
                lambda event, payload: self._emit(session, event, payload),
            )
            if result is not None:
                session.conversation_phase = "playback"
                session.output_track.queue_speech(
                    result.synthesis.samples,
                    result.synthesis.sample_rate,
                )
                await asyncio.sleep(result.synthesis.audio_seconds)
        except asyncio.CancelledError:
            logger.info(
                "CONVERSATION_TURN_CANCELLED",
                extra={"peer_id": peer_id},
            )
            raise
        except Exception as exc:
            logger.exception(
                "CONVERSATION_TURN_FAILED",
                extra={"peer_id": peer_id, "error_type": type(exc).__name__},
            )
            await self._emit(
                session,
                "error",
                {"message": "Não foi possível concluir a conversa."},
            )
        finally:
            if session.conversation_task is current_task:
                session.conversation_task = None
                session.conversation_busy = False
                session.conversation_phase = None
                if session.vad is not None:
                    session.vad.reset()
                if session.automatic_conversation and peer_id in self._sessions:
                    await self._emit(session, "ready", {})

    @staticmethod
    async def _emit(
        session: PeerSession,
        event: str,
        payload: dict[str, object],
    ) -> None:
        PeerConnectionManager._emit_nowait(session, event, payload)

    @staticmethod
    def _emit_nowait(
        session: PeerSession,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if session.event_queue.full():
            with suppress(asyncio.QueueEmpty):
                session.event_queue.get_nowait()
        session.event_queue.put_nowait((event, payload))

    def _get_session(self, peer_id: str) -> PeerSession:
        session = self._sessions.get(peer_id)
        if session is None:
            raise PeerNotFoundError(peer_id)
        return session

    async def close(self, peer_id: str) -> bool:
        session = self._sessions.pop(peer_id, None)
        if session is None:
            return False
        session.capturing = False
        session.automatic_conversation = False
        if session.capture_task is not None:
            session.capture_task.cancel()
            with suppress(asyncio.CancelledError):
                await session.capture_task
        if session.conversation_task is not None:
            session.conversation_task.cancel()
            with suppress(asyncio.CancelledError):
                await session.conversation_task
        if self._conversation_manager is not None:
            self._conversation_manager.forget(peer_id)
        self._emit_nowait(session, "disconnected", {})
        if session.event_queue.full():
            with suppress(asyncio.QueueEmpty):
                session.event_queue.get_nowait()
        session.event_queue.put_nowait(None)
        await session.connection.close()
        logger.info("WEBRTC_DISCONNECTED", extra={"peer_id": peer_id})
        return True

    async def close_all(self) -> None:
        peer_ids = tuple(self._sessions)
        if peer_ids:
            await asyncio.gather(*(self.close(peer_id) for peer_id in peer_ids))


settings = get_settings()
if settings.stt_engine not in {"sherpa", "sherpa-whisper"}:
    raise ValueError(f"Unsupported STT_ENGINE: {settings.stt_engine}")

speech_to_text = SherpaWhisperSpeechToText(
    model_dir=settings.stt_model_dir,
    language=settings.stt_language,
    num_threads=settings.stt_num_threads,
)
if settings.tts_engine not in {"piper", "sherpa-piper"}:
    raise ValueError(f"Unsupported TTS_ENGINE: {settings.tts_engine}")

text_to_speech = SherpaPiperTextToSpeech(
    model_dir=settings.tts_model_dir,
    num_threads=settings.tts_num_threads,
    speed=settings.tts_speed,
    max_text_characters=settings.tts_max_text_characters,
)
peer_manager = PeerConnectionManager(
    speech_to_text=speech_to_text,
    text_to_speech=text_to_speech,
    min_audio_seconds=settings.stt_min_audio_seconds,
    max_audio_seconds=settings.stt_max_audio_seconds,
)
