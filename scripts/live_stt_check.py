"""Send a WAV file over WebRTC and request STT from a live deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
from contextlib import suppress
from pathlib import Path

import av
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from aiortc.mediastreams import MediaStreamError
from httpx import AsyncClient


def audio_duration(path: Path) -> float:
    with av.open(str(path)) as container:
        if container.duration is None:
            raise ValueError(f"Audio duration is unavailable for {path}")
        return float(container.duration * av.time_base)


async def drain_track(track) -> None:
    try:
        while True:
            await track.recv()
    except (MediaStreamError, asyncio.CancelledError):
        pass


async def check_stt(base_url: str, ca_file: Path, audio_file: Path) -> dict:
    peer = RTCPeerConnection()
    player = MediaPlayer(str(audio_file))
    if player.audio is None:
        raise ValueError(f"No audio track found in {audio_file}")
    peer.addTrack(player.audio)
    drain_tasks: list[asyncio.Task[None]] = []
    connected = asyncio.get_running_loop().create_future()
    peer_id: str | None = None
    ssl_context = ssl.create_default_context(cafile=str(ca_file))

    @peer.on("track")
    def on_track(track) -> None:
        drain_tasks.append(asyncio.create_task(drain_track(track)))

    @peer.on("connectionstatechange")
    def on_connection_state_change() -> None:
        if peer.connectionState == "connected" and not connected.done():
            connected.set_result(None)
        elif peer.connectionState == "failed" and not connected.done():
            connected.set_exception(RuntimeError("WebRTC connection failed"))

    try:
        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)

        async with AsyncClient(base_url=base_url, verify=ssl_context, timeout=45) as client:
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

            start_response = await client.post(
                f"/api/webrtc/peers/{peer_id}/transcription/start"
            )
            start_response.raise_for_status()

            await peer.setRemoteDescription(
                RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
            )
            await asyncio.wait_for(connected, timeout=10)
            await asyncio.sleep(audio_duration(audio_file) + 1)

            finish_response = await client.post(
                f"/api/webrtc/peers/{peer_id}/transcription/finish"
            )
            finish_response.raise_for_status()
            result = finish_response.json()
            if result["audio_seconds"] <= 0:
                raise RuntimeError("The deployment captured no audio")
            return result
    finally:
        if peer_id is not None:
            with suppress(Exception):
                async with AsyncClient(
                    base_url=base_url, verify=ssl_context, timeout=10
                ) as client:
                    await client.delete(f"/api/webrtc/peers/{peer_id}")
        await peer.close()
        for task in drain_tasks:
            task.cancel()
        if drain_tasks:
            await asyncio.gather(*drain_tasks, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--audio-file", required=True, type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        check_stt(args.url.rstrip("/"), args.ca_file, args.audio_file)
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
