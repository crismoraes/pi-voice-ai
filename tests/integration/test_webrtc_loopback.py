import asyncio

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.stt.base import SpeechToText, TranscriptionResult
from app.tts.base import SynthesisResult, TextToSpeech
from app.webrtc.manager import peer_manager


class FakeSpeechToText(SpeechToText):
    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        audio_seconds = len(samples) / self.sample_rate
        return TranscriptionResult(
            text="teste de transcrição local",
            audio_seconds=audio_seconds,
            processing_seconds=0.01,
        )


class FakeTextToSpeech(TextToSpeech):
    async def synthesize(self, text: str) -> SynthesisResult:
        assert text == "resposta falada"
        time_axis = np.arange(22_050 // 2, dtype=np.float32) / 22_050
        return SynthesisResult(
            samples=(0.25 * np.sin(2 * np.pi * 440 * time_axis)).astype(np.float32),
            sample_rate=22_050,
            processing_seconds=0.02,
        )


async def exercise_audio_loopback() -> None:
    browser_peer = RTCPeerConnection()
    received_track = asyncio.get_running_loop().create_future()

    @browser_peer.on("track")
    def on_track(track) -> None:
        if track.kind == "audio" and not received_track.done():
            received_track.set_result(track)

    browser_peer.addTrack(AudioStreamTrack())
    original_stt = peer_manager._speech_to_text
    original_tts = peer_manager._text_to_speech
    peer_manager._speech_to_text = FakeSpeechToText()
    peer_manager._text_to_speech = FakeTextToSpeech()

    try:
        offer = await browser_peer.createOffer()
        await browser_peer.setLocalDescription(offer)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/webrtc/offer",
                json={
                    "sdp": browser_peer.localDescription.sdp,
                    "type": browser_peer.localDescription.type,
                },
            )
            assert response.status_code == 200
            answer = response.json()
            await browser_peer.setRemoteDescription(
                type(browser_peer.localDescription)(
                    sdp=answer["sdp"],
                    type=answer["type"],
                )
            )

            echoed_track = await asyncio.wait_for(received_track, timeout=10)
            frame = await asyncio.wait_for(echoed_track.recv(), timeout=10)

            assert frame.samples > 0
            assert peer_manager.active_peer_count == 1

            loopback_response = await client.put(
                f"/api/webrtc/peers/{answer['peer_id']}/loopback",
                json={"enabled": True},
            )
            assert loopback_response.status_code == 204

            start_response = await client.post(
                f"/api/webrtc/peers/{answer['peer_id']}/transcription/start"
            )
            assert start_response.status_code == 204
            await asyncio.sleep(0.7)

            finish_response = await client.post(
                f"/api/webrtc/peers/{answer['peer_id']}/transcription/finish"
            )
            assert finish_response.status_code == 200
            transcription = finish_response.json()
            assert transcription["text"] == "teste de transcrição local"
            assert transcription["audio_seconds"] >= 0.5
            assert transcription["processing_seconds"] == 0.01

            speech_response = await client.post(
                f"/api/webrtc/peers/{answer['peer_id']}/speech",
                json={"text": "resposta falada"},
            )
            assert speech_response.status_code == 200
            synthesis = speech_response.json()
            assert synthesis["audio_seconds"] == 0.5
            assert synthesis["processing_seconds"] == 0.02
            assert synthesis["sample_rate"] == 22_050

            heard_speech = False
            # Frames generated while STT was running may already be buffered at
            # the receiver. Drain up to two seconds so the queued TTS audio has
            # time to reach this side of the peer connection.
            for _ in range(100):
                speech_frame = await asyncio.wait_for(echoed_track.recv(), timeout=2)
                if np.max(np.abs(speech_frame.to_ndarray())) > 0:
                    heard_speech = True
                    break
            assert heard_speech

            close_response = await client.delete(
                f"/api/webrtc/peers/{answer['peer_id']}"
            )
            assert close_response.status_code == 204
            assert peer_manager.active_peer_count == 0

            repeated_close_response = await client.delete(
                f"/api/webrtc/peers/{answer['peer_id']}"
            )
            assert repeated_close_response.status_code == 204
    finally:
        peer_manager._speech_to_text = original_stt
        peer_manager._text_to_speech = original_tts
        await browser_peer.close()
        await peer_manager.close_all()


def test_audio_pipeline_over_webrtc() -> None:
    asyncio.run(exercise_audio_loopback())
