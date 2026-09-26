"""Interrupt a live assistant response with a second WebRTC utterance."""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
from contextlib import suppress
from pathlib import Path

import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from httpx import AsyncClient

from live_conversation_check import QueuedWavTrack


async def check_barge_in(
    base_url: str,
    ca_file: Path,
    first_audio: Path,
    interruption_audio: Path,
) -> dict:
    peer = RTCPeerConnection()
    input_track = QueuedWavTrack([first_audio, interruption_audio])
    peer.addTrack(input_track)
    connected = asyncio.get_running_loop().create_future()
    received_track = asyncio.get_running_loop().create_future()
    receiver_task: asyncio.Task[None] | None = None
    peer_id: str | None = None
    audible_frames = 0
    received_peak = 0
    ssl_context = ssl.create_default_context(cafile=str(ca_file))

    @peer.on("connectionstatechange")
    def on_connection_state_change() -> None:
        if peer.connectionState == "connected" and not connected.done():
            connected.set_result(None)
        elif peer.connectionState == "failed" and not connected.done():
            connected.set_exception(RuntimeError("WebRTC connection failed"))

    @peer.on("track")
    def on_track(track) -> None:
        if track.kind == "audio" and not received_track.done():
            received_track.set_result(track)

    async def receive_audio(track) -> None:
        nonlocal audible_frames, received_peak
        try:
            while True:
                frame = await track.recv()
                peak = int(np.max(np.abs(frame.to_ndarray())))
                received_peak = max(received_peak, peak)
                if peak >= 100:
                    audible_frames += 1
        except (MediaStreamError, asyncio.CancelledError):
            pass

    try:
        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)
        async with AsyncClient(
            base_url=base_url,
            verify=ssl_context,
            timeout=120,
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
            mode_response = await client.put(
                f"/api/webrtc/peers/{peer_id}/conversation",
                json={"enabled": True},
            )
            mode_response.raise_for_status()

            async with client.stream(
                "GET", f"/api/webrtc/peers/{peer_id}/events"
            ) as event_response:
                event_response.raise_for_status()
                await peer.setRemoteDescription(
                    RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                )
                await asyncio.wait_for(connected, timeout=10)
                output_track = await asyncio.wait_for(received_track, timeout=10)
                receiver_task = asyncio.create_task(receive_audio(output_track))

                started = False
                interruption_sent = False
                interruption: dict | None = None
                transcripts: list[dict] = []
                syntheses: list[dict] = []
                event_name = "message"
                data = ""
                async for line in event_response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                    elif not line and data:
                        payload = json.loads(data)
                        if event_name == "ready" and not started:
                            input_track.play_next()
                            started = True
                        elif event_name == "tts_done":
                            syntheses.append(payload)
                            if not interruption_sent:
                                input_track.play_next()
                                interruption_sent = True
                        elif event_name == "interrupted":
                            interruption = payload
                        elif event_name == "transcript":
                            transcripts.append(payload)
                        elif (
                            event_name == "ready"
                            and interruption is not None
                            and len(syntheses) >= 2
                        ):
                            break
                        event_name = "message"
                        data = ""

                if interruption is None:
                    raise RuntimeError("The first response was not interrupted")
                if len(transcripts) < 2 or len(syntheses) < 2:
                    raise RuntimeError("The second automatic turn did not complete")
                if audible_frames == 0:
                    raise RuntimeError("No assistant speech arrived over WebRTC")
                return {
                    "interruption": interruption,
                    "transcripts": transcripts,
                    "syntheses": syntheses,
                    "received_peak": received_peak,
                    "audible_frames": audible_frames,
                }
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
    parser.add_argument("--first-audio", required=True, type=Path)
    parser.add_argument("--interruption-audio", required=True, type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        check_barge_in(
            args.url.rstrip("/"),
            args.ca_file,
            args.first_audio,
            args.interruption_audio,
        )
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
