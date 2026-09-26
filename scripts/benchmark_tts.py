"""Benchmark the configured local TTS model."""

from __future__ import annotations

import argparse
import asyncio
import json
import wave
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.tts.sherpa_piper import SherpaPiperTextToSpeech


async def benchmark(text: str, output: Path | None) -> dict[str, object]:
    settings = get_settings()
    service = SherpaPiperTextToSpeech(
        model_dir=settings.tts_model_dir,
        num_threads=settings.tts_num_threads,
        speed=settings.tts_speed,
        max_text_characters=settings.tts_max_text_characters,
    )
    result = await service.synthesize(text)
    if output is not None:
        pcm = (np.clip(result.samples, -1, 1) * 32767).astype(np.int16)
        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(result.sample_rate)
            wav_file.writeframes(pcm.tobytes())
    return {
        "audio_seconds": round(result.audio_seconds, 3),
        "processing_seconds": round(result.processing_seconds, 3),
        "real_time_factor": round(result.real_time_factor, 3),
        "sample_rate": result.sample_rate,
        "output": str(output) if output is not None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.text, args.output))))


if __name__ == "__main__":
    main()
