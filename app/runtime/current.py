"""Configured process-wide assistant control."""

import asyncio

from app.config import get_settings
from app.runtime.control import AssistantControl, VoiceInterruptControl
from app.runtime.prompt import PromptControl
from app.runtime.voice_pipeline import VoicePipelineControl

settings = get_settings()
assistant_control = AssistantControl(
    enabled=settings.assistant_enabled,
    state_path=settings.assistant_state_path,
)
voice_interrupt_control = VoiceInterruptControl()
pipeline_selection_lock = asyncio.Lock()
prompt_control = PromptControl(
    default_instructions=settings.llm_instructions,
    state_path=settings.prompt_state_path,
    max_characters=settings.prompt_max_characters,
)
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
