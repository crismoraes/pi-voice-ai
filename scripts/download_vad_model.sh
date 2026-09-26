#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="$project_dir/models"
model_path="$models_dir/silero_vad.onnx"
download_url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
expected_sha256="9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"
temporary_path="$(mktemp)"

cleanup() {
    rm -f "$temporary_path"
}
trap cleanup EXIT

if [[ -f "$model_path" ]] && printf '%s  %s\n' "$expected_sha256" "$model_path" | sha256sum --check --status; then
    printf 'VAD model already installed: %s\n' "$model_path"
    exit 0
fi

mkdir -p "$models_dir"
curl --fail --location --retry 3 --output "$temporary_path" "$download_url"
printf '%s  %s\n' "$expected_sha256" "$temporary_path" | sha256sum --check --status
mv "$temporary_path" "$model_path"
printf 'VAD model installed: %s\n' "$model_path"
