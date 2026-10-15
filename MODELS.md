# Model assets

The server needs two files in `models/kokoro/` (git-ignored, mounted read-only into
the container at `/app/models/kokoro`). `setup_models.sh` / `setup_models.ps1`
download them and verify exact size + SHA-256.

| File | Bytes | SHA-256 | Upstream URL |
|---|---|---|---|
| `kokoro-v0_19.onnx` | 325,525,180 | `dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c` | <https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx> |
| `voices.json` | 30,789,387 | `ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df` | <https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json> |

Both are assets of the `model-files` release of
[thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files).

## Why this pair

`uv.lock` pins `kokoro-onnx==0.2.6`, whose `Kokoro` class loads a **JSON** voices file
(`json.load`) and whose README names `kokoro-v0_19.onnx` + `voices.json`. It also
provides `Kokoro.from_session()`, which `onnx_tts_handler.py` uses. Later
`kokoro-onnx` releases switched to `voices-v1.0.bin` + `kokoro-v1.0.onnx` and are
**not** compatible with these files; `pyproject.toml` allows `>=0.2.6`, so re-locking
without an upper bound could silently break this pairing.

## Provenance and licenses

| Item | Source | License |
|---|---|---|
| Kokoro-82M model weights | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0 (model card metadata) |
| `kokoro-v0_19.onnx` | ONNX export; release notes: "optimized f32 version from [taylorchu/kokoro-onnx](https://github.com/taylorchu/kokoro-onnx/releases/tag/v0.1.0)" | Derived from the Apache-2.0 weights; `taylorchu/kokoro-onnx` is MIT (GitHub license API) |
| `voices.json` | Published by thewh1teagle/kokoro-onnx | See note below |
| `kokoro-onnx` (Python library and release hosting repo) | <https://github.com/thewh1teagle/kokoro-onnx> | MIT |

**Provenance of `voices.json` is not documented upstream.** The `model-files` release
notes describe only the `.onnx` files and `voices.bin`; they say nothing about
`voices.json`. It is presumably the Kokoro v0.19 style vectors converted to JSON
by the `kokoro-onnx` maintainers (the library's own README links to it), but that is
an inference, not a stated fact. Its license is therefore best assumed to follow the
Apache-2.0 Kokoro weights it derives from; verify before redistributing it.

GitHub does not publish a `digest` for the `model-files` release assets (it is
`null` in the release API), so the SHA-256 values above could not be cross-checked
against upstream metadata. Sizes match the upstream asset sizes exactly (HEAD
`Content-Length` and the release API). The SHA-256 values are also quoted
independently in other public repositories, but no authoritative upstream
checksum exists; treat them as trust-on-first-use pins.

The container image additionally installs the system package `espeak-ng` (GPL-3.0)
for phonemization.

## Verify manually

PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 models\kokoro\kokoro-v0_19.onnx, models\kokoro\voices.json
(Get-Item models\kokoro\kokoro-v0_19.onnx).Length   # 325525180
(Get-Item models\kokoro\voices.json).Length         # 30789387
```

bash:

```bash
cd models/kokoro
sha256sum -c <<'EOF'
dece567789190ebe987bd245d95c09d5ac86de28ff0c325c2e3faaf3de04442c  kokoro-v0_19.onnx
ff3f0e5cf156088d4847f277e43c49e3248b798b47027d01afd75d78065744df  voices.json
EOF
stat -c %s kokoro-v0_19.onnx voices.json   # 325525180, 30789387 (macOS: stat -f %z)
```

The container runs as uid 10001, so the files must be world-readable
(`chmod 0644`; the setup scripts take care of this on Linux).
