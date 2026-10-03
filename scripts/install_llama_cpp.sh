#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$project_dir/vendor/llama.cpp"
build_dir="$source_dir/build"
version="v0.5.0"
commit="d2e54583c7452353eb35d40431281f6ee984332f"

if [[ -x "$build_dir/bin/llama-server" ]] &&
   [[ -f "$source_dir/.pivoice-commit" ]] &&
   [[ "$(cat "$source_dir/.pivoice-commit")" == "$commit" ]]; then
    printf 'llama.cpp %s is already built.\n' "$version"
    exit 0
fi

mkdir -p "$(dirname "$source_dir")"
if [[ ! -d "$source_dir/.git" ]]; then
    rm -rf "$source_dir"
    git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$source_dir"
fi

git -C "$source_dir" fetch --depth 1 origin "$commit"
git -C "$source_dir" checkout --detach "$commit"
cmake -S "$source_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_CURL=OFF \
    -DGGML_NATIVE=ON \
    -DGGML_OPENMP=ON \
    -DGGML_BLAS=OFF
cmake --build "$build_dir" --config Release --target llama-server -j "$(nproc)"
printf '%s' "$commit" > "$source_dir/.pivoice-commit"
printf 'Built llama.cpp %s at %s.\n' "$version" "$build_dir/bin/llama-server"
