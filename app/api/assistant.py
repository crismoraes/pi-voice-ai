"""Streaming text assistant endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from time import perf_counter

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.base import LanguageModelError, TokenUsage
from app.llm.llama_cpp import LlamaCppLanguageModel
from app.llm.openai_responses import OpenAIResponsesLanguageModel
from app.llm.selector import LanguageModelSelector
from app.runtime.current import assistant_control, prompt_control
from app.usage.runtime import usage_store
from app.usage.store import UsageTurn

logger = logging.getLogger("pi_voice_ai.llm")
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AssistantRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def encode_event(event: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


settings = get_settings()
openai_key = (
    settings.openai_api_key.get_secret_value()
    if settings.openai_api_key is not None
    else None
)
openai_models = {
    model: OpenAIResponsesLanguageModel(
        api_key=openai_key,
        model=model,
        instructions=lambda: prompt_control.instructions,
        max_output_tokens=settings.openai_max_output_tokens,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    for model in settings.openai_model_options
}
local_models = {
    model: LlamaCppLanguageModel(
        base_url=settings.local_llm_base_url,
        model=model,
        instructions=lambda: prompt_control.instructions,
        max_output_tokens=settings.local_llm_max_output_tokens,
        timeout_seconds=settings.local_llm_timeout_seconds,
    )
    for model in settings.local_llm_model_options
}
language_model = LanguageModelSelector(
    providers={"openai": openai_models, "llama.cpp": local_models},
    default_provider=settings.llm_provider,
    default_model=(
        settings.openai_model
        if settings.llm_provider == "openai"
        else settings.local_llm_model
    ),
    selection_path=settings.llm_selection_path,
)


async def response_events(text: str) -> AsyncIterator[str]:
    started_at = perf_counter()
    first_token_seconds: float | None = None
    output_characters = 0
    token_usage: list[TokenUsage] = []
    logger.info(
        "LLM_STARTED",
        extra={"model": language_model.model, "input_characters": len(text)},
    )
    try:
        async for delta in language_model.stream_response(
            text, on_usage=token_usage.append
        ):
            if first_token_seconds is None:
                first_token_seconds = perf_counter() - started_at
                logger.info(
                    "LLM_FIRST_TOKEN",
                    extra={
                        "model": language_model.model,
                        "seconds": round(first_token_seconds, 3),
                    },
                )
            output_characters += len(delta)
            yield encode_event("delta", {"text": delta})

        total_seconds = perf_counter() - started_at
        if token_usage:
            try:
                await asyncio.to_thread(
                    usage_store.record,
                    UsageTurn(
                        source="assistant_api",
                        session_id=None,
                        usage=token_usage[-1],
                        first_text_seconds=first_token_seconds or total_seconds,
                        total_seconds=total_seconds,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "USAGE_RECORD_FAILED",
                    extra={"error_type": type(exc).__name__},
                )
        logger.info(
            "LLM_COMPLETED",
            extra={
                "model": language_model.model,
                "output_characters": output_characters,
                "first_token_seconds": round(first_token_seconds or total_seconds, 3),
                "total_seconds": round(total_seconds, 3),
            },
        )
        yield encode_event(
            "done",
            {
                "model": language_model.model,
                "first_token_seconds": round(first_token_seconds or total_seconds, 3),
                "total_seconds": round(total_seconds, 3),
            },
        )
    except LanguageModelError as exc:
        logger.warning(
            "LLM_FAILED",
            extra={"model": language_model.model, "error_type": type(exc).__name__},
        )
        yield encode_event("error", {"message": str(exc)})


@router.post("/responses")
async def create_response(request: AssistantRequest) -> StreamingResponse:
    if not assistant_control.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The voice assistant is paused",
        )
    return StreamingResponse(
        response_events(request.text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
