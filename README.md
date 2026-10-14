# openai-kokoro-tts

**Experimental local text-to-speech API adapter for [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M).** This is an independently developed OpenAI-style integration, not an OpenAI product or a fork of the Kokoro model.

> **Status (14 October 2026): Experimental / Alpha.**
> Public `main` at `17a733bac108` has known functional, packaging, and conversion defects.
> The active work branch (`work/readme-fleet-kokoro-20261014`, continuing `work/kokoro-cpu-hardening-20261013` at `d3dfa135c916`) implements and independently proves the CPU repair, frozen Python 3.12 packaging, strict API contracts, and real containerized speech synthesis on CPU.

---

## 1. What is Tested and Working on This Branch

| Area | Status on Tested Branch | Evidence & Verification |
|---|---|---|
| **Audio Synthesis** | ✅ Verified | Real in-memory WAV and MP3 generation from Kokoro ONNX model at 24000 Hz mono. |
| **API Contract** | ✅ Verified | `POST /v1/audio/speech` and `GET /v1/models` OpenAI-compatible endpoints with Bearer auth. |
| **Input Validation** | ✅ Verified | Rejection of malformed/non-object JSON (400), text empty/too long (400), nonfinite/invalid speed (400), invalid/unknown voice (400), unsupported format (400), body > 16 KiB (413), missing/bad token (401). |
| **Production Server** | ✅ Verified | Gevent WSGI production serving path (`gevent.pywsgi.WSGIServer`) replaces development Flask server. |
| **Concurrency Safety** | ✅ Verified | Thread-safe generation lock prevents re-entrancy model collisions; no temporary audio files written to disk. |
| **Docker Packaging** | ✅ Verified | Clean-context build with `.dockerignore`, Debian slim + Python 3.12, system `espeak-ng` & `ffmpeg`, frozen `uv` dependencies, read-only model mount, loopback binding. |
| **Provider Negotiation** | ✅ Verified | Integrates PR #2 provider selection (`auto`, `cpu`, `cuda`, `dml`, `rocm`, `migraphx`) with safe fallback to CPU default and unit tests. |
| **Continuous Integration** | ✅ Restored | GitHub Actions workflow restored for Python 3.11 & 3.12 test matrix and clean Docker container build. |

---

## 2. Verified Live Inference Proof (14 October 2026)

On host `ubuntu-max` (Linux x86_64), the container was built from clean context (`docker build -t kokoro-cpu:test .`) and executed on an isolated loopback port (`127.0.0.1:19095`) with read-only model volume mounts and API key authentication (`API_KEY=test-cpu-proof-secret-2026`):

### Model & Voice Assets (Pinned Upstream)
- **Model**: `kokoro-v0_19.onnx` (`325,525,180 bytes`)  
  SHA256: `dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c`
- **Voices**: `voices.json` (`30,789,387 bytes`)  
  SHA256: `ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df`

### Test 1: Models Listing (`GET /v1/models`)
- Unauthenticated request: **HTTP 401 Unauthorized** (enforced before model load).
- Authenticated request: **HTTP 200 OK**.
- Returned voices (11 total): `af`, `af_bella`, `af_nicole`, `af_sarah`, `af_sky`, `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`.

### Test 2: WAV Synthesis (`POST /v1/audio/speech`, format `wav`)
- Text: `"Kokoro CPU synthesis is fully operational."`, voice: `"af_bella"`.
- Response: **HTTP 200 OK**, `Content-Type: audio/wav`, size: **157,740 bytes**.
- `ffprobe` inspection:
  - Codec: `pcm_s16le`
  - Sample rate: **24,000 Hz**, Channels: **1 (mono)**
  - Duration: **3.285 seconds** (78,848 samples)
- Waveform analysis:
  - Min: `-0.544`, Max: `+0.505`, RMS amplitude: `0.0862`
  - Active non-silent samples (`|amp| > 0.01`): **50,385 (63.9%)**

### Test 3: MP3 Synthesis (`POST /v1/audio/speech`, format `mp3`)
- Text: `"Kokoro CPU synthesis is fully operational."`, voice: `"af_bella"`.
- Response: **HTTP 200 OK**, `Content-Type: audio/mpeg`, size: **53,421 bytes**, initial ID3 header.
- Latency: **0.97 s**.
- `ffprobe` inspection:
  - Codec: `mp3` (`Lavf59.27.100`)
  - Sample rate: **24,000 Hz**, Channels: **1 (mono)**, Bitrate: **128 kbps**
  - Duration: **3.336 seconds**
- Decoded PCM analysis:
  - Min: `-0.517`, Max: `+0.479`, RMS amplitude: `0.0812`
  - Active non-silent samples (`|amp| > 0.01`): **49,751 (62.1%)**

---

## 3. Quick Start (CPU Local / Docker)

### Prerequisites
- Docker or Python 3.11–3.12 with `uv`
- `ffmpeg` and `espeak-ng`

### 1. Model Asset Setup
Download and verify the pinned upstream ONNX model and voice configurations:
```bash
./setup_models.sh
```
*(On Windows PowerShell, use `./setup_models.ps1`)*

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and specify a secure API_KEY (fail-closed if empty or placeholder)
```

### 3. Run with Docker Compose
```bash
docker compose up -d
```
The server will start on `127.0.0.1:9090` using the production WSGI server.

### 4. Test Synthesis
```bash
# List models
curl -s -H "Authorization: Bearer <YOUR_KEY>" http://127.0.0.1:9090/v1/models

# Generate MP3 speech
curl -X POST http://127.0.0.1:9090/v1/audio/speech \
  -H "Authorization: Bearer <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world from Kokoro TTS.", "voice": "af_bella", "response_format": "mp3"}' \
  -o speech.mp3
```

---

## 4. Optional GPU / Accelerator Providers (PR #2 Integration)

By default, the server runs on CPU (`ONNX_PROVIDER=CPUExecutionProvider`).

Through integration of [PR #2](https://github.com/matthewhand/openai-kokoro-tts/pull/2), `ONNX_PROVIDER=auto|cpu|cuda|dml|rocm|migraphx` is supported with automatic fallback to CPU:
- `auto`: Attempts detected accelerators (`CUDA` → `DirectML` → `MIGraphX` → `ROCm`), always falling back to CPU.
- `cpu`: Explicit CPU-only execution.
- Accelerated execution requires platform-specific compose files (`docker-compose.override.yml.example` for NVIDIA, `docker-compose.rocm.yml.example` for ROCm) and installing the respective ORT wheel (`onnxruntime-gpu` or `onnxruntime-rocm`), which are mutually exclusive with the base CPU wheel.

---

## 5. Remaining Release Gates

Before lifting experimental/alpha status, the following release gates remain:

1. **Human Auditory Intelligibility Gate**: While audio waveform validity, frequency spectrum, and decodability are mechanically proven (3.28s, 24kHz, 63.9% non-silence), formal subjective listening across diverse voice models remains unverified in this non-interactive environment.
2. **Hardware GPU Live Proof**: While provider selection and fallback logic are tested, live GPU kernel acceleration on CUDA or ROCm requires dedicated hardware verification with GPU devices mounted and accelerator wheels active.
3. **High-Concurrency Load Testing**: Under heavy synthetic concurrency, the serialized inference lock prevents race conditions; sustained throughput and latency under multi-client load require benchmarking.

---

## 6. Attribution and License

- **Kokoro-82M**: Developed by [hexgrad](https://huggingface.co/hexgrad/Kokoro-82M).
- **kokoro-onnx**: Developed by [thewh1teagle](https://github.com/thewh1teagle/kokoro-onnx).
- **openai-kokoro-tts**: Independent integration under the [MIT License](LICENSE).
- Synthetic audio generated by Kokoro must be used responsibly and in compliance with applicable laws.
