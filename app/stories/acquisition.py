"""Bounded, auditable acquisition from an explicit source manifest."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.stories.paths import StoryPaths


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def acquire_manifest(
    root: Path,
    manifest_path: Path,
    *,
    max_items: int = 20,
    max_bytes: int = 50_000_000,
    timeout_seconds: float = 30,
) -> list[dict[str, object]]:
    """Download only explicitly enabled items and retain evidence for review."""
    paths = StoryPaths(root)
    paths.create()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _atomic_write(paths.manifests / manifest_path.name, manifest_path.read_bytes())
    results: list[dict[str, object]] = []
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for item in manifest.get("items", [])[:max_items]:
            if not item.get("enabled", False):
                continue
            extension = str(item.get("extension", ".txt"))
            if extension not in {".txt", ".md", ".html", ".htm", ".epub", ".pdf", ".h5p"}:
                raise ValueError("Unsupported acquired file extension")
            output = paths.inbox / f"{item['id']}{extension}"
            sidecar_path = output.with_suffix(output.suffix + ".json")
            if output.is_file() and sidecar_path.is_file():
                results.append({"id": item["id"], "status": "already_downloaded", "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
                continue
            url = str(item["download_url"])
            allowed_hosts = set(item.get("allowed_hosts", []))
            host = (urlparse(url).hostname or "").lower()
            if host not in allowed_hosts:
                results.append({"id": item.get("id"), "status": "blocked_host", "host": host})
                continue
            response = None
            for attempt in range(3):
                response = client.get(url, headers={"User-Agent": "PiVoiceAI-story-library/1.4 (+local educational archive)"})
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                retry_after = min(float(response.headers.get("Retry-After", "2")), 10)
                time.sleep(retry_after * (attempt + 1))
            assert response is not None
            response.raise_for_status()
            final_host = (response.url.host or "").lower()
            if final_host not in allowed_hosts:
                raise ValueError(f"Redirected to non-allowlisted host: {final_host}")
            content = response.content
            if not content or len(content) > max_bytes:
                raise ValueError(f"Download {item.get('id')} has an invalid size")
            if extension in {".epub", ".h5p"} and not content.startswith(b"PK"):
                raise ValueError(f"Download {item['id']} is not a ZIP-based document")
            if extension == ".pdf" and not content.startswith(b"%PDF"):
                raise ValueError(f"Download {item['id']} is not a PDF")
            if extension in {".txt", ".md", ".html", ".htm"} and b"\x00" in content[:4096]:
                raise ValueError(f"Download {item['id']} does not look like text")
            _atomic_write(output, content)
            sha256 = hashlib.sha256(content).hexdigest()
            expected = item.get("sha256")
            if expected and expected != sha256:
                output.unlink(missing_ok=True)
                raise ValueError(f"Checksum mismatch for {item['id']}")
            metadata = dict(item["metadata"])
            metadata.update({"source_url": item["canonical_url"], "source_item_id": item["id"]})
            _atomic_write(sidecar_path, json.dumps(metadata, ensure_ascii=False, indent=2).encode())
            results.append({"id": item["id"], "status": "downloaded", "bytes": len(content), "sha256": sha256})
            time.sleep(min(float(item.get("delay_seconds", 2)), 10))
    report = paths.reports / "acquisition-latest.json"
    _atomic_write(report, json.dumps({"items": results}, indent=2).encode())
    return results
