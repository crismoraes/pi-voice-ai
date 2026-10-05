import asyncio
import json

import pytest

from app.runtime.model_selector import (
    PersistentRuntimeModelSelector,
    RuntimeModelOption,
    RuntimeModelUnavailableError,
)


class FakeRuntimeModel:
    def __init__(self, *, available: bool = True, fail_warm_up: bool = False) -> None:
        self.available = available
        self.fail_warm_up = fail_warm_up
        self.warm_ups = 0
        self.closes = 0

    def is_available(self) -> bool:
        return self.available

    async def warm_up(self) -> None:
        self.warm_ups += 1
        if self.fail_warm_up:
            raise RuntimeError("load failed")

    async def close(self) -> None:
        self.closes += 1


def test_runtime_selector_persists_warms_and_releases_previous_model(tmp_path) -> None:
    async def run() -> None:
        first = FakeRuntimeModel()
        second = FakeRuntimeModel()
        selection_path = tmp_path / "selection.json"
        providers = {
            "local": {
                "small": RuntimeModelOption(first, "Small"),
                "tiny": RuntimeModelOption(second, "Tiny"),
            }
        }
        selector = PersistentRuntimeModelSelector(
            component="STT",
            providers=providers,
            default_provider="local",
            default_model="small",
            selection_path=selection_path,
        )

        await selector.select("local", "tiny")

        assert selector.model == "tiny"
        assert second.warm_ups == 1
        assert first.closes == 1
        assert json.loads(selection_path.read_text(encoding="utf-8")) == {
            "provider": "local",
            "model": "tiny",
        }
        restored = PersistentRuntimeModelSelector(
            component="STT",
            providers=providers,
            default_provider="local",
            default_model="small",
            selection_path=selection_path,
        )
        assert restored.model == "tiny"

    asyncio.run(run())


def test_runtime_selector_keeps_current_model_when_candidate_fails(tmp_path) -> None:
    async def run() -> None:
        current = FakeRuntimeModel()
        failing = FakeRuntimeModel(fail_warm_up=True)
        selector = PersistentRuntimeModelSelector(
            component="TTS",
            providers={
                "local": {
                    "current": RuntimeModelOption(current, "Current"),
                    "failing": RuntimeModelOption(failing, "Failing"),
                }
            },
            default_provider="local",
            default_model="current",
            selection_path=tmp_path / "selection.json",
        )

        with pytest.raises(RuntimeModelUnavailableError, match="Unable to prepare"):
            await selector.select("local", "failing")

        assert selector.model == "current"
        assert current.closes == 0
        assert failing.closes == 1

    asyncio.run(run())


def test_runtime_selector_rejects_missing_or_unavailable_models(tmp_path) -> None:
    async def run() -> None:
        selector = PersistentRuntimeModelSelector(
            component="STT",
            providers={
                "local": {
                    "missing": RuntimeModelOption(
                        FakeRuntimeModel(available=False), "Missing"
                    )
                }
            },
            default_provider="local",
            default_model="missing",
            selection_path=tmp_path / "selection.json",
        )

        with pytest.raises(ValueError, match="Unsupported STT"):
            await selector.select("cloud", "unknown")
        with pytest.raises(RuntimeModelUnavailableError, match="not installed"):
            await selector.select("local", "missing")

    asyncio.run(run())


def test_runtime_selector_persists_an_explicit_default_selection(tmp_path) -> None:
    async def run() -> None:
        selection_path = tmp_path / "selection.json"
        selector = PersistentRuntimeModelSelector(
            component="TTS",
            providers={
                "local": {
                    "voice": RuntimeModelOption(FakeRuntimeModel(), "Voice")
                }
            },
            default_provider="local",
            default_model="voice",
            selection_path=selection_path,
        )

        await selector.select("local", "voice")

        assert selection_path.is_file()
        assert json.loads(selection_path.read_text(encoding="utf-8"))["model"] == "voice"

    asyncio.run(run())
