"""Half-duplex OpenAI Realtime pipeline for Raspberry Pi USB audio."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from openai import AsyncOpenAI

from app.realtime.runtime import realtime_usage_recorder
from app.realtime.usage import RealtimeTurnUsage
from app.tts.base import SynthesisResult

logger = logging.getLogger("pi_voice_ai.realtime")


@dataclass(frozen=True, slots=True)
class RealtimeUsbResult:
    audio_seconds: float


class OpenAIRealtimeUsbPipeline:
    """Keep a Realtime WebSocket session and stream one half-duplex turn at a time."""

    input_sample_rate = 16_000
    realtime_sample_rate = 24_000

    def __init__(
        self,
        *,
        api_key: str,
        model_getter,
        voice_getter,
        instructions: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key) if api_key else None
        self._model_getter = model_getter
        self._voice_getter = voice_getter
        self._instructions = instructions
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._connection = None
        self._connection_model: str | None = None
        self._connection_voice: str | None = None
        self._session_id: str | None = None
        self._lock = asyncio.Lock()

    async def process(self, session_id, samples, emit, play_audio=None):
        if self._client is None:
            raise RuntimeError("OpenAI Realtime is unavailable")
        if play_audio is None:
            raise RuntimeError("Realtime USB playback is unavailable")
        async with self._lock:
            connection = await self._ensure_connection()
            pcm = self._resample_pcm(samples)
            started_at = perf_counter()
            first_audio_seconds: float | None = None
            output_samples = 0
            await connection.input_audio_buffer.clear()
            await connection.input_audio_buffer.append(
                audio=base64.b64encode(pcm).decode("ascii")
            )
            await connection.input_audio_buffer.commit()
            await connection.response.create()
            logger.info(
                "REALTIME_USB_TURN_STARTED",
                extra={
                    "model": self._connection_model,
                    "voice": self._connection_voice,
                    "audio_seconds": round(len(samples) / self.input_sample_rate, 3),
                },
            )
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    async for event in connection:
                        payload = event.to_dict()
                        event_type = payload.get("type")
                        if event_type == "session.created":
                            self._session_id = payload.get("session", {}).get("id")
                        elif event_type == "response.output_audio.delta":
                            raw = base64.b64decode(payload.get("delta", ""))
                            if not raw:
                                continue
                            chunk = np.frombuffer(raw, dtype="<i2").astype(np.float32)
                            chunk /= 32768.0
                            if first_audio_seconds is None:
                                first_audio_seconds = perf_counter() - started_at
                            output_samples += len(chunk)
                            await play_audio(
                                SynthesisResult(
                                    samples=chunk,
                                    sample_rate=self.realtime_sample_rate,
                                    processing_seconds=0,
                                )
                            )
                        elif event_type == "error":
                            raise RuntimeError(
                                payload.get("error", {}).get(
                                    "message", "OpenAI Realtime returned an error"
                                )
                            )
                        elif event_type == "response.done":
                            response = payload.get("response", {})
                            await self._record_usage(
                                response,
                                first_audio_seconds,
                                perf_counter() - started_at,
                            )
                            logger.info(
                                "REALTIME_USB_TURN_COMPLETED",
                                extra={
                                    "model": self._connection_model,
                                    "voice": self._connection_voice,
                                    "first_audio_seconds": round(
                                        first_audio_seconds or 0, 3
                                    ),
                                    "total_seconds": round(
                                        perf_counter() - started_at, 3
                                    ),
                                    "response_audio_seconds": round(
                                        output_samples / self.realtime_sample_rate, 3
                                    ),
                                },
                            )
                            return RealtimeUsbResult(
                                output_samples / self.realtime_sample_rate
                            )
            except BaseException:
                await self.close()
                raise
        raise RuntimeError("OpenAI Realtime closed before completing the response")

    async def _ensure_connection(self):
        model = self._model_getter()
        voice = self._voice_getter()
        if (
            self._connection is not None
            and self._connection_model == model
            and self._connection_voice == voice
        ):
            return self._connection
        await self.close()
        assert self._client is not None
        manager = self._client.realtime.connect(
            model=model,
            extra_headers={
                "OpenAI-Safety-Identifier": hashlib.sha256(
                    b"pi-voice-ai-usb"
                ).hexdigest()
            },
            max_retries=0,
        )
        connection = await manager.enter()
        await connection.session.update(
            session={
                "type": "realtime",
                "instructions": self._instructions,
                "output_modalities": ["audio"],
                "max_output_tokens": self._max_output_tokens,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "turn_detection": None,
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24_000},
                        "voice": voice,
                    },
                },
            }
        )
        self._connection = connection
        self._connection_model = model
        self._connection_voice = voice
        logger.info(
            "REALTIME_USB_CONNECTED", extra={"model": model, "voice": voice}
        )
        return connection

    async def _record_usage(
        self,
        response: dict,
        first_audio_seconds: float | None,
        total_seconds: float,
    ) -> None:
        usage = response.get("usage") or {}
        input_details = usage.get("input_token_details") or {}
        output_details = usage.get("output_token_details") or {}
        cached_details = input_details.get("cached_tokens_details") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        audio_input = int(input_details.get("audio_tokens") or 0)
        audio_output = int(output_details.get("audio_tokens") or 0)
        cached_input = int(input_details.get("cached_tokens") or 0)
        cached_audio = int(cached_details.get("audio_tokens") or 0)
        await realtime_usage_recorder.record(
            "usb",
            RealtimeTurnUsage(
                response_id=response.get("id") or f"unknown-{perf_counter()}",
                session_id=self._session_id,
                model=response.get("model") or self._connection_model or "unknown",
                input_tokens=input_tokens,
                cached_input_tokens=cached_input,
                output_tokens=output_tokens,
                total_tokens=int(usage.get("total_tokens") or input_tokens + output_tokens),
                text_input_tokens=int(
                    input_details.get("text_tokens") or max(input_tokens - audio_input, 0)
                ),
                text_cached_input_tokens=int(
                    cached_details.get("text_tokens")
                    or max(cached_input - cached_audio, 0)
                ),
                text_output_tokens=int(
                    output_details.get("text_tokens")
                    or max(output_tokens - audio_output, 0)
                ),
                audio_input_tokens=audio_input,
                audio_cached_input_tokens=cached_audio,
                audio_output_tokens=audio_output,
                first_audio_seconds=first_audio_seconds,
                total_seconds=total_seconds,
            ),
            self._connection_voice or "unknown",
        )

    def _resample_pcm(self, samples: np.ndarray) -> bytes:
        if not len(samples):
            return b""
        output_count = round(
            len(samples) * self.realtime_sample_rate / self.input_sample_rate
        )
        source = np.arange(len(samples), dtype=np.float64) / self.input_sample_rate
        target = np.arange(output_count, dtype=np.float64) / self.realtime_sample_rate
        resampled = np.interp(target, source, samples)
        return (np.clip(resampled, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

    async def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            await self.close()

    async def select_pipeline(self, pipeline: str) -> None:
        if pipeline != "openai-realtime":
            await self.close()

    async def close(self) -> None:
        connection = self._connection
        self._connection = None
        self._session_id = None
        self._connection_model = None
        self._connection_voice = None
        if connection is not None:
            await connection.close()

    async def shutdown(self) -> None:
        await self.close()
        if self._client is not None:
            await self._client.close()
