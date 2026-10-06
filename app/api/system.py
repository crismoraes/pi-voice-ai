"""Sanitized runtime technology information and LLM selection."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import __version__
from app.api.assistant import language_model
from app.config import get_settings
from app.llm.base import LanguageModelUnavailableError
from app.runtime.current import (
    assistant_control,
    pipeline_selection_lock,
    voice_interrupt_control,
    voice_pipeline,
)
from app.runtime.model_selector import RuntimeModelUnavailableError
from app.runtime.voice_pipeline import VoicePipelineUnavailableError
from app.webrtc.manager import speech_to_text, text_to_speech

router = APIRouter(prefix="/api/system", tags=["system"])


class LlmSelection(BaseModel):
    provider: str
    model: str


class VoiceModelSelection(BaseModel):
    provider: str
    model: str


class AssistantState(BaseModel):
    enabled: bool


class PipelineSelection(BaseModel):
    pipeline: str
    model: str
    voice: str


def _require_chained_pipeline() -> None:
    if voice_pipeline.pipeline != "chained":
        raise HTTPException(
            status_code=409,
            detail="Chained model selectors are disabled while Realtime is active",
        )


async def _voice_options(selector) -> list[dict[str, object]]:
    availability = await selector.status()
    return [
        {
            "provider": provider,
            "models": [
                {
                    "id": model,
                    "label": selector.label(provider, model),
                    "available": availability[provider][model],
                }
                for model in models
            ],
        }
        for provider, models in selector.options.items()
    ]


@router.get("/info")
async def system_info() -> dict[str, object]:
    """Return active model names and safe processing settings without paths."""
    settings = get_settings()
    availability = await language_model.status()
    return {
        "version": __version__,
        "assistant": {
            "enabled": assistant_control.enabled,
            "interrupt_available": voice_interrupt_control.available,
        },
        "pipeline": {
            "id": voice_pipeline.pipeline,
            "label": (
                "OpenAI Realtime"
                if voice_pipeline.pipeline == "openai-realtime"
                else "Chained"
            ),
            "options": [
                {"id": "chained", "label": "Chained", "available": True},
                {
                    "id": "openai-realtime",
                    "label": "OpenAI Realtime",
                    "available": voice_pipeline.realtime_available,
                },
            ],
            "realtime_model": voice_pipeline.realtime_model,
            "realtime_models": list(voice_pipeline.realtime_models),
            "realtime_voice": voice_pipeline.realtime_voice,
            "realtime_voices": list(voice_pipeline.realtime_voices),
            "max_output_tokens": settings.realtime_max_output_tokens,
        },
        "llm": {
            "provider": language_model.provider,
            "model": language_model.model,
            "processing": (
                "cloud" if language_model.provider == "openai" else "local"
            ),
            "options": [
                {
                    "provider": provider,
                    "models": list(models),
                    "available": availability[provider],
                }
                for provider, models in language_model.options.items()
            ],
            "tokens_per_second": language_model.metric(
                "llama.cpp", "last_tokens_per_second"
            ),
        },
        "stt": {
            "provider": speech_to_text.provider,
            "engine": settings.stt_engine,
            "model": speech_to_text.model,
            "model_label": speech_to_text.model_label,
            "options": await _voice_options(speech_to_text),
            "language": settings.stt_language,
            "precision": settings.stt_model_precision,
            "threads": settings.stt_num_threads,
            "processing": "local",
            "normalization": settings.stt_normalize_audio,
            "target_peak": settings.stt_target_peak,
            "max_gain": settings.stt_max_gain,
        },
        "tts": {
            "provider": text_to_speech.provider,
            "engine": settings.tts_engine,
            "model": text_to_speech.model,
            "model_label": text_to_speech.model_label,
            "options": await _voice_options(text_to_speech),
            "threads": settings.tts_num_threads,
            "processing": "local",
        },
        "audio": {
            "mode": settings.audio_mode,
            "vad": settings.vad_engine,
            "vad_threshold": settings.vad_threshold,
            "ending_silence_seconds": settings.vad_min_silence_seconds,
            "barge_in": (
                settings.usb_enable_barge_in
                if settings.audio_mode == "usb"
                else settings.enable_barge_in
            ),
            "tls": settings.tls_enabled,
        },
    }


@router.put("/llm")
async def select_llm(selection: LlmSelection) -> dict[str, str]:
    """Switch future LLM requests after allowlist and readiness checks."""
    _require_chained_pipeline()
    try:
        async with pipeline_selection_lock:
            await language_model.select(selection.provider, selection.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LanguageModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"provider": language_model.provider, "model": language_model.model}


@router.put("/stt")
async def select_stt(selection: VoiceModelSelection) -> dict[str, str]:
    """Switch future turns to an allowlisted STT provider and model."""
    _require_chained_pipeline()
    try:
        async with pipeline_selection_lock:
            await speech_to_text.select(selection.provider, selection.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "provider": speech_to_text.provider,
        "model": speech_to_text.model,
        "model_label": speech_to_text.model_label,
    }


@router.put("/tts")
async def select_tts(selection: VoiceModelSelection) -> dict[str, str]:
    """Switch future turns to an allowlisted TTS provider and model."""
    _require_chained_pipeline()
    try:
        async with pipeline_selection_lock:
            await text_to_speech.select(selection.provider, selection.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "provider": text_to_speech.provider,
        "model": text_to_speech.model,
        "model_label": text_to_speech.model_label,
    }


@router.put("/pipeline")
async def select_pipeline(selection: PipelineSelection) -> dict[str, str]:
    """Switch future voice sessions after allowlist and availability checks."""
    try:
        async with pipeline_selection_lock:
            await voice_pipeline.select(
                selection.pipeline, selection.model, selection.voice
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VoicePipelineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "pipeline": voice_pipeline.pipeline,
        "model": voice_pipeline.realtime_model,
        "voice": voice_pipeline.realtime_voice,
    }


@router.put("/assistant")
async def set_assistant_state(state: AssistantState) -> dict[str, bool]:
    """Pause or resume microphone-driven processing across all transports."""
    await assistant_control.set_enabled(state.enabled)
    return {"enabled": assistant_control.enabled}


@router.post("/assistant/interrupt")
async def interrupt_assistant() -> dict[str, bool]:
    """Stop an active local response without disabling future voice turns."""
    return {"interrupted": await voice_interrupt_control.interrupt()}
