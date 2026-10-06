"""Local OpenAI-compatible embeddings client for the story index."""

from __future__ import annotations

import httpx
import numpy as np


class LocalEmbeddingClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str], *, query: bool = False) -> list[np.ndarray]:
        prefix = "query: " if query else "passage: "
        response = httpx.post(
            f"{self.base_url}/v1/embeddings",
            json={"model": self.model, "input": [prefix + text for text in texts]},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = []
        for row in rows:
            vector = np.asarray(row["embedding"], dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            vectors.append(vector / norm if norm else vector)
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding server returned an unexpected result count")
        return vectors

    def ready(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/health", timeout=2).status_code == 200
        except httpx.HTTPError:
            return False
