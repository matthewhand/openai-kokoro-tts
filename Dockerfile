# CPU-first Docker image. Model files are NOT baked in: mount them read-only at
# /app/models (see MODELS.md / setup_models.sh). Runs as a non-root user and
# writes nothing to disk, so it is compatible with `read_only: true` + tmpfs /tmp.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# ONNX Runtime wheel variant. Default is the CPU wheel from uv.lock. Opt-in
# accelerator builds (UNTESTED, see docker-compose.override.yml.example and
# docker-compose.rocm.yml.example) replace it, e.g.
#   --build-arg ORT_PACKAGE=onnxruntime-gpu==1.31.0
# The CPU and GPU/ROCm wheels share the `onnxruntime/` package dir and cannot coexist.
ARG ORT_PACKAGE=onnxruntime

# Use the image's system Python only: a uv-managed interpreter would be installed
# under /root and be unreadable by the unprivileged runtime user.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Dedicated unprivileged account (fixed uid/gid so bind-mount permissions are predictable).
RUN groupadd --system --gid 10001 kokoro \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin kokoro

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY openai_kokoro_tts/ ./openai_kokoro_tts/

RUN uv sync --frozen --no-dev

# Optional ORT swap into the project venv (no-op for the default CPU build).
RUN if [ "$ORT_PACKAGE" != "onnxruntime" ]; then \
        uv pip uninstall --python /app/.venv/bin/python onnxruntime \
        && uv pip install --python /app/.venv/bin/python "$ORT_PACKAGE"; \
    fi

# Application code and the venv stay root-owned and world-readable/executable
# (uv/pip create them 0755/0644): the runtime user can read and run everything
# but cannot modify it, so no chown of /app is needed. /app/models is only a
# mount point for the read-only model volume.
RUN mkdir -p /app/models

# ONNX_PROVIDER is intentionally NOT set here. It is read via
# onnx_providers.normalize_provider() (unset -> "auto"). With the default CPU
# wheel "auto" can only resolve to CPUExecutionProvider, so a baked-in CPU value
# would be redundant, and in an ORT_PACKAGE=onnxruntime-gpu/rocm build it would
# silently disable the accelerator. The CPU-first default is pinned explicitly in
# docker-compose.yml instead.
#
# NUMBA_CACHE_DIR: librosa (30 `cache=True` jit sites) makes numba look for a
# writable cache dir at import time and fails if none exists; with a read-only
# rootfs and an unwritable site-packages the only usable place is the tmpfs.
# HF_HOME: keep any transformers/huggingface cache writes off the read-only rootfs.
ENV PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    NUMBA_CACHE_DIR=/tmp/numba-cache \
    HF_HOME=/tmp/hf \
    HOST=0.0.0.0 \
    PORT=9090

USER 10001:10001
EXPOSE 9090

# Liveness only: the server has no /health route (both routes require the API key
# and the model is lazy-loaded on first request), so an HTTP probe would either
# need the secret or trigger a model load. A bare TCP connect to the listening
# port needs neither and sends no HTTP request. It does NOT prove the model
# assets are present or loadable.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('PORT', '9090'))), 3).close()"]

# Production WSGI serving path via waitress (threaded; see server.serve)
CMD ["python", "-m", "openai_kokoro_tts.server"]
