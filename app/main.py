"""FastAPI application entry point for the voice assistant."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.assistant import language_model, router as assistant_router
from app.api.health import router as health_router
from app.api.signaling import router as signaling_router
from app.config import PROJECT_ROOT, get_settings
from app.conversation.manager import ConversationManager
from app.logging_config import configure_logging
from app.vad.sherpa_silero import SherpaSileroVoiceActivityDetector
from app.webrtc.manager import peer_manager, speech_to_text, text_to_speech

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("pi_voice_ai")

conversation_manager = ConversationManager(
    speech_to_text=speech_to_text,
    language_model=language_model,
    text_to_speech=text_to_speech,
    max_turns=settings.conversation_max_turns,
    tts_chunk_characters=settings.tts_chunk_characters,
)
peer_manager.configure_conversations(
    conversation_manager,
    lambda: SherpaSileroVoiceActivityDetector(
        model_path=settings.vad_model_path,
        threshold=settings.vad_threshold,
        min_silence_seconds=settings.vad_min_silence_seconds,
        min_speech_seconds=settings.vad_min_speech_seconds,
        max_speech_seconds=settings.vad_max_speech_seconds,
        num_threads=settings.vad_num_threads,
    ),
    enable_barge_in=settings.enable_barge_in,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.gather(speech_to_text.warm_up(), text_to_speech.warm_up())
    logger.info("APP_MODELS_READY")
    logger.info("APP_STARTED", extra={"version": __version__})
    yield
    await peer_manager.close_all()
    await language_model.close()
    logger.info("APP_STOPPED", extra={"version": __version__})


app = FastAPI(
    title="PiVoice AI",
    version=__version__,
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(signaling_router)
app.include_router(assistant_router)
app.mount(
    "/",
    StaticFiles(directory=str(PROJECT_ROOT / "web"), html=True),
    name="web",
)


def run() -> None:
    """Run the application using environment-backed host and port settings."""
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
        ssl_certfile=str(settings.tls_cert_file) if settings.tls_cert_file else None,
        ssl_keyfile=str(settings.tls_key_file) if settings.tls_key_file else None,
    )


if __name__ == "__main__":
    run()
