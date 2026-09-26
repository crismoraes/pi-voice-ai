import asyncio

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.stt.base import SpeechToText, TranscriptionResult
from app.webrtc.manager import peer_manager


class FakeSpeechToText(SpeechToText):
    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        audio_seconds = len(samples) / self.sample_rate
        return TranscriptionResult(
            text="teste de transcrição local",
            audio_seconds=audio_seconds,
            processing_seconds=0.01,
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
    peer_manager._speech_to_text = FakeSpeechToText()

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
        await browser_peer.close()
        await peer_manager.close_all()


def test_audio_track_is_echoed_over_webrtc() -> None:
    asyncio.run(exercise_audio_loopback())
