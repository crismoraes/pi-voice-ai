"""Offline text extraction with bounded archive and document handling."""

from __future__ import annotations

import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from pypdf import PdfReader

from app.stories.types import ExtractedSection, ExtractionResult

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".epub", ".pdf", ".h5p"}


class _TextHtmlParser(HTMLParser):
    block_tags = {"p", "div", "section", "article", "h1", "h2", "h3", "li", "br", "blockquote"}
    ignored_tags = {"script", "style", "nav", "svg", "canvas", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags:
            self._ignored += 1
        elif not self._ignored and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags and self._ignored:
            self._ignored -= 1
        elif not self._ignored and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self.parts.append(data)

    def text(self) -> str:
        return _normalize_text("".join(self.parts))


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _decode_text(data: bytes) -> tuple[str, tuple[str, ...]]:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding), ()
        except UnicodeDecodeError:
            pass
    return data.decode("cp1252"), ("decoded_as_cp1252_needs_review",)


def _safe_zip_members(archive: zipfile.ZipFile, *, max_entries: int, max_uncompressed: int):
    members = archive.infolist()
    if len(members) > max_entries:
        raise ValueError("Archive contains too many files")
    if sum(item.file_size for item in members) > max_uncompressed:
        raise ValueError("Archive expands beyond the configured limit")
    for item in members:
        member = PurePosixPath(item.filename)
        if member.is_absolute() or ".." in member.parts:
            raise ValueError("Archive member escapes its root")
        if item.is_dir():
            continue
        if (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Archive contains a symbolic link")
        yield item


def _html_text(data: bytes) -> str:
    decoded, _ = _decode_text(data)
    parser = _TextHtmlParser()
    parser.feed(decoded)
    return parser.text()


def _extract_epub(path: Path, max_bytes: int) -> ExtractionResult:
    with zipfile.ZipFile(path) as archive:
        members = {item.filename: item for item in _safe_zip_members(archive, max_entries=2000, max_uncompressed=max_bytes)}
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(node.attrib["full-path"] for node in container.iter() if node.tag.endswith("rootfile"))
        opf = ElementTree.fromstring(archive.read(rootfile))
        base = PurePosixPath(rootfile).parent
        manifest = {
            node.attrib["id"]: node.attrib["href"]
            for node in opf.iter()
            if node.tag.endswith("item") and "id" in node.attrib and "href" in node.attrib
        }
        spine = [node.attrib["idref"] for node in opf.iter() if node.tag.endswith("itemref") and "idref" in node.attrib]
        sections = []
        for order, item_id in enumerate(spine, 1):
            member_name = str(base / PurePosixPath(manifest[item_id]))
            if member_name not in members:
                continue
            text = _html_text(archive.read(member_name))
            if text:
                sections.append(ExtractedSection(order, None, text, member_name))
    return ExtractionResult(tuple(sections), "extracted" if sections else "failed")


def _extract_h5p(path: Path, max_bytes: int) -> ExtractionResult:
    with zipfile.ZipFile(path) as archive:
        members = {item.filename: item for item in _safe_zip_members(archive, max_entries=2000, max_uncompressed=max_bytes)}
        content_name = "content/content.json"
        if content_name not in members:
            raise ValueError("H5P has no content/content.json")
        payload = json.loads(archive.read(content_name))
    values: list[str] = []
    allowed_keys = {"text", "title", "description", "content"}

    def visit(value, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key)
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str) and key in allowed_keys and len(value) < 100_000:
            text = _html_text(value.encode("utf-8"))
            if text and text not in values:
                values.append(text)

    visit(payload)
    sections = tuple(ExtractedSection(i, None, text, f"{content_name}#{i}") for i, text in enumerate(values, 1))
    return ExtractionResult(sections, "extracted" if sections else "failed")


def extract_document(path: Path, *, max_uncompressed_bytes: int = 100_000_000) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported story format: {suffix}")
    if suffix in {".txt", ".md", ".markdown"}:
        decoded, warnings = _decode_text(path.read_bytes())
        text = _normalize_text(decoded)
        return ExtractionResult((ExtractedSection(1, None, text, "document"),), "extracted", warnings)
    if suffix in {".html", ".htm"}:
        text = _html_text(path.read_bytes())
        return ExtractionResult((ExtractedSection(1, None, text, "document"),), "extracted" if text else "failed")
    if suffix == ".epub":
        return _extract_epub(path, max_uncompressed_bytes)
    if suffix == ".h5p":
        return _extract_h5p(path, max_uncompressed_bytes)
    reader = PdfReader(str(path), strict=False)
    sections = []
    empty_pages = 0
    for index, page in enumerate(reader.pages, 1):
        text = _normalize_text(page.extract_text() or "")
        if text:
            sections.append(ExtractedSection(index, None, text, f"page:{index}"))
        else:
            empty_pages += 1
    if not sections:
        return ExtractionResult((), "needs_ocr", (f"empty_pages:{empty_pages}",))
    warnings = (f"empty_pages:{empty_pages}",) if empty_pages else ()
    return ExtractionResult(tuple(sections), "extracted", warnings)
