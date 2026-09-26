"""Privacy-preserving SQLite history for OpenAI token usage."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.llm.base import TokenUsage


@dataclass(frozen=True, slots=True)
class UsagePricing:
    model: str
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float
    effective_date: str


@dataclass(frozen=True, slots=True)
class UsageTurn:
    source: str
    session_id: str | None
    usage: TokenUsage
    request_count: int = 1
    audio_seconds: float | None = None
    first_text_seconds: float | None = None
    total_seconds: float | None = None


class UsageStore:
    """Persist numeric usage only; speech and response text are never stored."""

    def __init__(self, path: Path, pricing: UsagePricing) -> None:
        self.path = path
        self.pricing = pricing

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_turns (
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
                "CREATE INDEX IF NOT EXISTS idx_usage_created_at "
                "ON usage_turns(created_at)"
            )

    def record(self, turn: UsageTurn) -> int:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        session_hash = (
            hashlib.sha256(turn.session_id.encode("utf-8")).hexdigest()[:16]
            if turn.session_id
            else None
        )
        estimated_cost = self.estimate_cost(turn.usage)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO usage_turns (
                    created_at, source, session_hash, model, request_count,
                    input_tokens, cached_input_tokens, output_tokens,
                    reasoning_output_tokens, total_tokens, estimated_cost_usd,
                    audio_seconds, first_text_seconds, total_seconds,
                    pricing_model, pricing_date, input_price_per_million,
                    cached_input_price_per_million, output_price_per_million
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at, turn.source, session_hash, turn.usage.model,
                    turn.request_count, turn.usage.input_tokens,
                    turn.usage.cached_input_tokens, turn.usage.output_tokens,
                    turn.usage.reasoning_output_tokens, turn.usage.total_tokens,
                    estimated_cost, turn.audio_seconds, turn.first_text_seconds,
                    turn.total_seconds, self.pricing.model,
                    self.pricing.effective_date, self.pricing.input_per_million,
                    self.pricing.cached_input_per_million,
                    self.pricing.output_per_million,
                ),
            )
            return int(cursor.lastrowid)

    def estimate_cost(self, usage: TokenUsage) -> float | None:
        if not (
            usage.model == self.pricing.model
            or usage.model.startswith(f"{self.pricing.model}-")
        ):
            return None
        uncached = max(usage.input_tokens - usage.cached_input_tokens, 0)
        return (
            uncached * self.pricing.input_per_million
            + usage.cached_input_tokens * self.pricing.cached_input_per_million
            + usage.output_tokens * self.pricing.output_per_million
        ) / 1_000_000

    def summary(self, days: int) -> dict[str, object]:
        window = f"-{days} days"
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            totals = connection.execute(
                """
                SELECT COUNT(*) AS turns, COALESCE(SUM(request_count), 0) AS requests,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(reasoning_output_tokens), 0) AS reasoning_output_tokens,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                FROM usage_turns WHERE datetime(created_at) >= datetime('now', ?)
                """,
                (window,),
            ).fetchone()
            daily = connection.execute(
                """
                SELECT substr(created_at, 1, 10) AS date, COUNT(*) AS turns,
                       SUM(total_tokens) AS total_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                FROM usage_turns WHERE datetime(created_at) >= datetime('now', ?)
                GROUP BY substr(created_at, 1, 10) ORDER BY date
                """,
                (window,),
            ).fetchall()
        return {
            "days": days,
            "totals": dict(totals),
            "daily": [dict(row) for row in daily],
            "pricing": {
                "model": self.pricing.model,
                "effective_date": self.pricing.effective_date,
                "currency": "USD",
            },
        }

    def recent(self, days: int, limit: int) -> list[dict[str, object]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, created_at, source, model, request_count, input_tokens,
                       cached_input_tokens, output_tokens, reasoning_output_tokens,
                       total_tokens, estimated_cost_usd, audio_seconds,
                       first_text_seconds, total_seconds
                FROM usage_turns WHERE datetime(created_at) >= datetime('now', ?)
                ORDER BY id DESC LIMIT ?
                """,
                (f"-{days} days", limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)
