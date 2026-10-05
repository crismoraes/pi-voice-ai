"""Configured process-wide assistant control."""

import asyncio

from app.config import get_settings
from app.runtime.control import AssistantControl
from app.runtime.voice_pipeline import VoicePipelineControl

settings = get_settings()
assistant_control = AssistantControl(
    enabled=settings.assistant_enabled,
    state_path=settings.assistant_state_path,
)
pipeline_selection_lock = asyncio.Lock()
voice_pipeline = VoicePipelineControl(
    default_pipeline=settings.voice_pipeline,
    selection_path=settings.pipeline_selection_path,
    realtime_available=bool(
        settings.openai_api_key and settings.openai_api_key.get_secret_value()
    ),
    realtime_model=settings.realtime_model,
    realtime_models=settings.realtime_model_options,
    realtime_voice=settings.realtime_voice,
    realtime_voices=settings.realtime_voice_options,
)
