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


class ZeroStreamReader(FakeStreamReader):
    async def readexactly(self, size: int) -> bytes:
        return bytes(size)


class FakeStreamWriter:
    def __init__(self) -> None:
        self.data = bytearray()
        self.closed = False
        self.drain_calls = 0

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        self.drain_calls += 1
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class FakeProcess:
    def __init__(self, *, capture: bool = False, zero_stream: bool = False) -> None:
        self.stdin = None if capture else FakeStreamWriter()
        self.stdout = (
            ZeroStreamReader() if zero_stream else FakeStreamReader()
        ) if capture else None
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


class CountingVad(FakeVad):
    def __init__(self) -> None:
        self.calls = 0

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        self.calls += 1
        return []


class SegmentVad(FakeVad):
    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        return [samples]


class SpeechOnsetVad(FakeVad):
    def __init__(self) -> None:
        self.is_speech_detected = False

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        self.is_speech_detected = True
        return []


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


class PartiallyFailingConversationManager(FakeConversationManager):
    async def process(self, *_: object, **kwargs: object) -> None:
        await kwargs["play_audio"](
            SynthesisResult(
                samples=np.zeros(240, dtype=np.float32),
                sample_rate=24_000,
                processing_seconds=0.01,
            )
        )
        raise TimeoutError("response.done was not received")


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
        assert process.stdin.drain_calls == 0

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


def test_usb_audio_discards_samples_before_vad_while_disabled() -> None:
    async def run() -> None:
        vad = CountingVad()
        adapter = UsbAudioConversation(
            conversation_manager=FakeConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=lambda: vad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
        )
        adapter._vad = vad
        adapter._enabled = False

        await adapter._accept_samples(np.ones(512, dtype=np.float32))

        assert vad.calls == 0

    asyncio.run(run())


def test_usb_audio_marks_capture_for_pause_when_turn_starts() -> None:
    async def run() -> None:
        async def factory(*_: object, **__: object) -> FakeProcess:
            return FakeProcess()

        adapter = UsbAudioConversation(
            conversation_manager=FailingConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=SegmentVad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
            process_factory=factory,
        )
        adapter._vad = SegmentVad()

        started = await adapter._accept_samples(np.ones(512, dtype=np.float32))

        assert started
        assert adapter._busy
        assert not adapter._capture_released.is_set()
        assert not adapter._turn_finished.is_set()
        assert adapter._conversation_task is not None
        await asyncio.sleep(0)
        assert not adapter._conversation_task.done()
        adapter._capture_released.set()
        await adapter._conversation_task
        assert adapter._turn_finished.is_set()

    asyncio.run(run())


def test_usb_barge_in_stops_playback_when_new_speech_starts() -> None:
    async def run() -> None:
        process = FakeProcess()

        async def factory(*_: object, **__: object) -> FakeProcess:
            return process

        vad = SpeechOnsetVad()
        adapter = UsbAudioConversation(
            conversation_manager=FakeConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=lambda: vad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
            enable_barge_in=True,
            process_factory=factory,
        )
        playback = AlsaPlayback("playback", factory)
        await playback.play(
            SynthesisResult(
                samples=np.zeros(240, dtype=np.float32),
                sample_rate=24_000,
                processing_seconds=0,
            )
        )
        task = asyncio.create_task(asyncio.sleep(60))
        adapter._vad = vad
        adapter._busy = True
        adapter._playback = playback
        adapter._conversation_task = task

        await adapter._accept_samples(np.ones(512, dtype=np.float32))

        assert task.cancelled()
        assert process.killed
        assert not adapter._busy
        assert adapter._playback is None

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


def test_usb_audio_aborts_partial_realtime_playback_before_local_error() -> None:
    async def run() -> None:
        calls: list[tuple[object, ...]] = []
        processes: list[FakeProcess] = []

        async def factory(*args: object, **_: object) -> FakeProcess:
            calls.append(args)
            process = FakeProcess()
            processes.append(process)
            return process

        adapter = UsbAudioConversation(
            conversation_manager=PartiallyFailingConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=FakeVad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
            process_factory=factory,
        )
        task = asyncio.create_task(adapter._run_turn(np.zeros(1600, dtype=np.float32)))
        adapter._conversation_task = task
        await task

        assert len(processes) == 2
        assert processes[0].killed
        assert calls[0][-1] == "24000"
        assert calls[1][-1] == "22050"
        assert processes[1].stdin is not None
        assert processes[1].stdin.closed

    asyncio.run(run())


def test_usb_audio_restarts_a_zero_pcm_capture_stream() -> None:
    async def run() -> None:
        arecord_count = 0

        async def factory(*args: object, **_: object) -> FakeProcess:
            nonlocal arecord_count
            if args[0] == "arecord":
                arecord_count += 1
                return FakeProcess(capture=True, zero_stream=arecord_count == 1)
            return FakeProcess()

        adapter = UsbAudioConversation(
            conversation_manager=FakeConversationManager(),  # type: ignore[arg-type]
            text_to_speech=FakeTextToSpeech(),  # type: ignore[arg-type]
            vad_factory=FakeVad,  # type: ignore[arg-type]
            capture_device="capture",
            playback_device="playback",
            period_frames=512,
            capture_retry_seconds=0.001,
            zero_stream_seconds=0.032,
            process_factory=factory,
        )

        await adapter.start()
        for _ in range(100):
            if arecord_count >= 2:
                break
            await asyncio.sleep(0.001)

        assert arecord_count == 2
        assert adapter.running
        await adapter.stop()

    asyncio.run(run())
