# CPU-first development image. Requires model files mounted at runtime.
# Source-only draft: a fresh build and model-backed run are NOT yet verified.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY openai_kokoro_tts/ ./openai_kokoro_tts/

RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    HOST=0.0.0.0 \
    PORT=9090 \
    ONNX_PROVIDER=CPUExecutionProvider
EXPOSE 9090

# No model downloads, startup installs, model conversion or output persistence.
CMD ["uv", "run", "--no-sync", "python", "-m", "openai_kokoro_tts.server"]
