# openai-kokoro-tts

Local text-to-speech API with an OpenAI-compatible surface, backed by
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) through
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx). Independently
developed; not an OpenAI product and not a fork of the Kokoro model.

CPU-first. Runs on a machine with no GPU.

## What it does

- `POST /v1/audio/speech` returns WAV or MP3, 24 kHz mono, generated in memory.
- `GET /v1/models` lists the voices bundled with the model.
- Bearer authentication, on by default and fail-closed: a missing, placeholder,
  or malformed `REQUIRE_API_KEY` / `API_KEY` aborts startup rather than
  silently serving unauthenticated.
- One inference at a time. Extra requests wait briefly, then get `503` with
  `Retry-After` instead of queueing without bound.
- Errors are sanitised. Validation failures return `400`; everything else
  returns a generic `500`. Request text, paths and keys never appear in a response.

## Verified on this machine (15 October 2026)

Windows 10, AMD Ryzen 9 5950X, Python 3.12.10, ONNX Runtime CPU, no GPU.
Model `kokoro-v1.0.onnx` with `voices-v1.0.bin` (54 voices), `kokoro-onnx` 0.6.1.

| Check | Result |
|---|---|
| `pytest` | 73 passed |
| Model SHA-256 | matches the pin in `MODELS.md` |
| Active provider | `CPUExecutionProvider` |
| WAV | `pcm_s16le`, 24 kHz, mono, 3.316 s for a 6-word sentence |
| MP3 | `libmp3lame`, 24 kHz, mono, 128 kbps |
| Latency | 0.96 s cold, 0.71–0.76 s warm |
| Memory | ~840 MB peak working set while loaded |
| Startup | ~0.5 s to accept connections; model loads on first request |
| Shutdown | clean on `SIGTERM` and on Windows console break |
| Auth | missing and wrong tokens get `401` on both endpoints |

An earlier run on `ubuntu-max` (14 October 2026) proved the same contract
against the older `kokoro-v0_19` model. Those numbers are superseded by the
table above.

## Run it

Needs Python 3.11 or 3.12, `ffmpeg` and `espeak-ng`.

```bash
./setup_models.sh          # Windows: ./setup_models.ps1
cp .env.example .env       # set a real API_KEY
python -m openai_kokoro_tts.server
```

`setup_models` downloads the two pinned files into `models/kokoro/` and checks
size and SHA-256 before keeping them. Details, sources and licences are in
`MODELS.md`.

```bash
curl -s -H "Authorization: Bearer $API_KEY" http://127.0.0.1:9090/v1/models

curl -X POST http://127.0.0.1:9090/v1/audio/speech \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"Hello from Kokoro.","voice":"af_bella","response_format":"mp3"}' \
  -o speech.mp3
```

## Docker

```bash
docker compose up -d
```

The image runs as uid 10001 with a read-only root filesystem, drops all
capabilities, and binds to `127.0.0.1:9090`. Model files are mounted read-only
from `./models` and must be world-readable, which the setup scripts arrange.
The container is not built or run as part of the verification above.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `API_KEY` | none | required; startup fails on empty or placeholder values |
| `REQUIRE_API_KEY` | `true` | only `true` and `false` are accepted |
| `DEFAULT_VOICE` | `af_bella` | must exist in the loaded voice file |
| `ONNX_MODEL_PATH` | `models/kokoro/kokoro-v1.0.onnx` | |
| `VOICES_PATH` | `models/kokoro/voices-v1.0.bin` | |
| `ONNX_PROVIDER` | `cpu` | `auto`, `cpu`, `cuda`, `dml`, `rocm`, `migraphx`; falls back to CPU |
| `INFERENCE_MAX_WAITING` | `1` | requests allowed to wait for the model |
| `INFERENCE_QUEUE_TIMEOUT_S` | `10` | then `503` |
| `PORT` / `HOST` | `9090` / `0.0.0.0` | compose overrides the bind to loopback |

## Accelerators

Untested. `docker-compose.override.yml.example` (NVIDIA) and
`docker-compose.rocm.yml.example` (AMD) show how to rebuild the image with the
matching ONNX Runtime wheel. The CPU wheel and an accelerator wheel cannot be
installed together. If the requested provider fails to load, the server falls
back to CPU and logs which one is actually active.

## Limits

- Input is capped at 1000 characters and request bodies at 16 KiB.
- Inference is serial. Throughput is one utterance at a time.
- No GPU or ROCm path has been run.
- Nobody has listened to the output; only the decoded waveform was checked.

## Licence

Kokoro-82M weights are Apache-2.0. `kokoro-onnx` is MIT. This project is MIT.
See `MODELS.md` for the voice-file provenance.
