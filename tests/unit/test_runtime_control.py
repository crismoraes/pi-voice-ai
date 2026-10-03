import asyncio
import json
import os
import stat
from pathlib import Path

from app.runtime.control import AssistantControl


def test_assistant_control_notifies_handlers_and_persists_state(tmp_path: Path) -> None:
    state_path = tmp_path / "assistant-state.json"
    observed: list[bool] = []
    control = AssistantControl(enabled=True, state_path=state_path)

    async def handler(enabled: bool) -> None:
        observed.append(enabled)

    control.register(handler)
    asyncio.run(control.set_enabled(False))

    assert control.enabled is False
    assert observed == [False]
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"enabled": False}
    if os.name == "posix":
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600

    restored = AssistantControl(enabled=True, state_path=state_path)
    assert restored.enabled is False


def test_assistant_control_does_not_repeat_an_unchanged_state(tmp_path: Path) -> None:
    observed: list[bool] = []
    state_path = tmp_path / "assistant-state.json"
    control = AssistantControl(
        enabled=True, state_path=state_path
    )

    async def handler(enabled: bool) -> None:
        observed.append(enabled)

    control.register(handler)
    asyncio.run(control.set_enabled(True))

    assert observed == []
    assert not state_path.exists()
