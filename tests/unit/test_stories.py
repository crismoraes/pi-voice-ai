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
from app.stories.audio_cache import StoryAudioCache
from app.tts.base import SynthesisResult
import numpy as np


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


def test_text_pdf_and_valid_epub_keep_source_structure(tmp_path: Path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter(); page = writer.add_blank_page(300, 300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject(); stream.set_data(b"BT /F1 12 Tf 40 250 Td (Canonical PDF story) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    pdf = tmp_path / "text.pdf"
    with pdf.open("wb") as target: writer.write(target)
    pdf_result = extract_document(pdf)
    assert pdf_result.status == "extracted" and "Canonical PDF story" in pdf_result.text

    epub = tmp_path / "story.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OPS/content.opf"/></rootfiles></container>')
        archive.writestr("OPS/content.opf", '<package><manifest><item id="one" href="one.xhtml"/></manifest><spine><itemref idref="one"/></spine></package>')
        archive.writestr("OPS/one.xhtml", '<html><body><h1>Story One</h1><p>First paragraph.</p></body></html>')
    epub_result = extract_document(epub)
    assert epub_result.status == "extracted" and epub_result.sections[0].source_locator == "OPS/one.xhtml"


def test_exact_read_does_not_need_an_llm(tmp_path: Path):
    library = StoryLibrary(tmp_path / "library")
    story = tmp_path / "story.txt"; story.write_text("Exact canonical text.", encoding="utf-8")
    library.ingest_file(story, metadata(title="Lantern Story")); library.build_index()
    turn = StoryEngine(library).handle("child", "read the Lantern Story")
    assert turn is not None and turn.mode == "READ_EXACT"
    assert turn.llm_prompt is None and turn.text_segments == ("Exact canonical text.",)
    engine = StoryEngine(library)
    assert engine.handle("pt", "Quais histórias de Natal você tem?").llm_prompt is None
    first = engine.handle("pt", "read the Lantern Story")
    assert first and first.story_id
    again = engine.handle("pt", "Read that story from the beginning")
    assert again and again.story_id == first.story_id and again.llm_prompt is None


def test_acquisition_rejects_html_disguised_as_epub(tmp_path: Path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>Error</html>", request=request))
    item = {"id": "book", "extension": ".epub", "download_url": "https://books.example/book.epub",
            "canonical_url": "https://books.example/book", "allowed_hosts": ["books.example"],
            "metadata": {"source_name": "test", "language": "en"}}
    paths = StoryPaths(tmp_path / "library"); paths.create()
    with httpx.Client(transport=transport) as client, pytest.raises(ValueError, match="expected ZIP"):
        _acquire_item(client, paths, item, 1000)


def test_collection_with_roman_headings_splits_without_mixing_stories(tmp_path: Path):
    library = StoryLibrary(tmp_path / "library")
    source = tmp_path / "collection.txt"
    source.write_text("I\n\nFIRST TALE\n\nFirst body.\n\nII\n\nSECOND TALE[A]\n\nSecond body.\n\nIII\n\nTHIRD TALE\n\nThird body.", encoding="utf-8")
    result = library.ingest_file(source, metadata(title="Collection", collection=True))
    library.build_index()
    assert result["stories"] == 3
    stories = library.list_stories()
    assert [item["title"] for item in stories] == ["FIRST TALE", "SECOND TALE", "THIRD TALE"]
    assert library.get_story(stories[1]["story_id"])["sections"][0]["text"] == "Second body."


def test_story_audio_cache_is_voice_specific_and_invalidated_by_review(tmp_path: Path):
    library = StoryLibrary(tmp_path / "library"); library.initialize()
    cache = StoryAudioCache(library.paths.cache_audio, 1_000_000)
    audio = SynthesisResult(np.array([0.1, -0.1], dtype=np.float32), 22050, 0.2)
    cache.put("hello", "english", audio)
    assert cache.get("hello", "english") is not None
    assert cache.get("hello", "spanish") is None
    source = tmp_path / "story.txt"; source.write_text("hello", encoding="utf-8")
    document = library.ingest_file(source, metadata())
    library.review(document["document_id"], "approved")
    assert cache.get("hello", "english") is None


def test_semantic_index_uses_same_local_vector_space_for_query_and_story(tmp_path: Path):
    class FakeEmbeddings:
        model = "fake-multilingual"
        def ready(self): return True
        def embed(self, texts, *, query=False):
            return [np.array([1.0, 0.0], dtype=np.float32) if any(word in text.casefold() for word in ("lantern", "farol")) else np.array([0.0, 1.0], dtype=np.float32) for text in texts]
    library = StoryLibrary(tmp_path / "library", FakeEmbeddings())
    source = tmp_path / "story.txt"; source.write_text("A gentle light guides everyone home.", encoding="utf-8")
    library.ingest_file(source, metadata(title="Lantern Story")); result = library.build_index()
    assert result["semantic"] == "available"
    found = library.search("farol", language="en")
    assert found and found[0].method == "semantic_multilingual_e5"


def test_index_chunks_long_paragraphs_within_embedding_limit(tmp_path: Path):
    section = {
        "section_order": 1,
        "text": " ".join(f"word{number}" for number in range(527)),
        "source_locator": "paragraph:1",
    }

    chunks = StoryLibrary._chunk_sections([section])

    assert len(chunks) == 4
    assert all(len(text.split()) <= 180 for _, text, _ in chunks)
    assert chunks[0][1].split()[-30:] == chunks[1][1].split()[:30]
