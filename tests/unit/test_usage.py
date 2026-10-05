import os
import stat
import sqlite3
from pathlib import Path

from app.llm.base import TokenUsage
from app.usage.store import (
    RealtimeUsagePricing,
    UsagePricing,
    UsageStore,
    UsageTurn,
)


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
        (
            RealtimeUsagePricing(
                model="gpt-realtime-2.1",
                text_input_per_million=4.00,
                text_cached_input_per_million=0.40,
                text_output_per_million=24.00,
                audio_input_per_million=32.00,
                audio_cached_input_per_million=0.40,
                audio_output_per_million=64.00,
                effective_date="2026-10-05",
            ),
            RealtimeUsagePricing(
                model="gpt-realtime-2.1-mini",
                text_input_per_million=0.60,
                text_cached_input_per_million=0.06,
                text_output_per_million=2.40,
                audio_input_per_million=10.00,
                audio_cached_input_per_million=0.30,
                audio_output_per_million=20.00,
                effective_date="2026-10-05",
            ),
        ),
    )
    store.initialize()
    return store


def test_usage_store_records_numeric_history_and_estimates_cost(tmp_path: Path) -> None:
    database_path = tmp_path / "usage.db"
    store = make_store(database_path)
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
            llm_provider="openai",
            stt_provider="sherpa-onnx",
            stt_model="whisper-small-int8",
            tts_provider="sherpa-onnx",
            tts_model="pt_BR-jeff-medium",
        )
    )

    summary = store.summary(30)
    recent = store.recent(30, 10)
    assert summary["totals"]["total_tokens"] == 1_100
    assert summary["totals"]["estimated_cost_usd"] == 0.000132
    assert recent[0]["source"] == "usb"
    assert recent[0]["pipeline"] == "chained"
    assert recent[0]["llm_provider"] == "openai"
    assert recent[0]["stt_model"] == "whisper-small-int8"
    assert recent[0]["tts_model"] == "pt_BR-jeff-medium"
    assert recent[0]["audio_input_tokens"] == 0
    assert recent[0]["audio_output_tokens"] == 0
    assert "session_hash" not in recent[0]
    assert set(recent[0]).isdisjoint({"transcript", "response_text", "audio"})
    if os.name == "posix":
        assert stat.S_IMODE(database_path.stat().st_mode) == 0o600


def test_usage_store_does_not_price_an_unconfigured_model(tmp_path: Path) -> None:
    store = make_store(tmp_path / "usage.db")
    usage = TokenUsage("another-model", 10, 0, 5, 0, 15)
    assert store.estimate_cost(usage) is None


def test_usage_store_prices_realtime_text_audio_and_cache_separately(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path / "usage.db")
    usage = TokenUsage("gpt-realtime-2.1", 150, 30, 70, 0, 220)
    turn = UsageTurn(
        source="webrtc",
        session_id="session",
        usage=usage,
        pipeline="openai-realtime",
        llm_provider="openai",
        tts_provider="openai",
        tts_model="marin",
        text_input_tokens=50,
        text_cached_input_tokens=10,
        text_output_tokens=20,
        audio_input_tokens=100,
        audio_cached_input_tokens=20,
        audio_output_tokens=50,
    )

    store.record(turn)
    recent = store.recent(30, 1)[0]

    expected = (
        40 * 4.00 + 10 * 0.40 + 20 * 24.00
        + 80 * 32.00 + 20 * 0.40 + 50 * 64.00
    ) / 1_000_000
    assert recent["estimated_cost_usd"] == expected
    assert recent["audio_cached_input_tokens"] == 20
    assert recent["text_input_tokens"] == 50


def test_usage_store_uses_mini_prices_for_alias_and_snapshot(tmp_path: Path) -> None:
    store = make_store(tmp_path / "usage.db")
    turn = UsageTurn(
        source="usb",
        session_id="mini-session",
        usage=TokenUsage(
            "gpt-realtime-2.1-mini-2026-10-01", 150, 30, 70, 0, 220
        ),
        pipeline="openai-realtime",
        llm_provider="openai",
        tts_provider="openai",
        tts_model="marin",
        text_input_tokens=50,
        text_cached_input_tokens=10,
        text_output_tokens=20,
        audio_input_tokens=100,
        audio_cached_input_tokens=20,
        audio_output_tokens=50,
    )

    store.record(turn)
    recent = store.recent(30, 1)[0]

    expected = (
        40 * 0.60 + 10 * 0.06 + 20 * 2.40
        + 80 * 10.00 + 20 * 0.30 + 50 * 20.00
    ) / 1_000_000
    assert recent["estimated_cost_usd"] == expected
    with sqlite3.connect(store.path) as connection:
        snapshot = connection.execute(
            "SELECT pricing_model, input_price_per_million, "
            "audio_input_price_per_million FROM usage_turns"
        ).fetchone()
    assert snapshot == ("gpt-realtime-2.1-mini", 0.60, 10.00)


def test_usage_store_migrates_existing_history_without_backfilling_models(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "usage.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE usage_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                session_hash TEXT,
                model TEXT NOT NULL,
                request_count INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                reasoning_output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL,
                audio_seconds REAL,
                first_text_seconds REAL,
                total_seconds REAL,
                pricing_model TEXT NOT NULL,
                pricing_date TEXT NOT NULL,
                input_price_per_million REAL NOT NULL,
                cached_input_price_per_million REAL NOT NULL,
                output_price_per_million REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO usage_turns (
                created_at, source, model, request_count, input_tokens,
                cached_input_tokens, output_tokens, reasoning_output_tokens,
                total_tokens, pricing_model, pricing_date,
                input_price_per_million, cached_input_price_per_million,
                output_price_per_million
            ) VALUES ('2026-10-05T18:33:00+00:00', 'usb', 'gpt-6-luna',
                      1, 10, 0, 5, 0, 15, 'gpt-6-luna', '2026-09-26',
                      0.10, 0.01, 0.50)
            """
        )

    store = make_store(database_path)
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(usage_turns)")
        }

    assert columns["pipeline"][4] == "'chained'"
    assert "stt_model" in columns
    assert "tts_model" in columns
    assert "audio_input_tokens" in columns
    assert "audio_output_tokens" in columns
    migrated = store.recent(365, 10)[0]
    assert migrated["pipeline"] == "chained"
    assert migrated["stt_model"] is None
    assert migrated["tts_model"] is None
