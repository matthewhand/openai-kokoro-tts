# Model assets

The server needs two files in `models/kokoro/` (git-ignored; mounted read-only
into the container at `/app/models/kokoro`). `setup_models.sh` and
`setup_models.ps1` download them and refuse to keep a file whose size or
SHA-256 differs from the pin.

| File | Bytes | SHA-256 |
|---|---|---|
| `kokoro-v1.0.onnx` | 325,505,369 | `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a` |
| `voices-v1.0.bin` | 28,214,398 | `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d` |

Source: the `model-files-v1.1` release of
[thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)
(1 March 2025), the current model release as of October 2026.

```
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

`voices-v1.0.bin` carries 54 voices. `kokoro-v1.0.onnx` is the English model;
the same release also ships a Chinese/English `kokoro-v1.1-zh` pair and fp16/int8
quantisations, which this project does not use.

## Why this pair

`uv.lock` pins `kokoro-onnx==0.6.1`. From 0.3.0 onward the library loads voices
with `numpy.load`, so it needs the `.bin` file, and the project README names
`kokoro-v1.0.onnx` together with `voices-v1.0.bin`. The earlier pair
(`kokoro-v0_19.onnx` + `voices.json`) belongs to `kokoro-onnx` 0.2.x and does
not load under 0.6.1.

The pins were hashed locally after download on 15 October 2026. GitHub publishes
no digest for these release assets, so there is no upstream checksum to compare
against; treat them as trust-on-first-use.

## Provenance and licences

| Item | Source | Licence |
|---|---|---|
| Kokoro-82M weights | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0 |
| `kokoro-v1.0.onnx` | exported by thewh1teagle/kokoro-onnx from the Kokoro weights | Apache-2.0, as a derivative of the weights |
| `voices-v1.0.bin` | style vectors published by thewh1teagle/kokoro-onnx | follows the weights |
| `kokoro-onnx` library | thewh1teagle/kokoro-onnx | MIT |
| `espeak-ng` | system package, used for phonemisation | GPL-3.0 |

## Check by hand

```powershell
Get-FileHash -Algorithm SHA256 models\kokoro\kokoro-v1.0.onnx, models\kokoro\voices-v1.0.bin
```

```bash
cd models/kokoro && sha256sum -c <<'EOF'
beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a  kokoro-v1.0.onnx
bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d  voices-v1.0.bin
EOF
```

The container runs as uid 10001, so both files must be world-readable. The
setup scripts set `0644`.
