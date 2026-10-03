"""Measure streaming latency and generation speed from the local llama.cpp server."""

from __future__ import annotations

import argparse
import json
from time import perf_counter

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Em duas frases curtas, explique o que é um Raspberry Pi.",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8081/v1")
    parser.add_argument("--model", default="qwen3.5-2b-q4_k_m")
    args = parser.parse_args()
    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "system",
                "content": "Responda em português brasileiro, de forma concisa e sem Markdown.",
            },
            {"role": "user", "content": args.prompt},
        ],
        "max_tokens": 180,
        "stream": True,
        "stream_options": {"include_usage": True},
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
    }
    started = perf_counter()
    first_text: float | None = None
    output: list[str] = []
    usage: dict[str, object] = {}
    timings: dict[str, object] = {}
    with httpx.Client(timeout=90, trust_env=False) as client:
        with client.stream("POST", f"{args.url.rstrip('/')}/chat/completions", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                content = (choices[0].get("delta") or {}).get("content") if choices else None
                if content:
                    first_text = first_text or perf_counter() - started
                    output.append(content)
                usage = chunk.get("usage") or usage
                timings = chunk.get("timings") or timings
    total = perf_counter() - started
    print("".join(output).strip())
    print(
        json.dumps(
            {
                "model": args.model,
                "first_text_seconds": round(first_text or total, 3),
                "total_seconds": round(total, 3),
                "tokens_per_second": timings.get("predicted_per_second"),
                "usage": usage,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
