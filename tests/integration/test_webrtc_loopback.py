import asyncio

from aiortc import AudioStreamTrack, RTCPeerConnection
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.webrtc.manager import peer_manager


async def exercise_audio_loopback() -> None:
    browser_peer = RTCPeerConnection()
    received_track = asyncio.get_running_loop().create_future()

    @browser_peer.on("track")
    def on_track(track) -> None:
        if track.kind == "audio" and not received_track.done():
            received_track.set_result(track)

    browser_peer.addTrack(AudioStreamTrack())

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
        await browser_peer.close()
        await peer_manager.close_all()


def test_audio_track_is_echoed_over_webrtc() -> None:
    asyncio.run(exercise_audio_loopback())
