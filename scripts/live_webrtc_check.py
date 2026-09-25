"""Validate an audio loopback against a running PiVoice AI deployment."""

from __future__ import annotations

import argparse
import asyncio
import ssl
from pathlib import Path

from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription
from httpx import AsyncClient


async def check_loopback(base_url: str, ca_file: Path) -> None:
    peer = RTCPeerConnection()
    received_track = asyncio.get_running_loop().create_future()
    peer_id: str | None = None
    ssl_context = ssl.create_default_context(cafile=str(ca_file))

    @peer.on("track")
    def on_track(track) -> None:
        if track.kind == "audio" and not received_track.done():
            received_track.set_result(track)

    peer.addTrack(AudioStreamTrack())

    try:
        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)

        async with AsyncClient(base_url=base_url, verify=ssl_context, timeout=15) as client:
            response = await client.post(
                "/api/webrtc/offer",
                json={
                    "sdp": peer.localDescription.sdp,
                    "type": peer.localDescription.type,
                },
            )
            response.raise_for_status()
            answer = response.json()
            peer_id = answer["peer_id"]
            await peer.setRemoteDescription(
                RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
            )

            echoed_track = await asyncio.wait_for(received_track, timeout=10)
            frame = await asyncio.wait_for(echoed_track.recv(), timeout=10)
            if frame.samples <= 0:
                raise RuntimeError("The returned audio frame contains no samples")

            close_response = await client.delete(f"/api/webrtc/peers/{peer_id}")
            close_response.raise_for_status()
    finally:
        await peer.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Deployment base URL")
    parser.add_argument("--ca-file", required=True, type=Path, help="Trusted CA file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(check_loopback(args.url.rstrip("/"), args.ca_file))
    print("Live WebRTC loopback passed")


if __name__ == "__main__":
    main()
