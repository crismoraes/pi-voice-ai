#!/usr/bin/env bash
set -Eeuo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model="$project_dir/models/multilingual-e5-small-Q4_k_m.gguf"
expected="6661b6e1ccb06e3044e2cd7aa25ca0b837ef7224a2cb5aff3a9e6807c60d01f1"
if [[ -f "$model" ]] && printf '%s  %s\n' "$expected" "$model" | sha256sum --check --status; then
    printf 'Story embedding model already installed: %s\n' "$model"
    exit 0
fi
temporary="$(mktemp --suffix=.gguf)"
trap 'rm -f "$temporary"' EXIT
curl --fail --location --retry 3 --output "$temporary" \
  "https://huggingface.co/keisuke-miyako/multilingual-e5-small-gguf-q4_k_m/resolve/main/multilingual-e5-small-Q4_k_m.gguf"
printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check --status
install -m 0644 "$temporary" "$model"
printf 'Story embedding model installed and verified: %s\n' "$model"
