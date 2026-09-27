"""Sanitized runtime technology information for the local dashboard."""

from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


def _model_label(directory_name: str, prefix: str) -> str:
    return directory_name.removeprefix(prefix).replace("-", " ").strip()


@router.get("/info")
async def system_info() -> dict[str, object]:
    """Return active model names and safe processing settings without paths."""
    settings = get_settings()
    stt_model = _model_label(settings.stt_model_dir.name, "sherpa-onnx-whisper-")
    tts_model = _model_label(settings.tts_model_dir.name, "vits-piper-")
    return {
        "version": __version__,
        "llm": {
            "provider": "OpenAI",
            "model": settings.openai_model,
            "processing": "cloud",
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
