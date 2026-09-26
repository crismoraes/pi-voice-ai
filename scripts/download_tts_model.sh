#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="$project_dir/models"
model_name="vits-piper-pt_BR-jeff-medium"
model_dir="$models_dir/$model_name"
archive="$(mktemp --suffix=.tar.bz2)"
expected_sha256="da4c870fc7b20600c74261b3e1dd1c816da2ce063e18c46e1f2cd86dea88f3f0"
download_url="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$model_name.tar.bz2"

cleanup() {
    rm -f "$archive"
}
trap cleanup EXIT

required_paths=(
    "$model_dir/pt_BR-jeff-medium.onnx"
    "$model_dir/tokens.txt"
    "$model_dir/espeak-ng-data"
)

model_complete=true
for required_path in "${required_paths[@]}"; do
    if [[ ! -e "$required_path" ]]; then
        model_complete=false
        break
    fi
done

if [[ "$model_complete" == true ]]; then
    printf 'TTS model already installed: %s\n' "$model_dir"
    exit 0
fi

mkdir -p "$models_dir"
curl --fail --location --retry 3 --output "$archive" "$download_url"
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
rm -rf "$model_dir"
tar -xjf "$archive" -C "$models_dir"

for required_path in "${required_paths[@]}"; do
    [[ -e "$required_path" ]] || {
        printf 'Missing model path after extraction: %s\n' "$required_path" >&2
        exit 1
    }
done

printf 'TTS model installed: %s\n' "$model_dir"
