"""Request local TTS and verify its audio crosses a live WebRTC connection."""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
from contextlib import suppress
from pathlib import Path

import numpy as np
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from httpx import AsyncClient


async def check_tts(base_url: str, ca_file: Path, text: str) -> dict:
    peer = RTCPeerConnection()
    peer.addTrack(AudioStreamTrack())
    received_track = asyncio.get_running_loop().create_future()
    connected = asyncio.get_running_loop().create_future()
    peer_id: str | None = None
    receiver_task: asyncio.Task[None] | None = None
    recording = asyncio.Event()
    peak = 0
    audible_frames = 0
    ssl_context = ssl.create_default_context(cafile=str(ca_file))

    @peer.on("track")
    def on_track(track) -> None:
        if track.kind == "audio" and not received_track.done():
            received_track.set_result(track)

    @peer.on("connectionstatechange")
    def on_connection_state_change() -> None:
        if peer.connectionState == "connected" and not connected.done():
            connected.set_result(None)
        elif peer.connectionState == "failed" and not connected.done():
            connected.set_exception(RuntimeError("WebRTC connection failed"))

    async def receive_audio(track) -> None:
        nonlocal peak, audible_frames
        try:
            while True:
                frame = await track.recv()
                if recording.is_set():
                    frame_peak = int(np.max(np.abs(frame.to_ndarray())))
                    peak = max(peak, frame_peak)
                    if frame_peak >= 100:
                        audible_frames += 1
        except (MediaStreamError, asyncio.CancelledError):
            pass

    try:
        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)
        async with AsyncClient(
            base_url=base_url,
            verify=ssl_context,
            timeout=60,
            trust_env=False,
        ) as client:
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
            await asyncio.wait_for(connected, timeout=10)
            output_track = await asyncio.wait_for(received_track, timeout=10)
            receiver_task = asyncio.create_task(receive_audio(output_track))

            recording.set()
            speech_response = await client.post(
                f"/api/webrtc/peers/{peer_id}/speech",
                json={"text": text},
            )
            speech_response.raise_for_status()
            result = speech_response.json()
            await asyncio.sleep(result["audio_seconds"] + 1)
            recording.clear()

            if audible_frames == 0:
                raise RuntimeError("No audible TTS samples arrived over WebRTC")
            result["received_peak"] = peak
            result["audible_frames"] = audible_frames
            return result
    finally:
        if peer_id is not None:
            with suppress(Exception):
                async with AsyncClient(
                    base_url=base_url,
                    verify=ssl_context,
                    timeout=10,
                    trust_env=False,
                ) as client:
                    await client.delete(f"/api/webrtc/peers/{peer_id}")
        await peer.close()
        if receiver_task is not None:
            receiver_task.cancel()
            await asyncio.gather(receiver_task, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument(
        "--text",
        default="Olá. Este é o teste da voz local do PiVoice AI.",
    )
    args = parser.parse_args()
    result = asyncio.run(check_tts(args.url.rstrip("/"), args.ca_file, args.text))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
