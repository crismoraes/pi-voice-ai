"""Typed records used by the story catalog, importer, and voice engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

StoryLanguage = Literal["en", "pt", "es"]
StoryMode = Literal[
    "READ_EXACT", "RETELL", "INTERACTIVE", "CREATE", "ASK_ABOUT_STORY"
]


@dataclass(slots=True)
class SourceMetadata:
    title: str
    language: StoryLanguage
    source_name: str
    source_url: str | None = None
    source_item_id: str | None = None
    author: str | None = None
    editor: str | None = None
    translator: str | None = None
    locale: str | None = None
    category: str | None = None
    themes: list[str] = field(default_factory=list)
    summary: str | None = None
    content_warnings: list[str] = field(default_factory=list)
    age_min: int | None = None
    age_max: int | None = None
    age_review_status: str = "pending"
    license_id: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    rights_evidence: str | None = None
    rights_status: str = "pending"
    review_status: str = "needs_review"
    work_id: str | None = None
    edition_id: str | None = None
    collection: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExtractedSection:
    order: int
    title: str | None
    text: str
    source_locator: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    sections: tuple[ExtractedSection, ...]
    status: str
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n\n".join(section.text for section in self.sections if section.text)


@dataclass(frozen=True, slots=True)
class StorySearchResult:
    story_id: str
    title: str
    author: str | None
    language: str
    category: str | None
    source_name: str
    source_url: str | None
    method: str
    score: float | None


@dataclass(frozen=True, slots=True)
class StoryTurn:
    mode: StoryMode
    language: str
    text_segments: tuple[str, ...] = ()
    llm_prompt: str | None = None
    story_id: str | None = None
