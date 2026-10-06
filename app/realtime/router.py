"""Route complete audio turns through the selected voice pipeline."""

from __future__ import annotations

import asyncio

from app.conversation.manager import ConversationManager
from app.realtime.usb import OpenAIRealtimeUsbPipeline
from app.runtime.voice_pipeline import VoicePipelineControl


class VoicePipelineRouter:
    """Hold pipeline selection stable for every complete conversation turn."""

    def __init__(
        self,
        *,
        control: VoicePipelineControl,
        chained: ConversationManager,
        realtime: OpenAIRealtimeUsbPipeline,
        selection_lock: asyncio.Lock,
    ) -> None:
        self._control = control
        self._chained = chained
        self._realtime = realtime
        self._selection_lock = selection_lock

    async def process(self, session_id, samples, emit, play_audio=None):
        async with self._selection_lock:
            if self._control.pipeline == "openai-realtime":
                return await self._realtime.process(
                    session_id, samples, emit, play_audio=play_audio
                )
            return await self._chained.process(
                session_id,
                samples,
                emit,
                play_audio=play_audio,
                acquire_pipeline_lock=False,
            )

    def forget(self, session_id: str) -> None:
        self._chained.forget(session_id)

    def confirm_story_playback(self, session_id: str) -> None:
        self._chained.confirm_story_playback(session_id)
