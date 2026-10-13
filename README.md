# openai-kokoro-tts

**Experimental local text-to-speech API adapter for [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M).** This is an independently developed OpenAI-style integration, not an OpenAI product or a fork of the Kokoro model.

> **Release status (13 October 2026): repair required.** The public `main` branch has known functional and packaging defects. This README documents what is checked in and what has been observed separately; it is **not** a guarantee that the repository builds or generates speech from a fresh checkout.

## What is actually available?

| Area | Public `main` at `17a733bac108` | Evidence / limitation |
| --- | --- | --- |
| Flask routes | `POST /v1/audio/speech`, `GET /v1/models` exist | Broken server/handler contracts prevent an end-to-end claim |
| ONNX inference | ONNX Runtime session code exists | Character-code tokens and a placeholder voice embedding are not verified Kokoro conditioning |
| Audio output | WAV wrapper and file-writing handler exist | Handler returns a filename but Flask expects samples; advertised formats do not match encoding |
| Voice list | Route exists | Imported handler has no `get_voices()` method |
| Docker | Compose and Dockerfile exist | Build/runtime version and model-conversion paths conflict |
| Tests | Mock-based ONNX handler tests exist | No reproduced clean installation or model-backed end-to-end API acceptance test |
| GPU support | **Not on main** | Experimental [PR #2](https://github.com/matthewhand/openai-kokoro-tts/pull/2) is still open |

This status is based on source inspection rather than executing a model or publishing a release.

## CPU evidence recorded independently of public main

[Issue #1](https://github.com/matthewhand/openai-kokoro-tts/issues/1) records two live speech responses on **1 September 2026**:

| Environment | Recorded result | Actual execution provider |
| --- | --- | --- |
| Linux / GTX 1080 | HTTP 200, ID3 MP3, **1.02 s** | ONNX Runtime 1.29 CPU |
| Linux / AMD GPUs | HTTP 200, ID3 MP3, **4.08 s** | ONNX Runtime 1.28 CPU |

These are individual observations from existing containers, **not benchmarks**, not GPU inference, and not verification of the checked-in Dockerfile or `main` implementation. The recorded evidence does not pin a deployed source revision or image digest.

## Known release blockers

1. **Speech output:** `openai_kokoro_tts/onnx_tts_handler.py` returns an output **path**; `server.py` treats it as raw audio samples. Requested format and returned bytes can disagree.
2. **Voice API:** `server.py` calls a missing `get_voices()` method. `/v1/models` also lacks the speech route's authentication decorator.
3. **Model pipeline:** Handwritten character-code tokens and a fixed fake style embedding do not constitute verified Kokoro phonemization and voice conditioning.
4. **Docker:** Image uses Python **3.13** while package metadata declares `>=3.11,<3.13`; conversion output paths differ and conversion is invoked twice.
5. **Safety and reliability:** Fixed output filename, inconsistent authentication, incomplete input limits/validation and unverified concurrent-request behavior.
6. **Coverage:** No clean-install, real-audio, negative-authentication, output-format or resource-limit acceptance evidence for public `main`.

### Installation and API expectations

**There is currently no verified public-main quick start.** Do not use the older `docker compose up --build` instructions as proof of a working release, expose the unverified service to the internet, or submit confidential text.

The *intended* API request includes `input`, optional `voice`, `speed` and `response_format`. In source, `/v1/audio/speech` defaults to voice `af_bella` and format `wav`; the server's default port is **9090**, not 8000. Advertised MP3, WAV and other formats are **not all implemented correctly**. Treat both routes as experimental until source-level repairs and local end-to-end checks are documented.

Package metadata currently declares Python **3.11–3.12**. The checked-in sample configuration includes an unusable placeholder API key; supply a non-default secret before any isolated test. The repository's model setup script fetches assets, but does not establish that the required ONNX/voice files are usable.

## Experimental optional GPU work — separate branch

[PR #2, `feat/onnx-provider-auto`](https://github.com/matthewhand/openai-kokoro-tts/pull/2) at `e5538000a192` proposes CPU fallback and opt-in CUDA, DirectML, ROCm and MIGraphX execution-provider selection. It includes mock-backed provider-selection tests and platform-specific container examples.

**The PR is unmerged, does not repair the existing end-to-end speech-output contract, and is not proof of successful GPU inference.** Do not treat its README edits or compose examples as instructions for public `main`. Preserve CPU-only operation as the baseline until independent hardware validation. The separate Transformers handler generates placeholder audio and is not a supported backend.

## Privacy and security

The existing ONNX handler writes generated audio files to disk; a previous assertion that no data is stored was inaccurate. Review text logging, audio retention, filesystem permissions and concurrent file access before use. The speech endpoint checks an API key when enabled, but `/v1/models` does not apply the same decorator. The default Compose configuration binds a host network port. These are **not production security guarantees**.

Kokoro model weights, voices and dependencies can carry licenses distinct from this repository's [MIT license](LICENSE). Review and attribute them separately.

## Release acceptance gates

A future release must independently verify all of the following, with a pinned source revision:

- Fresh, repeatable Python 3.11/3.12 CPU installation with checksummed model and voice assets.
- A short synthetic text request returning **decodable, correctly labeled audio** with correct sample rate, duration and requested format.
- Authenticated voice/model listing; consistent 401 responses and no default or logged secrets.
- Validated text length, voice, speed, JSON body, resource limits and failure responses.
- Concurrent requests without filename collisions or cross-request leakage; documented deletion/retention behavior.
- Offline/local synthetic regressions, plus separately approved, low-load real model checks; no hosted GitHub CI required.
- GPU claims only after optional-provider tests run on their actual hardware.

**No gate is considered passed solely because the code compiles, an old container replied 200, or a mocked test passes.**

## Development direction

1. Restore a consistent CPU audio generation and response contract, plus local synthetic HTTP tests.
2. Repair build and model setup; perform a clean CPU smoke test.
3. Harden authentication, input boundaries, concurrency and privacy.
4. Independently reconcile GPU PR #2 against the CPU baseline.
5. Publish a tested quick start and lift the experimental designation only after all release gates pass.

## Attribution and responsible use

[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) is developed by hexgrad and its contributors; this project is a separate API adapter. Generated audio is synthetic. Do not use it for harmful impersonation, deception or violations of privacy.

Integration source: [MIT license](LICENSE). This project is not affiliated with or endorsed by OpenAI.
