#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="models/kokoro"
mkdir -p "$MODEL_DIR"

MODEL_FILE="$MODEL_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$MODEL_DIR/voices.json"

MODEL_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

EXPECTED_MODEL_SHA256="dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c"
EXPECTED_VOICES_SHA256="ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df"

verify_checksum() {
    local file="$1"
    local expected="$2"
    if [ -f "$file" ]; then
        local actual
        actual=$(sha256sum "$file" | awk '{print $1}')
        if [ "$actual" = "$expected" ]; then
            return 0
        fi
    fi
    return 1
}

echo "Setting up Kokoro ONNX model and voices assets in $MODEL_DIR..."

if verify_checksum "$VOICES_FILE" "$EXPECTED_VOICES_SHA256"; then
    echo "voices.json already present with valid SHA256."
else
    echo "Downloading voices.json..."
    curl -fL "$VOICES_URL" -o "$VOICES_FILE.tmp"
    actual_voices_sha256=$(sha256sum "$VOICES_FILE.tmp" | awk '{print $1}')
    if [ "$actual_voices_sha256" != "$EXPECTED_VOICES_SHA256" ]; then
        echo "Error: voices.json SHA256 mismatch (expected $EXPECTED_VOICES_SHA256, got $actual_voices_sha256)"
        rm -f "$VOICES_FILE.tmp"
        exit 1
    fi
    mv "$VOICES_FILE.tmp" "$VOICES_FILE"
    echo "voices.json verified."
fi

if verify_checksum "$MODEL_FILE" "$EXPECTED_MODEL_SHA256"; then
    echo "kokoro-v0_19.onnx already present with valid SHA256."
else
    echo "Downloading kokoro-v0_19.onnx..."
    curl -fL "$MODEL_URL" -o "$MODEL_FILE.tmp"
    actual_model_sha256=$(sha256sum "$MODEL_FILE.tmp" | awk '{print $1}')
    if [ "$actual_model_sha256" != "$EXPECTED_MODEL_SHA256" ]; then
        echo "Error: kokoro-v0_19.onnx SHA256 mismatch (expected $EXPECTED_MODEL_SHA256, got $actual_model_sha256)"
        rm -f "$MODEL_FILE.tmp"
        exit 1
    fi
    mv "$MODEL_FILE.tmp" "$MODEL_FILE"
    echo "kokoro-v0_19.onnx verified."
fi

echo "Kokoro ONNX CPU assets ready in $MODEL_DIR."
