"""Browser WebRTC bridge and numeric usage ingestion for OpenAI Realtime."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx
from fastapi import APIRouter, Body, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.realtime.runtime import realtime_usage_recorder
from app.realtime.usage import RealtimeTurnUsage
from app.runtime.current import assistant_control, voice_pipeline

logger = logging.getLogger("pi_voice_ai.realtime")
router = APIRouter(prefix="/api/realtime", tags=["realtime"])


class RealtimeUsageReport(BaseModel):
    response_id: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    model: str = Field(min_length=1, max_length=128)
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    text_input_tokens: int = Field(ge=0)
    text_cached_input_tokens: int = Field(ge=0)
    text_output_tokens: int = Field(ge=0)
    audio_input_tokens: int = Field(ge=0)
    audio_cached_input_tokens: int = Field(ge=0)
    audio_output_tokens: int = Field(ge=0)
    first_audio_seconds: float | None = Field(default=None, ge=0, le=3600)
    total_seconds: float | None = Field(default=None, ge=0, le=3600)


def _require_realtime() -> None:
    if not assistant_control.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "The voice assistant is paused")
    if voice_pipeline.pipeline != "openai-realtime":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "OpenAI Realtime is not the active voice pipeline"
        )


@router.post("/calls")
async def create_realtime_call(
    request: Request,
    sdp: str = Body(media_type="application/sdp", min_length=1, max_length=1_000_000),
) -> Response:
    """Exchange a browser SDP offer through the official unified interface."""
    _require_realtime()
    if not sdp.lstrip().startswith("v="):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid SDP offer")
    settings = get_settings()
    api_key = (
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key is not None
        else ""
    )
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAI is unavailable")
    safety_id = hashlib.sha256(
        f"pi-voice-ai-browser:{request.client.host if request.client else 'local'}".encode()
    ).hexdigest()
    session = {
        "type": "realtime",
        "model": voice_pipeline.realtime_model,
        "instructions": settings.llm_instructions,
        "output_modalities": ["audio"],
        "max_output_tokens": settings.realtime_max_output_tokens,
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "eagerness": "auto",
                    "create_response": True,
                    "interrupt_response": True,
                }
            },
            "output": {"voice": voice_pipeline.realtime_voice},
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.realtime_timeout_seconds) as client:
            upstream = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "OpenAI-Safety-Identifier": safety_id,
                },
                files={
                    "sdp": (None, sdp, "application/sdp"),
                    "session": (None, json.dumps(session), "application/json"),
                },
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "REALTIME_CALL_CONNECTION_FAILED",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Unable to connect to OpenAI Realtime",
        ) from exc
    if upstream.status_code >= 400:
        logger.warning(
            "REALTIME_CALL_REJECTED",
            extra={"status_code": upstream.status_code},
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"OpenAI Realtime rejected the session ({upstream.status_code})",
        )
    logger.info(
        "REALTIME_BROWSER_CALL_CREATED",
        extra={
            "model": voice_pipeline.realtime_model,
            "voice": voice_pipeline.realtime_voice,
        },
    )
    return Response(
        upstream.content,
        media_type="application/sdp",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/usage", status_code=status.HTTP_204_NO_CONTENT)
async def record_realtime_usage(report: RealtimeUsageReport) -> None:
    if not any(
        report.model == allowed or report.model.startswith(f"{allowed}-")
        for allowed in voice_pipeline.realtime_models
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported model")
    recorded = await realtime_usage_recorder.record(
        "webrtc",
        RealtimeTurnUsage(**report.model_dump()),
        voice_pipeline.realtime_voice,
    )
    if recorded:
        logger.info(
            "REALTIME_USAGE_RECORDED",
            extra={
                "model": report.model,
                "input_tokens": report.input_tokens,
                "output_tokens": report.output_tokens,
                "audio_input_tokens": report.audio_input_tokens,
                "audio_output_tokens": report.audio_output_tokens,
            },
        )
