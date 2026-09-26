"""Text segmentation for incremental local speech synthesis."""

import re


def split_text_for_speech(text: str, max_characters: int) -> list[str]:
    """Split text at sentence or word boundaries for low-latency synthesis."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        for word in sentence.split():
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_characters:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current and sentence.rstrip().endswith((".", "!", "?")):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks or [text]
