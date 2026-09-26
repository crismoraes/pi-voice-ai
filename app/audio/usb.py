"""ALSA USB microphone and speaker adapter for local voice conversations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from time import perf_counter

import numpy as np

from app.conversation.manager import ConversationManager
from app.tts.base import SynthesisResult, TextToSpeech
from app.vad.base import VoiceActivityDetector

logger = logging.getLogger("pi_voice_ai.usb_audio")


class UsbAudioUnavailableError(RuntimeError):
    """Raised when an ALSA process cannot provide the configured audio device."""


ProcessFactory = Callable[..., Awaitable[asyncio.subprocess.Process]]


class AlsaPlayback:
    """Stream consecutive synthesis chunks to one ALSA playback process."""

    def __init__(
        self,
        device: str,
        process_factory: ProcessFactory = asyncio.create_subprocess_exec,
    ) -> None:
        self._device = device
        self._process_factory = process_factory
        self._process: asyncio.subprocess.Process | None = None
        self._sample_rate: int | None = None
        self._started_at: float | None = None
        self._written_seconds = 0.0

    async def play(self, synthesis: SynthesisResult) -> None:
        if self._process is None:
            self._sample_rate = synthesis.sample_rate
            self._process = await self._process_factory(
                "aplay",
                "-q",
                "-D",
                self._device,
                "-t",
                "raw",
                "-f",
                "S16_LE",
                "-c",
                "1",
                "-r",
                str(synthesis.sample_rate),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            self._started_at = perf_counter()
            logger.info(
                "USB_PLAYBACK_STARTED",
                extra={"device": self._device, "sample_rate": synthesis.sample_rate},
            )
        elif synthesis.sample_rate != self._sample_rate:
            raise UsbAudioUnavailableError("TTS chunks use different sample rates")

        process = self._process
        if process.stdin is None:
            raise UsbAudioUnavailableError("ALSA playback input is unavailable")
        pcm = (np.clip(synthesis.samples, -1.0, 1.0) * 32767.0).astype("<i2")
        process.stdin.write(pcm.tobytes())
        await process.stdin.drain()
        self._written_seconds += synthesis.audio_seconds

    async def finish(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
            with suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()
        return_code = await process.wait()
        stderr = await process.stderr.read() if process.stderr is not None else b""
        if return_code != 0:
            raise UsbAudioUnavailableError(
                f"aplay exited with status {return_code}: "
                f"{stderr.decode(errors='replace').strip()}"
            )
        logger.info(
            "USB_PLAYBACK_COMPLETED",
            extra={
                "audio_seconds": round(self._written_seconds, 3),
                "elapsed_seconds": round(perf_counter() - (self._started_at or 0), 3),
            },
        )
        self._reset()

    async def interrupt(self) -> float:
        process = self._process
        if process is None:
            return 0.0
        elapsed = perf_counter() - (self._started_at or perf_counter())
        remaining = max(0.0, self._written_seconds - elapsed)
        process.kill()
        await process.wait()
        self._reset()
        return remaining

    def _reset(self) -> None:
        self._process = None
        self._sample_rate = None
        self._started_at = None
        self._written_seconds = 0.0


class UsbAudioConversation:
    """Run the shared conversation pipeline from an ALSA USB device."""

    sample_rate = 16_000
    session_id = "usb"

    def __init__(
        self,
        *,
        conversation_manager: ConversationManager,
        text_to_speech: TextToSpeech,
        vad_factory: Callable[[], VoiceActivityDetector],
        capture_device: str,
        playback_device: str,
        period_frames: int = 512,
        mixer_card: str = "P10S",
        playback_volume_percent: int = 75,
        capture_volume_percent: int = 100,
        error_message: str = "Desculpe, não consegui concluir a resposta. Tente novamente.",
        enable_barge_in: bool = False,
        process_factory: ProcessFactory = asyncio.create_subprocess_exec,
    ) -> None:
        self._conversation_manager = conversation_manager
        self._text_to_speech = text_to_speech
        self._vad_factory = vad_factory
        self._capture_device = capture_device
        self._playback_device = playback_device
        self._period_frames = period_frames
        self._mixer_card = mixer_card
        self._playback_volume_percent = playback_volume_percent
        self._capture_volume_percent = capture_volume_percent
        self._error_message = error_message
        self._enable_barge_in = enable_barge_in
        self._process_factory = process_factory
        self._capture_process: asyncio.subprocess.Process | None = None
        self._capture_task: asyncio.Task[None] | None = None
        self._conversation_task: asyncio.Task[None] | None = None
        self._vad: VoiceActivityDetector | None = None
        self._playback: AlsaPlayback | None = None
        self._busy = False

    @property
    def running(self) -> bool:
        return self._capture_task is not None and not self._capture_task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._vad = await asyncio.to_thread(self._vad_factory)
        await self._configure_mixer()
        try:
            self._capture_process = await self._process_factory(
                "arecord",
                "-q",
                "-D",
                self._capture_device,
                "-t",
                "raw",
                "-f",
                "S16_LE",
                "-c",
                "1",
                "-r",
                str(self.sample_rate),
                "--period-size",
                str(self._period_frames),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as exc:
            raise UsbAudioUnavailableError(f"Unable to start arecord: {exc}") from exc
        await asyncio.sleep(0)
        if self._capture_process.returncode is not None:
            stderr = await self._read_stderr(self._capture_process)
            raise UsbAudioUnavailableError(
                f"arecord exited with status {self._capture_process.returncode}: {stderr}"
            )
        self._capture_task = asyncio.create_task(self._capture_loop())
        logger.info(
            "USB_AUDIO_STARTED",
            extra={
                "capture_device": self._capture_device,
                "playback_device": self._playback_device,
                "sample_rate": self.sample_rate,
                "period_frames": self._period_frames,
                "barge_in": self._enable_barge_in,
            },
        )

    async def _configure_mixer(self) -> None:
        commands = (
            ("PCM", f"{self._playback_volume_percent}%", "unmute"),
            ("Mic", f"{self._capture_volume_percent}%", "cap"),
        )
        configured = True
        for control, level, state in commands:
            process = await self._process_factory(
                "amixer",
                "-q",
                "-c",
                self._mixer_card,
                "sset",
                control,
                level,
                state,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            return_code = await process.wait()
            if return_code != 0:
                configured = False
                detail = await self._read_stderr(process)
                logger.warning(
                    "USB_MIXER_CONFIGURATION_FAILED",
                    extra={
                        "card": self._mixer_card,
                        "control": control,
                        "return_code": return_code,
                        "detail": detail,
                    },
                )
        if configured:
            logger.info(
                "USB_MIXER_CONFIGURED",
                extra={
                    "card": self._mixer_card,
                    "playback_percent": self._playback_volume_percent,
                    "capture_percent": self._capture_volume_percent,
                },
            )

    async def stop(self) -> None:
        if self._capture_task is not None:
            self._capture_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._capture_task
            self._capture_task = None
        if self._conversation_task is not None:
            self._conversation_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._conversation_task
            self._conversation_task = None
        if self._playback is not None:
            await self._playback.interrupt()
            self._playback = None
        if self._capture_process is not None:
            if self._capture_process.returncode is None:
                self._capture_process.terminate()
                await self._capture_process.wait()
            self._capture_process = None
        self._conversation_manager.forget(self.session_id)
        self._busy = False
        logger.info("USB_AUDIO_STOPPED")

    async def _capture_loop(self) -> None:
        process = self._capture_process
        if process is None or process.stdout is None:
            raise UsbAudioUnavailableError("ALSA capture output is unavailable")
        byte_count = self._period_frames * 2
        try:
            while True:
                data = await process.stdout.readexactly(byte_count)
                samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
                await self._accept_samples(samples)
        except asyncio.IncompleteReadError:
            stderr = await self._read_stderr(process)
            logger.error(
                "USB_CAPTURE_ENDED",
                extra={"return_code": process.returncode, "detail": stderr},
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("USB_CAPTURE_FAILED")

    async def _accept_samples(self, samples: np.ndarray) -> None:
        vad = self._vad
        if vad is None:
            return
        if self._busy and not self._enable_barge_in:
            return
        was_speech = vad.is_speech_detected
        segments = vad.accept(samples)
        if not was_speech and vad.is_speech_detected:
            if self._busy:
                await self._interrupt_conversation()
            logger.info("USB_VAD_SPEECH_STARTED")
        for segment in segments:
            vad.reset()
            self._busy = True
            logger.info(
                "USB_VAD_SPEECH_ENDED",
                extra={"audio_seconds": round(len(segment) / self.sample_rate, 3)},
            )
            self._conversation_task = asyncio.create_task(self._run_turn(segment))
            break

    async def _run_turn(self, samples: np.ndarray) -> None:
        current_task = asyncio.current_task()
        self._playback = AlsaPlayback(self._playback_device, self._process_factory)
        try:
            result = await self._conversation_manager.process(
                self.session_id,
                samples,
                self._emit,
                play_audio=self._playback.play,
            )
            if result is not None:
                await self._playback.finish()
        except asyncio.CancelledError:
            logger.info("USB_CONVERSATION_CANCELLED")
            raise
        except Exception:
            logger.exception("USB_CONVERSATION_FAILED")
            await self._play_error_message()
        finally:
            if self._conversation_task is current_task:
                self._conversation_task = None
                self._playback = None
                self._busy = False
                if self._vad is not None:
                    self._vad.reset()
                logger.info("USB_CONVERSATION_READY")

    async def _play_error_message(self) -> None:
        try:
            if self._playback is None:
                self._playback = AlsaPlayback(
                    self._playback_device, self._process_factory
                )
            synthesis = await self._text_to_speech.synthesize(self._error_message)
            await self._playback.play(synthesis)
            await self._playback.finish()
            logger.info(
                "USB_ERROR_MESSAGE_PLAYED",
                extra={"audio_seconds": round(synthesis.audio_seconds, 3)},
            )
        except Exception:
            logger.exception("USB_ERROR_MESSAGE_FAILED")

    async def _interrupt_conversation(self) -> None:
        task = self._conversation_task
        playback = self._playback
        if task is not None and not task.done():
            task.cancel()
        remaining = 0.0
        if playback is not None:
            remaining = await playback.interrupt()
        if task is not None:
            with suppress(asyncio.CancelledError):
                await task
        self._conversation_task = None
        self._playback = None
        self._busy = False
        logger.info(
            "USB_CONVERSATION_INTERRUPTED",
            extra={"remaining_audio_seconds": round(remaining, 3)},
        )

    async def _emit(self, event: str, payload: dict[str, object]) -> None:
        metrics = {key: value for key, value in payload.items() if key != "text"}
        logger.info(f"USB_EVENT_{event.upper()}", extra=metrics)

    @staticmethod
    async def _read_stderr(process: asyncio.subprocess.Process) -> str:
        if process.stderr is None:
            return ""
        return (await process.stderr.read()).decode(errors="replace").strip()
