#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="$project_dir/models"
model_name="sherpa-onnx-whisper-tiny"
model_dir="$models_dir/$model_name"
archive="$(mktemp --suffix=.tar.bz2)"
expected_sha256="c46116994e539aa165266d96b325252728429c12535eb9d8b6a2b10f129e66b1"
download_url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$model_name.tar.bz2"

cleanup() {
    rm -f "$archive"
}
trap cleanup EXIT

required_files=(
    "$model_dir/tiny-encoder.int8.onnx"
    "$model_dir/tiny-decoder.int8.onnx"
    "$model_dir/tiny-tokens.txt"
)

model_complete=true
for required_file in "${required_files[@]}"; do
    if [[ ! -f "$required_file" ]]; then
        model_complete=false
        break
    fi
done

if [[ "$model_complete" == true ]]; then
    printf 'STT model already installed: %s\n' "$model_dir"
    exit 0
fi

mkdir -p "$models_dir"
curl --fail --location --retry 3 --output "$archive" "$download_url"
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
rm -rf "$model_dir"
tar -xjf "$archive" -C "$models_dir"

for required_file in "${required_files[@]}"; do
    [[ -f "$required_file" ]] || {
        printf 'Missing model file after extraction: %s\n' "$required_file" >&2
        exit 1
    }
done

printf 'STT model installed: %s\n' "$model_dir"
