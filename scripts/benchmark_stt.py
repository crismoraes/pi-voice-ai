"""Benchmark the configured local STT model with an audio file."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import av
import numpy as np
from av.audio.resampler import AudioResampler

from app.config import get_settings
from app.stt.sherpa_whisper import SherpaWhisperSpeechToText


def load_audio(path: Path) -> np.ndarray:
    chunks: list[np.ndarray] = []
    resampler = AudioResampler(format="s16", layout="mono", rate=16_000)
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                samples = (
                    resampled.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
                )
                chunks.append(samples)
        for resampled in resampler.resample(None):
            samples = resampled.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
            chunks.append(samples)
    if not chunks:
        raise ValueError(f"No audio frames found in {path}")
    return np.concatenate(chunks)


async def run(path: Path) -> None:
    settings = get_settings()
    service = SherpaWhisperSpeechToText(
        model_dir=settings.stt_model_dir,
        language=settings.stt_language,
        num_threads=settings.stt_num_threads,
        precision=settings.stt_model_precision,
    )
    result = await service.transcribe(load_audio(path))
    print(
        json.dumps(
            {
                "text": result.text,
                "audio_seconds": round(result.audio_seconds, 3),
                "processing_seconds": round(result.processing_seconds, 3),
                "real_time_factor": round(result.real_time_factor, 3),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.audio_file))


if __name__ == "__main__":
    main()
