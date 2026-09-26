"""Exercise the streaming assistant endpoint on a live deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
from pathlib import Path

from httpx import AsyncClient


async def check_llm(base_url: str, ca_file: Path, text: str) -> dict[str, object]:
    ssl_context = ssl.create_default_context(cafile=str(ca_file))
    event_name = "message"
    deltas: list[str] = []
    metrics: dict[str, object] | None = None

    async with AsyncClient(
        base_url=base_url,
        verify=ssl_context,
        timeout=60,
        trust_env=False,
    ) as client:
        async with client.stream(
            "POST",
            "/api/assistant/responses",
            json={"text": text},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    if event_name == "delta":
                        deltas.append(payload["text"])
                    elif event_name == "done":
                        metrics = payload
                    elif event_name == "error":
                        raise RuntimeError(payload["message"])
                elif not line:
                    event_name = "message"

    result_text = "".join(deltas)
    if not result_text:
        raise RuntimeError("The deployment streamed no assistant text")
    if metrics is None:
        raise RuntimeError("The deployment did not send completion metrics")
    return {"text": result_text, **metrics}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument(
        "--text",
        default="Responda em uma frase: o teste de streaming funcionou?",
    )
    args = parser.parse_args()
    result = asyncio.run(
        check_llm(args.url.rstrip("/"), args.ca_file, args.text)
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
