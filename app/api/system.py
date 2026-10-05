"""Sanitized runtime technology information and LLM selection."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import __version__
from app.api.assistant import language_model
from app.config import get_settings
from app.llm.base import LanguageModelUnavailableError
from app.runtime.current import assistant_control, pipeline_selection_lock
from app.runtime.model_selector import RuntimeModelUnavailableError
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
        "assistant": {"enabled": assistant_control.enabled},
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
            "tls": settings.tls_enabled,
        },
    }


@router.put("/llm")
async def select_llm(selection: LlmSelection) -> dict[str, str]:
    """Switch future LLM requests after allowlist and readiness checks."""
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


@router.put("/assistant")
async def set_assistant_state(state: AssistantState) -> dict[str, bool]:
    """Pause or resume microphone-driven processing across all transports."""
    await assistant_control.set_enabled(state.enabled)
    return {"enabled": assistant_control.enabled}
