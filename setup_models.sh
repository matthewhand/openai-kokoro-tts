#!/usr/bin/env bash
# Download the pinned Kokoro v0.19 ONNX model + voices.json (the pair expected by
# kokoro-onnx 0.2.6, see MODELS.md) into ./models/kokoro, verifying exact size
# and SHA-256. Idempotent: a file that already matches is left alone.
# Mirrors setup_models.ps1 - keep the two in sync.
set -euo pipefail

# Always operate relative to the repo root (where docker-compose.yml mounts ./models).
cd "$(dirname "${BASH_SOURCE[0]}")"

MODEL_DIR="models/kokoro"

BASE_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files"

MODEL_NAME="kokoro-v0_19.onnx"
MODEL_SIZE=325525180
MODEL_SHA256="dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c"

VOICES_NAME="voices.json"
VOICES_SIZE=30789387
VOICES_SHA256="ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df"

if command -v sha256sum >/dev/null 2>&1; then
    sha256_of() { sha256sum "$1" | awk '{print $1}'; }
elif command -v shasum >/dev/null 2>&1; then
    sha256_of() { shasum -a 256 "$1" | awk '{print $1}'; }
else
    echo "Error: need sha256sum or shasum on PATH" >&2
    exit 1
fi
command -v curl >/dev/null 2>&1 || { echo "Error: curl is required" >&2; exit 1; }

size_of() { wc -c < "$1" | tr -d '[:space:]'; }

# 0 if $1 exists with exactly size $2 and sha256 $3.
is_valid() {
    local file="$1" size="$2" sha="$3"
    [ -f "$file" ] || return 1
    [ "$(size_of "$file")" = "$size" ] || return 1
    [ "$(sha256_of "$file")" = "$sha" ] || return 1
}

CURRENT_TMP=""
cleanup() {
    if [ -n "$CURRENT_TMP" ]; then
        rm -f -- "$CURRENT_TMP"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fetch_asset() {
    local name="$1" size="$2" sha="$3"
    local dest="$MODEL_DIR/$name"
    local tmp="$dest.tmp"

    if is_valid "$dest" "$size" "$sha"; then
        echo "$name already present (size and SHA-256 OK)."
        chmod 0644 "$dest"
        return 0
    fi

    echo "Downloading $name ($size bytes)..."
    CURRENT_TMP="$tmp"
    rm -f -- "$tmp"   # discard any partial file from an interrupted run
    curl -fL --retry 3 --proto '=https' --tlsv1.2 -o "$tmp" "$BASE_URL/$name"

    local actual_size actual_sha
    actual_size="$(size_of "$tmp")"
    if [ "$actual_size" != "$size" ]; then
        echo "Error: $name size mismatch (expected $size, got $actual_size)" >&2
        exit 1
    fi
    actual_sha="$(sha256_of "$tmp")"
    if [ "$actual_sha" != "$sha" ]; then
        echo "Error: $name SHA-256 mismatch (expected $sha, got $actual_sha)" >&2
        exit 1
    fi

    # The container runs as uid 10001 and mounts this directory read-only, so the
    # files must be world-readable regardless of the caller's umask.
    chmod 0644 "$tmp"
    mv -f -- "$tmp" "$dest"
    CURRENT_TMP=""
    echo "$name verified."
}

echo "Setting up Kokoro ONNX model and voices assets in $MODEL_DIR..."
mkdir -p "$MODEL_DIR"
# Best effort: the directories may already exist owned by someone else (e.g. root,
# if `docker compose up` created ./models first); that must not abort the download.
chmod 0755 models "$MODEL_DIR" 2>/dev/null || true

fetch_asset "$VOICES_NAME" "$VOICES_SIZE" "$VOICES_SHA256"
fetch_asset "$MODEL_NAME" "$MODEL_SIZE" "$MODEL_SHA256"

echo "Kokoro ONNX CPU assets ready in $MODEL_DIR."
