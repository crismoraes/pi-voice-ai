import json
import zipfile
from pathlib import Path

import pytest
import httpx

from app.stories.engine import StoryEngine
from app.stories.extract import extract_document
from app.stories.library import StoryLibrary, StoryNotAvailableError
from app.stories.types import SourceMetadata
from app.stories.acquisition import _acquire_item
from app.stories.paths import StoryPaths


def metadata(**changes):
    values = dict(title="A Safe Story", language="en", source_name="test", rights_status="approved", review_status="approved", age_review_status="approved")
    values.update(changes)
    return SourceMetadata(**values)


def test_ingest_is_idempotent_and_search_never_exposes_pending(tmp_path: Path):
    library = StoryLibrary(tmp_path / "library")
    approved = tmp_path / "approved.txt"; approved.write_text("A lantern helps travelers return home.", encoding="utf-8")
    pending = tmp_path / "pending.txt"; pending.write_text("Secret dragon text.", encoding="utf-8")
    first = library.ingest_file(approved, metadata())
    assert library.ingest_file(approved, metadata())["status"] == "duplicate"
    pending_result = library.ingest_file(pending, metadata(title="Pending Dragon", rights_status="pending", review_status="needs_review"))
    library.build_index()
    assert library.search("travelers")[0].story_id.startswith("story_")
    assert library.search("dragon") == []
    pending_story = next(item for item in library.list_stories(approved_only=False) if item["title"] == "Pending Dragon")
    with pytest.raises(StoryNotAvailableError):
        library.get_story(pending_story["story_id"])
    assert first["status"] == "imported" and pending_result["status"] == "imported"


def test_malicious_epub_path_is_ignored_and_pdf_without_text_needs_ocr(tmp_path: Path):
    epub = tmp_path / "bad.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("../escape.txt", "bad")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>')
        archive.writestr("content.opf", '<package><manifest></manifest><spine></spine></package>')
    with pytest.raises(ValueError, match="escapes"):
        extract_document(epub)
    from pypdf import PdfWriter
    pdf = tmp_path / "scan.pdf"; writer = PdfWriter(); writer.add_blank_page(100, 100)
    with pdf.open("wb") as stream: writer.write(stream)
    assert extract_document(pdf).status == "needs_ocr"


def test_exact_read_does_not_need_an_llm(tmp_path: Path):
    library = StoryLibrary(tmp_path / "library")
    story = tmp_path / "story.txt"; story.write_text("Exact canonical text.", encoding="utf-8")
    library.ingest_file(story, metadata(title="Lantern Story")); library.build_index()
    turn = StoryEngine(library).handle("child", "read the Lantern Story")
    assert turn is not None and turn.mode == "READ_EXACT"
    assert turn.llm_prompt is None and turn.text_segments == ("Exact canonical text.",)


def test_acquisition_rejects_html_disguised_as_epub(tmp_path: Path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>Error</html>", request=request))
    item = {"id": "book", "extension": ".epub", "download_url": "https://books.example/book.epub",
            "canonical_url": "https://books.example/book", "allowed_hosts": ["books.example"],
            "metadata": {"source_name": "test", "language": "en"}}
    paths = StoryPaths(tmp_path / "library"); paths.create()
    with httpx.Client(transport=transport) as client, pytest.raises(ValueError, match="expected ZIP"):
        _acquire_item(client, paths, item, 1000)
