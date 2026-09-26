from pathlib import Path

from app.llm.base import TokenUsage
from app.usage.store import UsagePricing, UsageStore, UsageTurn


def make_store(path: Path) -> UsageStore:
    store = UsageStore(
        path,
        UsagePricing(
            model="gpt-6-luna",
            input_per_million=0.10,
            cached_input_per_million=0.01,
            output_per_million=0.50,
            effective_date="2026-09-26",
        ),
    )
    store.initialize()
    return store


def test_usage_store_records_numeric_history_and_estimates_cost(tmp_path: Path) -> None:
    store = make_store(tmp_path / "usage.db")
    usage = TokenUsage(
        model="gpt-6-luna",
        input_tokens=1_000,
        cached_input_tokens=200,
        output_tokens=100,
        reasoning_output_tokens=20,
        total_tokens=1_100,
    )

    store.record(
        UsageTurn(
            source="usb",
            session_id="private-session-id",
            usage=usage,
            audio_seconds=3.2,
            total_seconds=1.4,
        )
    )

    summary = store.summary(30)
    recent = store.recent(30, 10)
    assert summary["totals"]["total_tokens"] == 1_100
    assert summary["totals"]["estimated_cost_usd"] == 0.000132
    assert recent[0]["source"] == "usb"
    assert "session_hash" not in recent[0]
    assert set(recent[0]).isdisjoint({"transcript", "response_text", "audio"})


def test_usage_store_does_not_price_an_unconfigured_model(tmp_path: Path) -> None:
    store = make_store(tmp_path / "usage.db")
    usage = TokenUsage("another-model", 10, 0, 5, 0, 15)
    assert store.estimate_cost(usage) is None
