#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_dir="$project_dir/models"
target="$model_dir/qwen3.5-2b-q4_k_m.gguf"
partial="$target.part"
url="https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"
expected_sha256="aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223"

mkdir -p "$model_dir"
if [[ -f "$target" ]] && echo "$expected_sha256  $target" | sha256sum --check --status; then
    printf 'Local LLM model is already installed.\n'
    exit 0
fi

curl --fail --location --retry 4 --continue-at - --output "$partial" "$url"
echo "$expected_sha256  $partial" | sha256sum --check --status || {
    rm -f "$partial"
    printf 'Local LLM checksum verification failed.\n' >&2
    exit 1
}
mv "$partial" "$target"
printf 'Installed %s.\n' "$target"
