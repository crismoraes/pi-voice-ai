"""Filesystem layout and guarded path operations for the story library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoryPaths:
    root: Path

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    @property
    def indexes(self) -> Path:
        return self.root / "indexes"

    @property
    def cache_audio(self) -> Path:
        return self.root / "cache" / "audio"

    def raw(self, language: str) -> Path:
        return self.root / "raw" / language

    def normalized(self, language: str) -> Path:
        return self.root / "normalized" / language

    def stories(self, language: str) -> Path:
        return self.root / "stories" / language

    def derived(self, language: str) -> Path:
        return self.root / "derived" / language

    @property
    def database(self) -> Path:
        return self.indexes / "catalog.db"

    def create(self) -> None:
        for path in (
            self.inbox,
            self.manifests,
            self.reports,
            self.quarantine,
            self.indexes,
            self.cache_audio,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for language in ("en", "pt", "es"):
            for path in (
                self.raw(language),
                self.normalized(language),
                self.stories(language),
                self.derived(language),
            ):
                path.mkdir(parents=True, exist_ok=True)

    def require_inside(self, path: Path) -> Path:
        resolved_root = self.root.resolve()
        resolved = path.resolve()
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise ValueError("Path escapes the story library")
        return resolved
