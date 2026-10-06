"""Administrative CLI for the private story library."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

from app.config import get_settings
from app.stories.acquisition import acquire_manifest
from app.stories.library import StoryLibrary
from app.stories.embeddings import LocalEmbeddingClient


def _library(root: str | None) -> StoryLibrary:
    settings = get_settings()
    configured = settings.story_library_root
    embeddings = LocalEmbeddingClient(settings.story_embedding_base_url, settings.story_embedding_model, settings.story_embedding_timeout_seconds)
    return StoryLibrary(Path(root).resolve() if root else Path(configured), embeddings)


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _seed_samples(library: StoryLibrary) -> None:
    source = Path(__file__).resolve().parents[2] / "config" / "story_samples"
    library.paths.create()
    for path in source.rglob("*"):
        if path.is_file():
            shutil.copy2(path, library.paths.inbox / path.name)


def _export(library: StoryLibrary, output: Path) -> dict[str, object]:
    stories = library.list_stories(limit=500)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"format": 1, "stories": stories}, ensure_ascii=False, indent=2))
        for item in stories:
            payload = library.get_story(str(item["story_id"]))
            archive.writestr(f"stories/{item['story_id']}.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return {"exported": len(stories), "path": str(output)}


def _import_package(library: StoryLibrary, package: Path) -> dict[str, object]:
    if package.stat().st_size > 100_000_000:
        raise ValueError("Story package exceeds 100 MB")
    imported = 0
    with zipfile.ZipFile(package) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(item.file_size for item in members) > 200_000_000:
            raise ValueError("Story package expands beyond its safety limit")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != 1:
            raise ValueError("Unsupported story package format")
        for item in manifest.get("stories", []):
            story_id = str(item["story_id"])
            if not story_id.startswith("story_"):
                raise ValueError("Invalid story identifier in package")
            payload = json.loads(archive.read(f"stories/{story_id}.json"))
            text = "\n\n".join(section["text"] for section in payload.get("sections", []))
            destination = library.paths.inbox / f"import-{story_id}.txt"
            destination.write_text(text, encoding="utf-8")
            sidecar = {
                "title": payload["title"], "language": payload["language"],
                "author": payload.get("author"), "source_name": "PiVoice story package",
                "source_url": payload.get("source_url"), "license_id": payload.get("license_id"),
                "license_url": payload.get("license_url"), "attribution": payload.get("attribution"),
                "rights_status": "pending", "review_status": "needs_review", "age_review_status": "pending"
            }
            destination.with_suffix(".txt.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
            imported += 1
    return {"prepared_for_review": imported, "ingest": library.ingest_inbox()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stories")
    parser.add_argument("--root")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").add_argument("--offline", action="store_true")
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--offline", action="store_true")
    bootstrap.add_argument("--languages", nargs="+", choices=["en", "pt", "es"], default=["en", "pt", "es"])
    bootstrap.add_argument("--max-per-language", type=int, default=50)
    bootstrap.add_argument("--manifest", type=Path, default=Path("config/story_sources.json"))
    ingest = sub.add_parser("ingest"); ingest.add_argument("path", nargs="?", type=Path); ingest.add_argument("--input", dest="input_path", type=Path)
    review = sub.add_parser("review"); review.add_argument("document_id", nargs="?"); review.add_argument("--decision", choices=["approved", "rejected", "needs_review"]); review.add_argument("--rights", choices=["approved", "blocked", "pending"]); review.add_argument("--list", action="store_true")
    index = sub.add_parser("index"); index.add_argument("--full", action="store_true"); index.add_argument("--incremental", action="store_true")
    listing = sub.add_parser("list"); listing.add_argument("--language", choices=["en", "pt", "es"]); listing.add_argument("--all", action="store_true"); listing.add_argument("--approved-only", action="store_true")
    search = sub.add_parser("search"); search.add_argument("query", nargs="?"); search.add_argument("--query", dest="query_option"); search.add_argument("--language", choices=["en", "pt", "es"]); search.add_argument("--age", type=int)
    play = sub.add_parser("play"); play.add_argument("--id", required=True); play.add_argument("--section", type=int, default=1); play.add_argument("--mode", choices=["read_exact"], default="read_exact")
    sub.add_parser("report")
    export = sub.add_parser("export"); export.add_argument("output", type=Path)
    package_import = sub.add_parser("import-package"); package_import.add_argument("package", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    library = _library(args.root)
    library.initialize()
    if args.command == "doctor":
        with sqlite3.connect(library.paths.database) as db:
            fts = db.execute("SELECT value FROM metadata WHERE key='fts5'").fetchone()[0]
        _print({"ok": True, "offline": args.offline, "root": str(library.paths.root), "sqlite_fts5": fts, "network_attempted": False})
    elif args.command == "bootstrap":
        downloads = [] if args.offline else acquire_manifest(library.paths.root, args.manifest, max_items=max(1, args.max_per_language * len(args.languages)))
        _seed_samples(library)
        ingested = library.ingest_inbox()
        _print({"downloads": downloads, "ingested": ingested, "index": library.build_index()})
    elif args.command == "ingest": _print(library.ingest_inbox(args.input_path or args.path))
    elif args.command == "review":
        if args.list or args.document_id == "list" or not args.document_id:
            _print(library.report()["pending"])
        else:
            if args.decision: library.review(args.document_id, args.decision)
            if args.rights: library.set_rights(args.document_id, args.rights)
            _print({"document_id": args.document_id, "updated": True})
    elif args.command == "index": _print(library.build_index(incremental=not args.full))
    elif args.command == "list": _print(library.list_stories(language=args.language, approved_only=not args.all))
    elif args.command == "search":
        query = args.query_option or args.query
        if not query: raise SystemExit("A search query is required")
        _print([asdict(item) for item in library.search(query, language=args.language, age=args.age)])
    elif args.command == "play":
        story = library.get_story(args.id)
        sections = story["sections"]
        selected = next((item for item in sections if item["section_order"] == args.section), None)
        if selected is None: raise SystemExit("Section is unavailable")
        _print({"story_id": args.id, "title": story["title"], "section": selected})
    elif args.command == "report": _print(library.report())
    elif args.command == "export": _print(_export(library, args.output))
    elif args.command == "import-package": _print(_import_package(library, args.package))
    return 0


if __name__ == "__main__":
    sys.exit(main())
