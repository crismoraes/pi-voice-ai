import os
import stat
import sqlite3
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
