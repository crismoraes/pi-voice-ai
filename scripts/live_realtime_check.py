"""Validate one OpenAI Realtime WebSocket response without storing its content."""

from __future__ import annotations

import argparse
import asyncio
import json

from openai import AsyncOpenAI

from app.config import get_settings


async def check(model: str | None) -> None:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise SystemExit("OPENAI_API_KEY is not configured")
    model = model or settings.realtime_model
    if model not in settings.realtime_model_options:
        raise SystemExit(f"Model is not allowlisted: {model}")
    voice = settings.realtime_voice_options[0]
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    saw_audio = False
    try:
        async with client.realtime.connect(model=model, max_retries=0) as connection:
            await connection.session.update(
                session={
                    "type": "realtime",
                    "instructions": settings.llm_instructions,
                    "output_modalities": ["audio"],
                    "max_output_tokens": 32,
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
            await connection.conversation.item.create(
                item={
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Responda apenas: OK."}
                    ],
                }
            )
            await connection.response.create()
            async with asyncio.timeout(settings.realtime_timeout_seconds):
                async for event in connection:
                    payload = event.to_dict()
                    event_type = payload.get("type")
                    if event_type == "response.output_audio.delta":
                        saw_audio = True
                    elif event_type == "error":
                        raise RuntimeError(
                            payload.get("error", {}).get("message", "Realtime error")
                        )
                    elif event_type == "response.done":
                        response = payload.get("response", {})
                        usage = response.get("usage") or {}
                        print(
                            json.dumps(
                                {
                                    "model": response.get("model") or model,
                                    "voice": voice,
                                    "audio_received": saw_audio,
                                    "input_tokens": usage.get("input_tokens", 0),
                                    "output_tokens": usage.get("output_tokens", 0),
                                    "total_tokens": usage.get("total_tokens", 0),
                                }
                            )
                        )
                        return
    finally:
        await client.close()
    raise RuntimeError("Realtime connection ended before response.done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=get_settings().realtime_model_options)
    asyncio.run(check(parser.parse_args().model))
