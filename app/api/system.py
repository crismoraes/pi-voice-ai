"""Sanitized runtime technology information and LLM selection."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import __version__
from app.api.assistant import language_model
from app.config import get_settings
from app.llm.base import LanguageModelUnavailableError
from app.runtime.current import assistant_control

router = APIRouter(prefix="/api/system", tags=["system"])


class LlmSelection(BaseModel):
    provider: str
    model: str


class AssistantState(BaseModel):
    enabled: bool


def _model_label(directory_name: str, prefix: str) -> str:
    return directory_name.removeprefix(prefix).replace("-", " ").strip()


@router.get("/info")
async def system_info() -> dict[str, object]:
    """Return active model names and safe processing settings without paths."""
    settings = get_settings()
    stt_model = _model_label(settings.stt_model_dir.name, "sherpa-onnx-whisper-")
    tts_model = _model_label(settings.tts_model_dir.name, "vits-piper-")
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
            "engine": settings.stt_engine,
            "model": f"Whisper {stt_model.title()}",
            "language": settings.stt_language,
            "precision": settings.stt_model_precision,
            "threads": settings.stt_num_threads,
            "processing": "local",
            "normalization": settings.stt_normalize_audio,
            "target_peak": settings.stt_target_peak,
            "max_gain": settings.stt_max_gain,
        },
        "tts": {
            "engine": settings.tts_engine,
            "model": tts_model,
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
        await language_model.select(selection.provider, selection.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LanguageModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"provider": language_model.provider, "model": language_model.model}


@router.put("/assistant")
async def set_assistant_state(state: AssistantState) -> dict[str, bool]:
    """Pause or resume microphone-driven processing across all transports."""
    await assistant_control.set_enabled(state.enabled)
    return {"enabled": assistant_control.enabled}
