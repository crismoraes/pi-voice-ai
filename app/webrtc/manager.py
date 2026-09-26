"""Lifecycle management for WebRTC audio and local transcription."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import MediaStreamError
from av.audio.resampler import AudioResampler

from app.config import get_settings
from app.stt.base import SpeechToText, TranscriptionResult
from app.stt.sherpa_whisper import SherpaWhisperSpeechToText

logger = logging.getLogger("pi_voice_ai.webrtc")


class PeerNotFoundError(LookupError):
    """Raised when a transcription targets an unknown peer."""


class AudioTrackUnavailableError(RuntimeError):
    """Raised when capture starts before an audio track arrives."""


class CaptureStateError(RuntimeError):
    """Raised when capture start/finish calls are out of order."""


class AudioDurationError(ValueError):
    """Raised when captured audio is too short to transcribe."""


@dataclass(slots=True)
class PeerSession:
    connection: RTCPeerConnection
    capture_task: asyncio.Task[None] | None = None
    audio_track_ready: bool = False
    capturing: bool = False
    chunks: list[np.ndarray] = field(default_factory=list)
    sample_count: int = 0
    truncated: bool = False


class PeerConnectionManager:
    """Create, track and close WebRTC peers and their audio captures."""

    sample_rate = 16_000

    def __init__(
        self,
        speech_to_text: SpeechToText,
        min_audio_seconds: float,
        max_audio_seconds: float,
    ) -> None:
        self._sessions: dict[str, PeerSession] = {}
        self._relay = MediaRelay()
        self._speech_to_text = speech_to_text
        self._min_samples = int(min_audio_seconds * self.sample_rate)
        self._max_samples = int(max_audio_seconds * self.sample_rate)

    @property
    def active_peer_count(self) -> int:
        return len(self._sessions)

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
                peer_connection.addTrack(self._relay.subscribe(track))
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
                    if not session.capturing or session.sample_count >= self._max_samples:
                        continue
                    samples = (
                        resampled_frame.to_ndarray()
                        .reshape(-1)
                        .astype(np.float32)
                        / 32768.0
                    )
                    remaining = self._max_samples - session.sample_count
                    if len(samples) > remaining:
                        samples = samples[:remaining]
                        session.truncated = True
                    session.chunks.append(samples.copy())
                    session.sample_count += len(samples)
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
        if session.capture_task is not None:
            session.capture_task.cancel()
            with suppress(asyncio.CancelledError):
                await session.capture_task
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
peer_manager = PeerConnectionManager(
    speech_to_text=speech_to_text,
    min_audio_seconds=settings.stt_min_audio_seconds,
    max_audio_seconds=settings.stt_max_audio_seconds,
)
