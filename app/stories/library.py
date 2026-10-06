"""SQLite catalog, guarded ingestion, review, indexing, and approved search."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import numpy as np
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.stories.extract import SUPPORTED_SUFFIXES, extract_document
from app.stories.paths import StoryPaths
from app.stories.types import ExtractionResult, SourceMetadata, StorySearchResult
from app.stories.embeddings import LocalEmbeddingClient

SCHEMA_VERSION = 1
LANGUAGES = {"en", "pt", "es"}
EMBEDDING_CONTEXT_TOKENS = 512
EMBEDDING_TOKENIZER = "multilingual-e5 embedded SentencePiece"
CHUNK_TARGET_WORDS = 180
CHUNK_OVERLAP_WORDS = 30


class StoryNotAvailableError(LookupError):
    """Raised when a story is absent or fails required access filters."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if os.name == "posix":
        temporary.chmod(0o600)
    temporary.replace(path)


class StoryLibrary:
    """Own the private catalog and enforce approval on every read path."""

    def __init__(self, root: Path, embedding_client: LocalEmbeddingClient | None = None) -> None:
        self.paths = StoryPaths(root)
        self.embedding_client = embedding_client

    def initialize(self) -> None:
        self.paths.create()
        with self._connect() as database:
            database.executescript(
                """
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    text_sha256 TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL CHECK(language IN ('en','pt','es')),
                    locale TEXT,
                    author TEXT,
                    editor TEXT,
                    translator TEXT,
                    category TEXT,
                    themes_json TEXT NOT NULL,
                    summary TEXT,
                    content_warnings_json TEXT NOT NULL,
                    age_min INTEGER,
                    age_max INTEGER,
                    age_review_status TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT,
                    source_item_id TEXT,
                    license_id TEXT,
                    license_url TEXT,
                    attribution TEXT,
                    rights_evidence TEXT,
                    rights_status TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    extraction_status TEXT NOT NULL,
                    raw_path TEXT NOT NULL,
                    normalized_path TEXT,
                    work_id TEXT,
                    edition_id TEXT,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stories (
                    story_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    section_order INTEGER NOT NULL,
                    source_locator TEXT,
                    word_count INTEGER NOT NULL,
                    estimated_duration REAL NOT NULL,
                    duration_estimation_method TEXT NOT NULL,
                    index_status TEXT NOT NULL DEFAULT 'pending',
                    story_path TEXT NOT NULL,
                    UNIQUE(document_id, section_order)
                );
                CREATE TABLE IF NOT EXISTS sections (
                    story_id TEXT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
                    section_order INTEGER NOT NULL,
                    title TEXT,
                    text TEXT NOT NULL,
                    source_locator TEXT,
                    PRIMARY KEY(story_id, section_order)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    story_id TEXT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
                    chunk_order INTEGER NOT NULL,
                    section_order INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    source_locator TEXT,
                    text_sha256 TEXT NOT NULL,
                    UNIQUE(story_id, chunk_order)
                );
                CREATE TABLE IF NOT EXISTS story_progress (
                    session_id TEXT PRIMARY KEY,
                    story_id TEXT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
                    next_section INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS story_vectors (
                    story_id TEXT PRIMARY KEY REFERENCES stories(story_id) ON DELETE CASCADE,
                    model TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunk_vectors (
                    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                    model TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS story_document_idx ON stories(document_id);
                CREATE INDEX IF NOT EXISTS story_language_review_idx
                    ON documents(language, rights_status, review_status);
                """
            )
            database.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)",
                (str(SCHEMA_VERSION),),
            )
            try:
                database.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS story_fts USING fts5(story_id UNINDEXED, title, summary, themes, language UNINDEXED, tokenize='unicode61 remove_diacritics 2')"
                )
                database.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(chunk_id UNINDEXED, story_id UNINDEXED, text, language UNINDEXED, tokenize='unicode61 remove_diacritics 2')"
                )
                database.execute(
                    "INSERT OR REPLACE INTO metadata(key,value) VALUES('fts5','available')"
                )
            except sqlite3.OperationalError:
                database.execute(
                    "INSERT OR REPLACE INTO metadata(key,value) VALUES('fts5','unavailable')"
                )

    def _connect(self) -> sqlite3.Connection:
        self.paths.indexes.mkdir(parents=True, exist_ok=True)
        database = sqlite3.connect(self.paths.database)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys=ON")
        database.execute("PRAGMA journal_mode=WAL")
        return database

    def ingest_inbox(self, input_path: Path | None = None) -> list[dict[str, object]]:
        self.initialize()
        source = self.paths.require_inside(input_path or self.paths.inbox)
        candidates = [source] if source.is_file() else sorted(source.iterdir())
        results = []
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            sidecar = path.with_suffix(path.suffix + ".json")
            if not sidecar.is_file():
                sidecar = path.with_suffix(".json")
            try:
                metadata = self._load_metadata(sidecar, path)
                results.append(self.ingest_file(path, metadata))
            except Exception as exc:
                results.append(
                    {
                        "file": path.name,
                        "status": "failed",
                        "reason": type(exc).__name__,
                        "detail": str(exc),
                    }
                )
        self.write_report("ingest-latest.json", {"generated_at": _utc_now(), "items": results})
        return results

    def _load_metadata(self, sidecar: Path, document: Path) -> SourceMetadata:
        if sidecar.is_file():
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        else:
            payload = {
                "title": document.stem,
                "language": "pt",
                "source_name": "manual-import",
                "rights_status": "pending",
                "review_status": "needs_review",
            }
        allowed = SourceMetadata.__dataclass_fields__.keys()
        return SourceMetadata(**{key: value for key, value in payload.items() if key in allowed})

    def ingest_file(self, path: Path, metadata: SourceMetadata) -> dict[str, object]:
        self.initialize()
        source = path.resolve()
        if not source.is_file() or source.is_symlink():
            raise ValueError("Story input must be a regular file")
        if metadata.language not in LANGUAGES:
            raise ValueError("Story language must be en, pt, or es")
        if source.stat().st_size > 100_000_000:
            raise ValueError("Story file exceeds 100 MB")
        digest = _sha256(source)
        document_id = _stable_id(
            "doc",
            metadata.source_name,
            metadata.source_item_id or "",
            metadata.edition_id or "",
            digest,
        )
        with self._connect() as database:
            existing = database.execute(
                "SELECT document_id, extraction_status FROM documents WHERE text_sha256=?",
                (digest,),
            ).fetchone()
            if existing:
                return {
                    "file": source.name,
                    "document_id": existing["document_id"],
                    "status": "duplicate",
                    "extraction_status": existing["extraction_status"],
                }

        raw_name = f"{document_id}{source.suffix.lower()}"
        raw_path = self.paths.raw(metadata.language) / raw_name
        if not raw_path.exists():
            temporary = raw_path.with_suffix(raw_path.suffix + ".tmp")
            shutil.copyfile(source, temporary)
            if _sha256(temporary) != digest:
                temporary.unlink(missing_ok=True)
                raise ValueError("Copied story hash does not match source")
            temporary.replace(raw_path)

        extraction = extract_document(raw_path)
        normalized_path = self.paths.normalized(metadata.language) / f"{document_id}.json"
        _atomic_json(
            normalized_path,
            {
                "document_id": document_id,
                "metadata": metadata.as_dict(),
                "text_sha256": digest,
                "extraction_status": extraction.status,
                "warnings": list(extraction.warnings),
                "sections": [asdict(section) for section in extraction.sections],
            },
        )
        stories = self._story_groups(metadata, extraction)
        with self._connect() as database:
            database.execute(
                """INSERT INTO documents (
                    document_id,text_sha256,title,language,locale,author,editor,translator,
                    category,themes_json,summary,content_warnings_json,age_min,age_max,
                    age_review_status,source_name,source_url,source_item_id,license_id,
                    license_url,attribution,rights_evidence,rights_status,review_status,
                    extraction_status,raw_path,normalized_path,work_id,edition_id,imported_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    document_id,
                    digest,
                    metadata.title,
                    metadata.language,
                    metadata.locale,
                    metadata.author,
                    metadata.editor,
                    metadata.translator,
                    metadata.category,
                    json.dumps(metadata.themes, ensure_ascii=False),
                    metadata.summary,
                    json.dumps(metadata.content_warnings, ensure_ascii=False),
                    metadata.age_min,
                    metadata.age_max,
                    metadata.age_review_status,
                    metadata.source_name,
                    metadata.source_url,
                    metadata.source_item_id,
                    metadata.license_id,
                    metadata.license_url,
                    metadata.attribution,
                    metadata.rights_evidence,
                    metadata.rights_status,
                    metadata.review_status,
                    extraction.status,
                    str(raw_path.relative_to(self.paths.root)),
                    str(normalized_path.relative_to(self.paths.root)),
                    metadata.work_id,
                    metadata.edition_id,
                    _utc_now(),
                ),
            )
            for story_order, (title, sections) in enumerate(stories, 1):
                story_id = _stable_id("story", document_id, str(story_order), title)
                text = "\n\n".join(section.text for section in sections)
                word_count = len(text.split())
                story_path = self.paths.stories(metadata.language) / f"{story_id}.json"
                story_payload = {
                    "story_id": story_id,
                    "document_id": document_id,
                    "title": title,
                    "language": metadata.language,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "sections": [asdict(section) for section in sections],
                }
                _atomic_json(story_path, story_payload)
                database.execute(
                    """INSERT INTO stories (
                        story_id,document_id,title,section_order,source_locator,word_count,
                        estimated_duration,duration_estimation_method,index_status,story_path
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        story_id,
                        document_id,
                        title,
                        story_order,
                        sections[0].source_locator if sections else None,
                        word_count,
                        round(word_count / 150, 2),
                        "word_count_150_wpm",
                        "pending",
                        str(story_path.relative_to(self.paths.root)),
                    ),
                )
                for section_order, section in enumerate(sections, 1):
                    database.execute(
                        "INSERT INTO sections VALUES(?,?,?,?,?)",
                        (story_id, section_order, section.title, section.text, section.source_locator),
                    )
        return {
            "file": source.name,
            "document_id": document_id,
            "status": "imported",
            "extraction_status": extraction.status,
            "stories": len(stories),
            "warnings": list(extraction.warnings),
        }

    @staticmethod
    def _story_groups(metadata: SourceMetadata, extraction: ExtractionResult):
        if not extraction.sections:
            return []
        if metadata.collection and len(extraction.sections) > 1:
            return [
                (section.title or f"{metadata.title} — {section.order}", [section])
                for section in extraction.sections
            ]
        if metadata.collection and len(extraction.sections) == 1:
            text = extraction.sections[0].text
            matches = list(re.finditer(r"(?m)^#{1,2}\s+(.+?)\s*$", text))
            if matches:
                groups = []
                for index, match in enumerate(matches):
                    start = match.end()
                    end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                    body = text[start:end].strip()
                    if body:
                        groups.append((match.group(1).strip(), [type(extraction.sections[0])(1, match.group(1).strip(), body, f"heading:{index + 1}")]))
                if groups:
                    return groups
            roman_matches = list(
                re.finditer(r"(?m)^([IVXLCDM]{1,8})\n\n([^\n]{4,180})\n\n", text)
            )
            if len(roman_matches) >= 3:
                groups = []
                for index, match in enumerate(roman_matches):
                    end = roman_matches[index + 1].start() if index + 1 < len(roman_matches) else len(text)
                    body = text[match.end():end].strip()
                    title = re.sub(r"\[[A-Z]+\]$", "", match.group(2)).strip(' "')
                    if body:
                        groups.append(
                            (
                                title,
                                [type(extraction.sections[0])(1, title, body, f"roman:{match.group(1)}")],
                            )
                        )
                if groups:
                    return groups
        return [(metadata.title, list(extraction.sections))]

    def review(self, document_id: str, decision: str) -> None:
        if decision not in {"approved", "rejected", "needs_review"}:
            raise ValueError("Unsupported review decision")
        with self._connect() as database:
            result = database.execute(
                "UPDATE documents SET review_status=? WHERE document_id=?",
                (decision, document_id),
            )
            if result.rowcount != 1:
                raise KeyError(document_id)
        self._invalidate_audio_cache()

    def set_rights(self, document_id: str, status: str) -> None:
        if status not in {"approved", "blocked", "pending"}:
            raise ValueError("Unsupported rights decision")
        with self._connect() as database:
            result = database.execute(
                "UPDATE documents SET rights_status=? WHERE document_id=?",
                (status, document_id),
            )
            if result.rowcount != 1:
                raise KeyError(document_id)
        self._invalidate_audio_cache()

    def _invalidate_audio_cache(self) -> None:
        for path in self.paths.cache_audio.glob("*.npz"):
            path.unlink(missing_ok=True)

    def build_index(self, *, incremental: bool = True) -> dict[str, object]:
        self.initialize()
        indexed = 0
        semantic = bool(self.embedding_client and self.embedding_client.ready())
        with self._connect() as database:
            fts = database.execute("SELECT value FROM metadata WHERE key='fts5'").fetchone()[0] == "available"
            rows = database.execute(
                """SELECT s.story_id,s.title,s.index_status,d.language,d.summary,d.themes_json
                   FROM stories s JOIN documents d USING(document_id)
                   WHERE (?=0 OR s.index_status!='indexed')""",
                (1 if incremental else 0,),
            ).fetchall()
            if not incremental:
                database.execute("DELETE FROM chunks")
                database.execute("DELETE FROM story_vectors")
                database.execute("DELETE FROM chunk_vectors")
                if fts:
                    database.execute("DELETE FROM story_fts")
                    database.execute("DELETE FROM chunk_fts")
            for row in rows:
                story_id = row["story_id"]
                database.execute("DELETE FROM chunks WHERE story_id=?", (story_id,))
                if fts:
                    database.execute("DELETE FROM story_fts WHERE story_id=?", (story_id,))
                    database.execute("DELETE FROM chunk_fts WHERE story_id=?", (story_id,))
                    database.execute(
                        "INSERT INTO story_fts VALUES(?,?,?,?,?)",
                        (story_id, row["title"], row["summary"] or "", " ".join(json.loads(row["themes_json"])), row["language"]),
                    )
                sections = database.execute(
                    "SELECT section_order,text,source_locator FROM sections WHERE story_id=? ORDER BY section_order",
                    (story_id,),
                ).fetchall()
                chunks = self._chunk_sections(sections)
                chunk_records: list[tuple[str, int, str, str]] = []
                for order, (section_order, text, locator) in enumerate(chunks, 1):
                    chunk_id = _stable_id("chunk", story_id, str(order), hashlib.sha256(text.encode()).hexdigest())
                    database.execute(
                        """INSERT INTO chunks (
                            chunk_id,story_id,chunk_order,section_order,text,source_locator,text_sha256
                        ) VALUES(?,?,?,?,?,?,?)""",
                        (chunk_id, story_id, order, section_order, text, locator, hashlib.sha256(text.encode()).hexdigest()),
                    )
                    if fts:
                        database.execute("INSERT INTO chunk_fts VALUES(?,?,?,?)", (chunk_id, story_id, text, row["language"]))
                    chunk_records.append((chunk_id, section_order, text, locator))
                if semantic and self.embedding_client is not None:
                    try:
                        story_text = " ".join((row["title"], row["summary"] or "", " ".join(json.loads(row["themes_json"]))))
                        vectors = self.embedding_client.embed([story_text, *(record[2] for record in chunk_records)])
                        database.execute("DELETE FROM story_vectors WHERE story_id=?", (story_id,))
                        database.execute("INSERT INTO story_vectors VALUES(?,?,?,?)", (story_id, self.embedding_client.model, len(vectors[0]), vectors[0].astype("<f4").tobytes()))
                        for record, vector in zip(chunk_records, vectors[1:], strict=True):
                            database.execute("INSERT OR REPLACE INTO chunk_vectors VALUES(?,?,?,?)", (record[0], self.embedding_client.model, len(vector), vector.astype("<f4").tobytes()))
                    except Exception:
                        semantic = False
                database.execute("UPDATE stories SET index_status='indexed' WHERE story_id=?", (story_id,))
                indexed += 1
            database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('semantic_search',?)", ("available" if semantic else "unavailable",))
            if semantic and self.embedding_client is not None:
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_model',?)", (self.embedding_client.model,))
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_revision',?)", (getattr(self.embedding_client, "revision", self.embedding_client.model),))
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_normalization','l2')")
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_prefixes','query:/passage:')")
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_tokenizer',?)", (EMBEDDING_TOKENIZER,))
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_context_tokens',?)", (str(EMBEDDING_CONTEXT_TOKENS),))
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('chunk_target_words',?)", (str(CHUNK_TARGET_WORDS),))
                database.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('chunk_overlap_words',?)", (str(CHUNK_OVERLAP_WORDS),))
        return {"indexed_stories": indexed, "fts5": fts, "semantic": "available" if semantic else "unavailable", "search_mode": "hybrid" if semantic else ("fts5" if fts else "like")}

    @staticmethod
    def _chunk_sections(sections, target_words: int = CHUNK_TARGET_WORDS, overlap_words: int = CHUNK_OVERLAP_WORDS):
        chunks = []
        for section in sections:
            # E5 accepts at most 512 tokens. Word windows keep even unusually
            # long source paragraphs below that limit while overlap retains
            # context. Exact reading still uses the untouched section text.
            words = section["text"].split()
            start = 0
            while start < len(words):
                window = words[start : start + target_words]
                if not window:
                    break
                chunks.append((section["section_order"], " ".join(window), section["source_locator"]))
                if start + target_words >= len(words):
                    break
                start += target_words - overlap_words
        return chunks

    def list_stories(self, *, language: str | None = None, approved_only: bool = True, age: int | None = None, limit: int = 100) -> list[dict[str, object]]:
        clauses = []
        values: list[object] = []
        if language:
            if language not in LANGUAGES:
                raise ValueError("Language must be en, pt, or es")
            clauses.append("d.language=?")
            values.append(language)
        if approved_only:
            clauses.extend(("d.rights_status='approved'", "d.review_status='approved'", "s.index_status='indexed'"))
        if age is not None:
            clauses.extend(("d.age_review_status='approved'", "(d.age_min IS NULL OR d.age_min<=?)", "(d.age_max IS NULL OR d.age_max>=?)"))
            values.extend((age, age))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(min(max(limit, 1), 500))
        with self._connect() as database:
            rows = database.execute(
                """SELECT s.story_id,s.title,s.word_count,s.estimated_duration,s.index_status,
                          d.document_id,d.author,d.language,d.locale,d.category,d.source_name,
                          d.source_url,d.license_id,d.rights_status,d.review_status,d.age_min,d.age_max
                   FROM stories s JOIN documents d USING(document_id)""" + where + " ORDER BY d.language,s.title LIMIT ?",
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, *, language: str | None = None, age: int | None = None, limit: int = 10) -> list[StorySearchResult]:
        normalized = query.strip()
        if not normalized or len(normalized) > 300:
            raise ValueError("Search query must contain 1 to 300 characters")
        if language and language not in LANGUAGES:
            raise ValueError("Language must be en, pt, or es")
        with self._connect() as database:
            params: list[object] = [normalized.casefold()]
            filters = ["d.rights_status='approved'", "d.review_status='approved'", "s.index_status='indexed'", "lower(s.title)=?"]
            if language:
                filters.append("d.language=?")
                params.append(language)
            if age is not None:
                filters.extend(("d.age_review_status='approved'", "(d.age_min IS NULL OR d.age_min<=?)", "(d.age_max IS NULL OR d.age_max>=?)"))
                params.extend((age, age))
            exact = database.execute(
                """SELECT s.story_id,s.title,d.author,d.language,d.category,d.source_name,d.source_url
                   FROM stories s JOIN documents d USING(document_id) WHERE """ + " AND ".join(filters) + " LIMIT ?",
                (*params, limit),
            ).fetchall()
            results = [self._search_result(row, "exact_title", 1.0) for row in exact]
            if len(results) >= limit:
                return results
            tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)[:12]
            fts_query = " AND ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
            if not fts_query:
                return results
            extra_filters = ["d.rights_status='approved'", "d.review_status='approved'", "s.index_status='indexed'", "story_fts MATCH ?"]
            extra_params: list[object] = [fts_query]
            if language:
                extra_filters.append("d.language=?")
                extra_params.append(language)
            if age is not None:
                extra_filters.extend(("d.age_review_status='approved'", "(d.age_min IS NULL OR d.age_min<=?)", "(d.age_max IS NULL OR d.age_max>=?)"))
                extra_params.extend((age, age))
            try:
                rows = database.execute(
                    """SELECT s.story_id,s.title,d.author,d.language,d.category,d.source_name,d.source_url,bm25(story_fts) score
                       FROM story_fts JOIN stories s USING(story_id) JOIN documents d USING(document_id)
                       WHERE """ + " AND ".join(extra_filters) + " ORDER BY score LIMIT ?",
                    (*extra_params, limit - len(results)),
                ).fetchall()
                seen = {item.story_id for item in results}
                results.extend(self._search_result(row, "fts5", float(row["score"])) for row in rows if row["story_id"] not in seen)
                if len(results) < limit:
                    chunk_filters = ["chunk_fts MATCH ?", "d.rights_status='approved'", "d.review_status='approved'", "s.index_status='indexed'"]
                    chunk_params: list[object] = [fts_query]
                    if language:
                        chunk_filters.append("d.language=?")
                        chunk_params.append(language)
                    chunk_rows = database.execute(
                        """SELECT DISTINCT s.story_id,s.title,d.author,d.language,d.category,d.source_name,d.source_url,
                                          bm25(chunk_fts) score
                           FROM chunk_fts JOIN stories s USING(story_id) JOIN documents d USING(document_id)
                           WHERE """ + " AND ".join(chunk_filters) + " ORDER BY score LIMIT ?",
                        (*chunk_params, limit - len(results)),
                    ).fetchall()
                    seen = {item.story_id for item in results}
                    results.extend(self._search_result(row, "chunk_fts5", float(row["score"])) for row in chunk_rows if row["story_id"] not in seen)
            except sqlite3.OperationalError:
                like = f"%{normalized}%"
                rows = database.execute(
                    """SELECT s.story_id,s.title,d.author,d.language,d.category,d.source_name,d.source_url
                       FROM stories s JOIN documents d USING(document_id)
                       WHERE d.rights_status='approved' AND d.review_status='approved' AND s.index_status='indexed'
                         AND (s.title LIKE ? OR d.summary LIKE ?) AND (? IS NULL OR d.language=?) LIMIT ?""",
                    (like, like, language, language, limit - len(results)),
                ).fetchall()
                seen = {item.story_id for item in results}
                results.extend(self._search_result(row, "like_fallback", None) for row in rows if row["story_id"] not in seen)
            if self.embedding_client is not None and len(results) < limit:
                try:
                    query_vector = self.embedding_client.embed([normalized], query=True)[0]
                    semantic_rows = database.execute(
                        """SELECT s.story_id,s.title,d.author,d.language,d.category,d.source_name,d.source_url,
                                  v.vector,v.dimension
                           FROM story_vectors v JOIN stories s USING(story_id) JOIN documents d USING(document_id)
                           WHERE d.rights_status='approved' AND d.review_status='approved' AND s.index_status='indexed'
                             AND (? IS NULL OR d.language=?)""",
                        (language, language),
                    ).fetchall()
                    scored = []
                    seen = {item.story_id for item in results}
                    for row in semantic_rows:
                        if row["story_id"] in seen: continue
                        vector = np.frombuffer(row["vector"], dtype="<f4", count=row["dimension"])
                        scored.append((float(np.dot(query_vector, vector)), row))
                    for score, row in sorted(scored, key=lambda item: item[0], reverse=True)[: limit - len(results)]:
                        if score >= 0.72:
                            results.append(self._search_result(row, "semantic_multilingual_e5", score))
                except Exception:
                    pass
            return results

    @staticmethod
    def _search_result(row, method: str, score: float | None) -> StorySearchResult:
        return StorySearchResult(row["story_id"], row["title"], row["author"], row["language"], row["category"], row["source_name"], row["source_url"], method, score)

    def get_story(self, story_id: str, *, age: int | None = None, include_text: bool = True) -> dict[str, object]:
        if not re.fullmatch(r"story_[0-9a-f]{24}", story_id):
            raise StoryNotAvailableError(story_id)
        filters = ["s.story_id=?", "d.rights_status='approved'", "d.review_status='approved'", "s.index_status='indexed'"]
        values: list[object] = [story_id]
        if age is not None:
            filters.extend(("d.age_review_status='approved'", "(d.age_min IS NULL OR d.age_min<=?)", "(d.age_max IS NULL OR d.age_max>=?)"))
            values.extend((age, age))
        with self._connect() as database:
            story = database.execute(
                """SELECT s.*,d.title document_title,d.author,d.language,d.locale,d.category,d.source_name,
                          d.source_url,d.license_id,d.license_url,d.attribution,d.content_warnings_json
                   FROM stories s JOIN documents d USING(document_id) WHERE """ + " AND ".join(filters),
                values,
            ).fetchone()
            if story is None:
                raise StoryNotAvailableError(story_id)
            payload = dict(story)
            payload["content_warnings"] = json.loads(payload.pop("content_warnings_json"))
            if include_text:
                payload["sections"] = [dict(row) for row in database.execute("SELECT section_order,title,text,source_locator FROM sections WHERE story_id=? ORDER BY section_order", (story_id,))]
        return payload

    def chunks_for_question(self, story_id: str, query: str, *, through_section: int | None = None, limit: int = 4) -> list[dict[str, object]]:
        self.get_story(story_id, include_text=False)
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)[:12]
        match = " OR ".join(f'"{token}"' for token in tokens)
        with self._connect() as database:
            try:
                section_filter = " AND c.section_order<=?" if through_section is not None else ""
                parameters: tuple[object, ...] = (match, story_id)
                if through_section is not None:
                    parameters += (through_section,)
                parameters += (limit,)
                rows = database.execute(
                    """SELECT c.chunk_order,c.section_order,c.text,c.source_locator,bm25(chunk_fts) score
                       FROM chunk_fts JOIN chunks c USING(chunk_id)
                       WHERE chunk_fts MATCH ? AND c.story_id=?""" + section_filter + " ORDER BY score LIMIT ?",
                    parameters,
                ).fetchall()
            except sqlite3.OperationalError:
                fallback_filter = " AND section_order<=?" if through_section is not None else ""
                fallback_parameters: tuple[object, ...] = (story_id,)
                if through_section is not None:
                    fallback_parameters += (through_section,)
                fallback_parameters += (limit,)
                rows = database.execute(
                    "SELECT chunk_order,section_order,text,source_locator,NULL score FROM chunks WHERE story_id=?"
                    + fallback_filter + " ORDER BY chunk_order LIMIT ?",
                    fallback_parameters,
                ).fetchall()
        return [dict(row) for row in rows]

    def report(self) -> dict[str, object]:
        self.initialize()
        with self._connect() as database:
            coverage = [dict(row) for row in database.execute(
                """SELECT language,COUNT(*) discovered,
                   COUNT(*) downloaded,
                   SUM(extraction_status='extracted') extracted,
                   SUM(review_status IN ('approved','rejected')) reviewed,
                   SUM(review_status='approved' AND rights_status='approved') approved,
                   (SELECT COUNT(*) FROM stories s JOIN documents dx ON dx.document_id=s.document_id
                    WHERE dx.language=d.language AND s.index_status='indexed') indexed_stories
                   FROM documents d GROUP BY language ORDER BY language"""
            )]
            sources = [dict(row) for row in database.execute(
                """SELECT source_name,language,COUNT(*) discovered,COUNT(*) downloaded,
                          SUM(extraction_status='extracted') extracted,
                          SUM(review_status IN ('approved','rejected')) reviewed,
                          SUM(review_status='approved' AND rights_status='approved') approved
                   FROM documents GROUP BY source_name,language ORDER BY source_name,language"""
            )]
            indexed = database.execute("SELECT COUNT(*) FROM stories WHERE index_status='indexed'").fetchone()[0]
            pending = [dict(row) for row in database.execute(
                "SELECT document_id,title,language,source_name,source_url,extraction_status,rights_status,review_status FROM documents WHERE extraction_status!='extracted' OR rights_status!='approved' OR review_status!='approved' ORDER BY imported_at"
            )]
            fts = database.execute("SELECT value FROM metadata WHERE key='fts5'").fetchone()[0]
            semantic_row = database.execute("SELECT value FROM metadata WHERE key='semantic_search'").fetchone()
            model_row = database.execute("SELECT value FROM metadata WHERE key='embedding_model'").fetchone()
            semantic_metadata = dict(database.execute("SELECT key,value FROM metadata WHERE key LIKE 'embedding_%' OR key LIKE 'chunk_%'").fetchall())
        semantic_status = semantic_row[0] if semantic_row else "unavailable"
        if semantic_status == "available" and self.embedding_client is not None and not self.embedding_client.ready():
            semantic_status = "runtime_unavailable_fts5_fallback"
        return {"generated_at": _utc_now(), "coverage": coverage, "sources": sources, "indexed_stories": indexed, "fts5": fts, "semantic_search": semantic_status, "embedding_model": model_row[0] if model_row else None, "semantic_index_metadata": semantic_metadata, "pending": pending}

    def write_report(self, name: str, payload: object) -> Path:
        path = self.paths.reports / name
        _atomic_json(path, payload)
        return path

    def load_progress(self, session_id: str) -> dict[str, object] | None:
        with self._connect() as database:
            row = database.execute(
                "SELECT story_id,next_section,language FROM story_progress WHERE session_id=?",
                (session_id[:128],),
            ).fetchone()
        return dict(row) if row else None

    def save_progress(self, session_id: str, story_id: str, next_section: int, language: str) -> None:
        with self._connect() as database:
            database.execute(
                """INSERT INTO story_progress(session_id,story_id,next_section,language,updated_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET
                   story_id=excluded.story_id,next_section=excluded.next_section,
                   language=excluded.language,updated_at=excluded.updated_at""",
                (session_id[:128], story_id, next_section, language, _utc_now()),
            )
