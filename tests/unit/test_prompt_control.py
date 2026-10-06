import asyncio
import json
import os

import pytest

from app.runtime.prompt import PromptControl


def test_prompt_control_persists_revision_and_restores_default(tmp_path) -> None:
    state_path = tmp_path / "data" / "prompt-state.json"
    control = PromptControl(
        default_instructions="Default behavior.",
        state_path=state_path,
        max_characters=100,
    )

    asyncio.run(control.set_instructions("  Custom behavior.  "))
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    restored = PromptControl(
        default_instructions="Default behavior.",
        state_path=state_path,
        max_characters=100,
    )

    assert saved == {"instructions": "Custom behavior.", "revision": 1}
    assert restored.instructions == "Custom behavior."
    assert restored.revision == 1
    assert restored.is_default is False
    if os.name == "posix":
        assert state_path.stat().st_mode & 0o777 == 0o600

    asyncio.run(restored.reset())
    assert restored.instructions == "Default behavior."
    assert restored.revision == 2
    assert restored.is_default is True


def test_prompt_control_rejects_empty_and_oversized_values(tmp_path) -> None:
    control = PromptControl(
        default_instructions="Default.",
        state_path=tmp_path / "prompt.json",
        max_characters=10,
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        asyncio.run(control.set_instructions("   "))
    with pytest.raises(ValueError, match="cannot exceed"):
        asyncio.run(control.set_instructions("x" * 11))
    assert not (tmp_path / "prompt.json").exists()
