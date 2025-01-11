# Use an Astral uv image with Python 3.13
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install Node.js, npm, and additional system dependencies
RUN apt-get update && apt-get install -y \
    git-lfs \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Copy uvx alongside uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /bin/

# Set working directory inside the container
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY openai_kokoro_tts/ openai_kokoro_tts/
COPY tests/ tests/

# Clone the Kokoro-82M model repository
RUN git lfs install && git clone https://huggingface.co/hexgrad/Kokoro-82M /app/models/kokoro

# Set environment variables to prioritize uv
ENV UV_SYSTEM_PYTHON=1
ENV PATH="/app/.venv/bin:$PATH"

# Initialize uv environment and add dependencies
RUN uv sync

# Expose the application port (default 8000, configurable via $PORT)
EXPOSE 8000

# Run the Flask server
CMD uv run openai_kokoro_tts/server.py
