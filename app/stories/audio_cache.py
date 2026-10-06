"""Bounded private cache for synthesized story segments."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

from app.tts.base import SynthesisResult


class StoryAudioCache:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root, self.max_bytes = root, max_bytes
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, text: str, voice: str) -> Path:
        key = hashlib.sha256(f"v1\x1f{voice}\x1f{text}".encode()).hexdigest()
        return self.root / f"{key}.npz"

    def get(self, text: str, voice: str) -> SynthesisResult | None:
        path = self._path(text, voice)
        try:
            with np.load(path, allow_pickle=False) as value:
                samples = np.asarray(value["samples"], dtype=np.float32)
                sample_rate = int(value["sample_rate"])
            path.touch()
            return SynthesisResult(samples=samples, sample_rate=sample_rate, processing_seconds=0.0)
        except (OSError, KeyError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def put(self, text: str, voice: str, result: SynthesisResult) -> None:
        path = self._path(text, voice)
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, samples=result.samples, sample_rate=result.sample_rate)
        if os.name == "posix": temporary.chmod(0o600)
        temporary.replace(path)
        self._prune()

    def clear(self) -> None:
        for path in self.root.glob("*.npz"):
            path.unlink(missing_ok=True)

    def _prune(self) -> None:
        files = sorted(self.root.glob("*.npz"), key=lambda path: path.stat().st_mtime)
        total = sum(path.stat().st_size for path in files)
        while files and total > self.max_bytes:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)
