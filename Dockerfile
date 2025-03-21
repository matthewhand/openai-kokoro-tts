# Use an Astral uv image with Python 3.13
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install Node.js, npm, and additional system dependencies
RUN apt-get update && apt-get install -y \
    git-lfs \
    espeak-ng \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Set working directory inside the container
WORKDIR /app

# Copy project files
COPY pyproject.toml ./ 
COPY openai_kokoro_tts/ openai_kokoro_tts/
COPY tests/ tests/

# Clone the Kokoro-82M model repository
RUN git lfs install && git clone https://huggingface.co/hexgrad/Kokoro-82M /app/models/kokoro

# Inject setup_models.sh logic directly (future-proofed to check for any .pth file)
RUN if [ -z "$(find /app/models/kokoro -maxdepth 1 -name '*.pth')" ]; then \
      echo "Error: No .pth file found in /app/models/kokoro." && exit 1; \
    fi && \
    curl -L "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json" -o /app/models/kokoro/voices.json && \
    echo "Model and dependencies have been successfully set up! Model directory: /app/models/kokoro, Voice directory: voices"

# Copy the conversion script
COPY openai_kokoro_tts/convert_to_onnx.py openai_kokoro_tts/

# Install Python dependencies for ONNX conversion
RUN uv pip install --system torch onnxruntime
# Run the conversion script and move the output to the correct location
RUN python /app/openai_kokoro_tts/convert_to_onnx.py && mv /app/openai_kokoro_tts/kokoro.onnx /app/models/kokoro/
RUN python openai_kokoro_tts/convert_to_onnx.py && mv /app/openai_kokoro_tts/kokoro.onnx /app/models/kokoro/

# Set environment variables to prioritize uv and Python path
ENV UV_SYSTEM_PYTHON=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Initialize uv environment and add dependencies
RUN uv sync

# Expose the application port (default 8000, configurable via $PORT)
EXPOSE 8000

# Run the Flask server
CMD uv run openai_kokoro_tts/server.py
