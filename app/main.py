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
from app.api.realtime import router as realtime_router
from app.api.signaling import router as signaling_router
from app.api.system import router as system_router
from app.api.usage import router as usage_router
from app.audio.usb import UsbAudioConversation
from app.config import PROJECT_ROOT, get_settings
from app.conversation.manager import ConversationManager
from app.logging_config import configure_logging
from app.realtime.router import VoicePipelineRouter
from app.realtime.usb import OpenAIRealtimeUsbPipeline
from app.runtime.current import (
    assistant_control,
    pipeline_selection_lock,
    voice_pipeline,
)
from app.usage.runtime import usage_store
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
    usage_store=usage_store,
    pipeline_lock=pipeline_selection_lock,
)
realtime_usb = OpenAIRealtimeUsbPipeline(
    api_key=(
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key is not None
        else ""
    ),
    model_getter=lambda: voice_pipeline.realtime_model,
    voice_getter=lambda: voice_pipeline.realtime_voice,
    instructions=settings.llm_instructions,
    max_output_tokens=settings.realtime_max_output_tokens,
    timeout_seconds=settings.realtime_timeout_seconds,
)
voice_pipeline_router = VoicePipelineRouter(
    control=voice_pipeline,
    chained=conversation_manager,
    realtime=realtime_usb,
    selection_lock=pipeline_selection_lock,
)
vad_factory = lambda: SherpaSileroVoiceActivityDetector(
    model_path=settings.vad_model_path,
    threshold=settings.vad_threshold,
    min_silence_seconds=settings.vad_min_silence_seconds,
    min_speech_seconds=settings.vad_min_speech_seconds,
    max_speech_seconds=settings.vad_max_speech_seconds,
    num_threads=settings.vad_num_threads,
)
peer_manager.configure_conversations(
    voice_pipeline_router,
    vad_factory,
    enable_barge_in=settings.enable_barge_in,
)
usb_audio = (
    UsbAudioConversation(
        conversation_manager=voice_pipeline_router,
        text_to_speech=text_to_speech,
        vad_factory=vad_factory,
        capture_device=settings.usb_capture_device,
        playback_device=settings.usb_playback_device,
        period_frames=settings.usb_capture_period_frames,
        capture_retry_seconds=settings.usb_capture_retry_seconds,
        zero_stream_seconds=settings.usb_zero_stream_seconds,
        mixer_card=settings.usb_mixer_card,
        playback_volume_percent=settings.usb_playback_volume_percent,
        capture_volume_percent=settings.usb_capture_volume_percent,
        error_message=settings.usb_error_message,
        enable_barge_in=settings.usb_enable_barge_in,
    )
    if settings.audio_mode == "usb"
    else None
)
assistant_control.register(peer_manager.set_enabled)
voice_pipeline.register(realtime_usb.select_pipeline)
if usb_audio is not None:
    assistant_control.register(usb_audio.set_enabled)
assistant_control.register(realtime_usb.set_enabled)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await asyncio.to_thread(usage_store.initialize)
    except Exception as exc:
        logger.warning(
            "USAGE_STORE_INITIALIZATION_FAILED",
            extra={"error_type": type(exc).__name__},
        )
    await asyncio.gather(speech_to_text.warm_up(), text_to_speech.warm_up())
    logger.info("APP_MODELS_READY")
    await peer_manager.set_enabled(assistant_control.enabled)
    if usb_audio is not None:
        await usb_audio.set_enabled(assistant_control.enabled)
    logger.info(
        "APP_STARTED",
        extra={
            "version": __version__,
            "audio_mode": settings.audio_mode,
            "assistant_enabled": assistant_control.enabled,
        },
    )
    try:
        yield
    finally:
        if usb_audio is not None:
            await usb_audio.stop()
        await peer_manager.close_all()
        await realtime_usb.shutdown()
        await language_model.close()
        await asyncio.gather(speech_to_text.close(), text_to_speech.close())
        logger.info("APP_STOPPED", extra={"version": __version__})


app = FastAPI(
    title="PiVoice AI",
    version=__version__,
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(signaling_router)
app.include_router(assistant_router)
app.include_router(usage_router)
app.include_router(system_router)
app.include_router(realtime_router)
app.mount(
    "/",
    StaticFiles(directory=str(PROJECT_ROOT / "web"), html=True),
    name="web",
)


def run() -> None:
    """Run the application using environment-backed host and port settings."""
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
        timeout_graceful_shutdown=settings.app_graceful_shutdown_seconds,
        ssl_certfile=str(settings.tls_cert_file) if settings.tls_cert_file else None,
        ssl_keyfile=str(settings.tls_key_file) if settings.tls_key_file else None,
    )


if __name__ == "__main__":
    run()
