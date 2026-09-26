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


class FakeTextToSpeech:
    async def synthesize(self, _: str) -> SynthesisResult:
        return SynthesisResult(
            samples=np.zeros(100, dtype=np.float32),
            sample_rate=22_050,
            processing_seconds=0.01,
        )


class FailingConversationManager(FakeConversationManager):
    async def process(self, *_: object, **__: object) -> None:
        raise RuntimeError("network unavailable")


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
        processes: list[FakeProcess] = []

        async def factory(*args: object, **kwargs: object) -> FakeProcess:
            calls.append((args, kwargs))
            process = FakeProcess(capture=args[0] == "arecord")
            processes.append(process)
            return process

        conversations = FakeConversationManager()
        adapter = UsbAudioConversation(
            conversation_manager=conversations,  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=FakeVad,  # type: ignore[arg-type]
            capture_device="plughw:CARD=P10S,DEV=0",
            playback_device="plughw:CARD=P10S,DEV=0",
            period_frames=512,
            process_factory=factory,
        )

        await adapter.start()
        assert adapter.running
        assert calls[0][0][:8] == (
            "amixer",
            "-q",
            "-c",
            "P10S",
            "sset",
            "PCM",
            "75%",
            "unmute",
        )
        assert calls[1][0][5:] == ("Mic", "100%", "cap")
        assert calls[2][0][:4] == (
            "arecord",
            "-q",
            "-D",
            "plughw:CARD=P10S,DEV=0",
        )
        assert "--period-size" in calls[2][0]

        await adapter.stop()
        assert processes[2].terminated
        assert conversations.forgotten == ["usb"]

    asyncio.run(run())


def test_usb_audio_plays_local_message_when_conversation_fails() -> None:
    async def run() -> None:
        calls: list[tuple[object, ...]] = []
        processes: list[FakeProcess] = []

        async def factory(*args: object, **_: object) -> FakeProcess:
            calls.append(args)
            process = FakeProcess()
            processes.append(process)
            return process

        adapter = UsbAudioConversation(
            conversation_manager=FailingConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=FakeVad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
            process_factory=factory,
        )
        task = asyncio.create_task(adapter._run_turn(np.zeros(1600, dtype=np.float32)))
        adapter._conversation_task = task
        await task

        assert calls[0][0] == "aplay"
        assert processes[0].stdin is not None
        assert len(processes[0].stdin.data) == 200

    asyncio.run(run())
