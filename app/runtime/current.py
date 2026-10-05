"""Configured process-wide assistant control."""

import asyncio

from app.config import get_settings
from app.runtime.control import AssistantControl

settings = get_settings()
assistant_control = AssistantControl(
    enabled=settings.assistant_enabled,
    state_path=settings.assistant_state_path,
)
pipeline_selection_lock = asyncio.Lock()
