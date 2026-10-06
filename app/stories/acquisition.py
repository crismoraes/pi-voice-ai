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


def _acquire_item(client: httpx.Client, paths: StoryPaths, item: dict, max_bytes: int) -> dict[str, object]:
    extension = str(item.get("extension", ".txt"))
    if extension not in {".txt", ".md", ".html", ".htm", ".epub", ".pdf", ".h5p"}:
        raise ValueError("unsupported acquired file extension")
    output = paths.inbox / f"{item['id']}{extension}"
    sidecar_path = output.with_suffix(output.suffix + ".json")
    if output.is_file() and sidecar_path.is_file():
        return {"id": item["id"], "source": item["metadata"]["source_name"], "language": item["metadata"]["language"],
                "status": "already_downloaded", "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "canonical_url": item["canonical_url"]}

    url = str(item["download_url"])
    allowed_hosts = {str(host).lower() for host in item.get("allowed_hosts", [])}
    host = (urlparse(url).hostname or "").lower()
    if host not in allowed_hosts:
        raise ValueError(f"host is not allowlisted: {host}")
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
        raise ValueError(f"redirected to non-allowlisted host: {final_host}")
    content = response.content
    if not content or len(content) > max_bytes:
        raise ValueError("download has an invalid size")
    if extension in {".epub", ".h5p"} and not content.startswith(b"PK"):
        raise ValueError(f"expected ZIP document; received {response.headers.get('content-type', 'unknown')}")
    if extension == ".pdf" and not content.startswith(b"%PDF"):
        raise ValueError("expected PDF document")
    if extension in {".txt", ".md", ".html", ".htm"} and b"\x00" in content[:4096]:
        raise ValueError("download does not look like text")
    sha256 = hashlib.sha256(content).hexdigest()
    expected = item.get("sha256")
    if expected and expected != sha256:
        raise ValueError("checksum mismatch")
    _atomic_write(output, content)
    metadata = dict(item["metadata"])
    metadata.update({"source_url": item["canonical_url"], "source_item_id": item["id"]})
    _atomic_write(sidecar_path, json.dumps(metadata, ensure_ascii=False, indent=2).encode())
    time.sleep(min(float(item.get("delay_seconds", 2)), 10))
    return {"id": item["id"], "source": metadata["source_name"], "language": metadata["language"],
            "status": "downloaded", "bytes": len(content), "sha256": sha256, "canonical_url": item["canonical_url"]}


def acquire_manifest(root: Path, manifest_path: Path, *, max_items: int = 20,
                     max_bytes: int = 50_000_000, timeout_seconds: float = 30) -> list[dict[str, object]]:
    """Download enabled items; isolate failures and retain manual-download evidence."""
    paths = StoryPaths(root)
    paths.create()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    _atomic_write(paths.manifests / manifest_path.name, manifest_bytes)
    results: list[dict[str, object]] = []
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        for item in manifest.get("items", [])[:max_items]:
            if not item.get("enabled", False):
                continue
            try:
                results.append(_acquire_item(client, paths, item, max_bytes))
            except Exception as exc:
                results.append({"id": item.get("id"), "source": item.get("metadata", {}).get("source_name"),
                                "language": item.get("metadata", {}).get("language"), "status": "failed",
                                "reason": str(exc), "canonical_url": item.get("canonical_url"),
                                "manual_download_required": True})
    summary: dict[str, int] = {}
    for result in results:
        summary[str(result["status"])] = summary.get(str(result["status"]), 0) + 1
    _atomic_write(paths.reports / "acquisition-latest.json",
                  json.dumps({"summary": summary, "items": results}, ensure_ascii=False, indent=2).encode())
    return results
