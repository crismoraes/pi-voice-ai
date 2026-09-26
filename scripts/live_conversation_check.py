"""Run automatic voice turns against a live PiVoice AI deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import time
from contextlib import suppress
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame
from av.audio.resampler import AudioResampler
from httpx import AsyncClient


class QueuedWavTrack(MediaStreamTrack):
    kind = "audio"
    sample_rate = 16_000
    frame_samples = 320

    def __init__(self, paths: list[Path]) -> None:
        super().__init__()
        self._clips = [self._load(path) for path in paths]
        self._next_clip = 0
        self._samples = np.empty(0, dtype=np.int16)
        self._offset = 0
        self._timestamp = 0
        self._started_at: float | None = None

    def _load(self, path: Path) -> np.ndarray:
        resampler = AudioResampler(format="s16", layout="mono", rate=self.sample_rate)
        chunks: list[np.ndarray] = []
        with av.open(str(path)) as container:
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    chunks.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                chunks.append(converted.to_ndarray().reshape(-1))
        if not chunks:
            raise ValueError(f"No audio samples found in {path}")
        return np.concatenate(chunks).astype(np.int16, copy=False)

    def play_next(self) -> None:
        if self._next_clip >= len(self._clips):
            raise RuntimeError("No queued WAV remains")
        leading_silence = np.zeros(self.sample_rate // 4, dtype=np.int16)
        self._samples = np.concatenate(
            (leading_silence, self._clips[self._next_clip])
        )
        self._next_clip += 1
        self._offset = 0

    async def recv(self) -> AudioFrame:
        if self.readyState != "live":
            raise MediaStreamError
        if self._started_at is None:
            self._started_at = time.time()
        else:
            self._timestamp += self.frame_samples
            wait = self._started_at + self._timestamp / self.sample_rate - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        if self._offset < len(self._samples):
            end = self._offset + self.frame_samples
            chunk = self._samples[self._offset:end]
            self._offset = end
        else:
            chunk = np.empty(0, dtype=np.int16)
        if len(chunk) < self.frame_samples:
            chunk = np.pad(chunk, (0, self.frame_samples - len(chunk)))
        frame = AudioFrame.from_ndarray(
            chunk.astype(np.int16, copy=False).reshape(1, -1),
            format="s16",
            layout="mono",
        )
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self.sample_rate)
        return frame


async def check_conversation(
    base_url: str,
    ca_file: Path,
    audio_files: list[Path],
) -> dict:
    peer = RTCPeerConnection()
    input_track = QueuedWavTrack(audio_files)
    peer.addTrack(input_track)
    connected = asyncio.get_running_loop().create_future()
    received_track = asyncio.get_running_loop().create_future()
    receiver_task: asyncio.Task[None] | None = None
    peer_id: str | None = None
    received_peak = 0
    audible_frames = 0
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
        nonlocal received_peak, audible_frames
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
            mode_response = await client.put(
                f"/api/webrtc/peers/{peer_id}/conversation",
                json={"enabled": True},
            )
            mode_response.raise_for_status()

            async with client.stream(
                "GET",
                f"/api/webrtc/peers/{peer_id}/events",
            ) as event_response:
                event_response.raise_for_status()
                await peer.setRemoteDescription(
                    RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
                )
                await asyncio.wait_for(connected, timeout=10)
                output_track = await asyncio.wait_for(received_track, timeout=10)
                receiver_task = asyncio.create_task(receive_audio(output_track))

                current_events: list[tuple[str, dict]] = []
                turns: list[dict] = []
                event_name = "message"
                data = ""
                completed_turn = False
                async for line in event_response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                    elif not line and data:
                        payload = json.loads(data)
                        if event_name == "tts_done":
                            completed_turn = True
                            current_events.append((event_name, payload))
                        elif event_name == "ready":
                            if completed_turn:
                                turns.append(summarize_turn(current_events))
                                current_events = []
                                completed_turn = False
                            if len(turns) == len(audio_files):
                                break
                            input_track.play_next()
                        else:
                            current_events.append((event_name, payload))
                        event_name = "message"
                        data = ""
                if audible_frames == 0:
                    raise RuntimeError("No assistant speech arrived over WebRTC")
                return {
                    "turns": turns,
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


def summarize_turn(events: list[tuple[str, dict]]) -> dict:
    event_map: dict[str, dict] = {}
    response_text = ""
    for event, payload in events:
        event_map[event] = payload
        if event == "assistant_delta":
            response_text += payload["text"]
    required = {
        "speech_started",
        "speech_ended",
        "transcript",
        "assistant_done",
        "tts_done",
    }
    missing = required.difference(event_map)
    if missing:
        raise RuntimeError(f"Missing conversation events: {sorted(missing)}")
    return {
        "transcript": event_map["transcript"],
        "response_text": response_text,
        "assistant": event_map["assistant_done"],
        "tts": event_map["tts_done"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument(
        "--audio-file",
        required=True,
        action="append",
        type=Path,
        help="WAV to send; repeat for multiple turns in the same session",
    )
    args = parser.parse_args()
    result = asyncio.run(
        check_conversation(args.url.rstrip("/"), args.ca_file, args.audio_file)
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
