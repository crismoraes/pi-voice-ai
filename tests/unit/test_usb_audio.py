import asyncio

import numpy as np

from app.audio.usb import AlsaPlayback, UsbAudioConversation
from app.tts.base import SynthesisResult


class FakeStreamReader:
    async def read(self) -> bytes:
        return b""

    async def readexactly(self, _: int) -> bytes:
        await asyncio.Future()
        return b""


class FakeStreamWriter:
    def __init__(self) -> None:
        self.data = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class FakeProcess:
    def __init__(self, *, capture: bool = False) -> None:
        self.stdin = None if capture else FakeStreamWriter()
        self.stdout = FakeStreamReader() if capture else None
        self.stderr = FakeStreamReader()
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class FakeVad:
    is_speech_detected = False

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        return []

    def reset(self) -> None:
        return None


class FakeConversationManager:
    def __init__(self) -> None:
        self.forgotten: list[str] = []

    def forget(self, session_id: str) -> None:
        self.forgotten.append(session_id)


def test_alsa_playback_reuses_process_and_writes_pcm() -> None:
    async def run() -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        process = FakeProcess()

        async def factory(*args: object, **kwargs: object) -> FakeProcess:
            calls.append((args, kwargs))
            return process

        playback = AlsaPlayback("plughw:CARD=P10S,DEV=0", factory)
        synthesis = SynthesisResult(
            samples=np.array([-1.0, 0.0, 0.5, 1.0], dtype=np.float32),
            sample_rate=22_050,
            processing_seconds=0.1,
        )
        await playback.play(synthesis)
        await playback.play(synthesis)
        await playback.finish()

        assert len(calls) == 1
        assert calls[0][0][:4] == (
            "aplay",
            "-q",
            "-D",
            "plughw:CARD=P10S,DEV=0",
        )
        assert process.stdin is not None
        assert len(process.stdin.data) == 16
        assert process.stdin.closed

    asyncio.run(run())


def test_usb_audio_starts_and_stops_arecord() -> None:
    async def run() -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        process = FakeProcess(capture=True)

        async def factory(*args: object, **kwargs: object) -> FakeProcess:
            calls.append((args, kwargs))
            return process

        conversations = FakeConversationManager()
        adapter = UsbAudioConversation(
            conversation_manager=conversations,  # type: ignore[arg-type]
            vad_factory=FakeVad,  # type: ignore[arg-type]
            capture_device="plughw:CARD=P10S,DEV=0",
            playback_device="plughw:CARD=P10S,DEV=0",
            period_frames=512,
            process_factory=factory,
        )

        await adapter.start()
        assert adapter.running
        assert calls[0][0][:4] == (
            "arecord",
            "-q",
            "-D",
            "plughw:CARD=P10S,DEV=0",
        )
        assert "--period-size" in calls[0][0]

        await adapter.stop()
        assert process.terminated
        assert conversations.forgotten == ["usb"]

    asyncio.run(run())
