"""Compare TTS text chunk sizes using the configured local voice."""

from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

from app.config import get_settings
from app.tts.chunking import split_text_for_speech
from app.tts.sherpa_piper import SherpaPiperTextToSpeech

DEFAULT_TEXT = (
    "Um assistente de voz precisa responder rapidamente e continuar natural. "
    "Ao dividir textos longos em sentenças, o primeiro áudio pode começar enquanto "
    "as próximas partes ainda estão sendo sintetizadas no Raspberry Pi. "
    "Este parágrafo mede o equilíbrio entre latência, continuidade e custo total."
)


async def benchmark(chunk_sizes: list[int], repeats: int) -> list[dict[str, object]]:
    settings = get_settings()
    service = SherpaPiperTextToSpeech(
        model_dir=settings.tts_model_dir,
        num_threads=settings.tts_num_threads,
        speed=settings.tts_speed,
        max_text_characters=settings.tts_max_text_characters,
    )
    await service.synthesize("aquecimento")
    results: list[dict[str, object]] = []
    for chunk_size in chunk_sizes:
        runs: list[dict[str, float | int]] = []
        for _ in range(repeats):
            chunks = split_text_for_speech(DEFAULT_TEXT, chunk_size)
            started_at = perf_counter()
            first_audio_seconds = 0.0
            processing_seconds = 0.0
            audio_seconds = 0.0
            for index, chunk in enumerate(chunks):
                synthesis = await service.synthesize(chunk)
                if index == 0:
                    first_audio_seconds = perf_counter() - started_at
                processing_seconds += synthesis.processing_seconds
                audio_seconds += synthesis.audio_seconds
            runs.append(
                {
                    "chunks": len(chunks),
                    "first_audio_seconds": round(first_audio_seconds, 3),
                    "processing_seconds": round(processing_seconds, 3),
                    "audio_seconds": round(audio_seconds, 3),
                }
            )
        results.append({"chunk_characters": chunk_size, "runs": runs})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", action="append", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.chunk_size, args.repeats))))


if __name__ == "__main__":
    main()
