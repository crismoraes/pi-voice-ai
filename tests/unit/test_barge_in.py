"""Barge-in behavior at the WebRTC conversation boundary."""

import asyncio

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection

from app.conversation.manager import ConversationResult
from app.stt.base import TranscriptionResult
from app.tts.base import SynthesisResult
from app.vad.base import VoiceActivityDetector
from app.webrtc.manager import (
    AssistantAudioTrack,
    PeerConnectionManager,
    PeerSession,
)


class MarkerVoiceActivityDetector(VoiceActivityDetector):
    """Treat positive samples as speech and zero samples as ending silence."""

    def __init__(self) -> None:
        self._speech = False

    @property
    def is_speech_detected(self) -> bool:
        return self._speech

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        if np.max(samples) > 0:
            self._speech = True
            return []
        if self._speech:
            self._speech = False
            return [np.ones(16_000, dtype=np.float32) * 0.1]
        return []

    def reset(self) -> None:
        self._speech = False


class PlaybackConversation:
    def __init__(self) -> None:
        self.calls = 0
        self.second_turn = asyncio.Event()

    async def process(self, session_id, samples, emit, play_audio=None):
        self.calls += 1
        if self.calls > 1:
            self.second_turn.set()
            return None
        result = ConversationResult(
            transcription=TranscriptionResult(
                text="primeiro turno",
                audio_seconds=1.0,
                processing_seconds=0.01,
            ),
            response_text="resposta longa",
            first_text_seconds=0.01,
            total_text_seconds=0.02,
            synthesis=SynthesisResult(
                samples=np.ones(80_000, dtype=np.float32) * 0.2,
                sample_rate=16_000,
                processing_seconds=0.01,
            ),
        )
        if play_audio is not None:
            await play_audio(result.synthesis)
        return result

    def forget(self, session_id: str) -> None:
        pass


async def exercise_barge_in() -> None:
    conversation = PlaybackConversation()
    manager = PeerConnectionManager(
        speech_to_text=None,  # type: ignore[arg-type]
        text_to_speech=None,  # type: ignore[arg-type]
        min_audio_seconds=0.5,
        max_audio_seconds=30,
    )
    manager.configure_conversations(
        conversation,  # type: ignore[arg-type]
        MarkerVoiceActivityDetector,
        enable_barge_in=True,
    )
    peer_id = "barge-in-peer"
    session = PeerSession(
        connection=RTCPeerConnection(),
        audio_track_ready=True,
        output_track=AssistantAudioTrack(AudioStreamTrack()),
        automatic_conversation=True,
        vad=MarkerVoiceActivityDetector(),
    )
    manager._sessions[peer_id] = session

    try:
        manager._feed_automatic_conversation(
            peer_id, session, np.ones(320, dtype=np.float32)
        )
        manager._feed_automatic_conversation(
            peer_id, session, np.zeros(320, dtype=np.float32)
        )
        for _ in range(20):
            if session.conversation_phase == "playback":
                break
            await asyncio.sleep(0)
        assert session.conversation_phase == "playback"

        manager._feed_automatic_conversation(
            peer_id, session, np.ones(320, dtype=np.float32)
        )
        await asyncio.sleep(0)
        assert not session.conversation_busy
        assert session.output_track._take_speech(960) is None

        manager._feed_automatic_conversation(
            peer_id, session, np.zeros(320, dtype=np.float32)
        )
        await asyncio.wait_for(conversation.second_turn.wait(), timeout=1)
        await asyncio.sleep(0)

        events = []
        while not session.event_queue.empty():
            events.append(session.event_queue.get_nowait())
        interrupted = [payload for event, payload in events if event == "interrupted"]
        assert interrupted == [
            {"phase": "playback", "remaining_audio_seconds": 5.0}
        ]
        assert [event for event, _ in events].count("speech_started") == 2
        assert [event for event, _ in events].count("speech_ended") == 2
        assert events[-1][0] == "ready"
    finally:
        await manager.close(peer_id)


def test_speech_interrupts_playback_and_starts_the_next_turn() -> None:
    asyncio.run(exercise_barge_in())
