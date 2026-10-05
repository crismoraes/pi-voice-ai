import asyncio
import json
import os
import stat
from pathlib import Path

import pytest

from app.runtime.voice_pipeline import (
    VoicePipelineControl,
    VoicePipelineUnavailableError,
)


def make_control(path: Path, *, available: bool = True) -> VoicePipelineControl:
    return VoicePipelineControl(
        default_pipeline="chained",
        selection_path=path,
        realtime_available=available,
        realtime_model="gpt-realtime-2.1",
        realtime_models=("gpt-realtime-2.1",),
        realtime_voice="marin",
        realtime_voices=("marin", "cedar"),
    )


def test_voice_pipeline_selection_persists_and_notifies(tmp_path: Path) -> None:
    async def exercise() -> list[str]:
        control = make_control(tmp_path / "pipeline.json")
        observed: list[str] = []

        async def handler(pipeline: str) -> None:
            observed.append(pipeline)

        control.register(handler)
        await control.select("openai-realtime", "gpt-realtime-2.1", "cedar")
        return observed

    observed = asyncio.run(exercise())
    path = tmp_path / "pipeline.json"
    assert observed == ["openai-realtime"]
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "pipeline": "openai-realtime",
        "realtime_model": "gpt-realtime-2.1",
        "realtime_voice": "cedar",
    }
    restored = make_control(path)
    assert restored.pipeline == "openai-realtime"
    assert restored.realtime_voice == "cedar"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_voice_pipeline_rejects_unavailable_or_unlisted_options(tmp_path: Path) -> None:
    async def exercise() -> None:
        control = make_control(tmp_path / "pipeline.json", available=False)
        with pytest.raises(VoicePipelineUnavailableError):
            await control.select("openai-realtime", "gpt-realtime-2.1", "marin")
        with pytest.raises(ValueError, match="Unsupported Realtime voice"):
            await control.select("chained", "gpt-realtime-2.1", "unknown")
        assert control.pipeline == "chained"

    asyncio.run(exercise())
