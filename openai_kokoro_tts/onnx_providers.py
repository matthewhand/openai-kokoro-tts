"""Pick an ONNX Runtime execution provider without tying the default to NVIDIA.

CPU is always last. CUDA / DirectML / ROCm / MIGraphX are used only when that
EP is in the installed wheel and session creation succeeds.

kokoro-onnx reads a single name from ONNX_PROVIDER. We set that env var to the
chosen EP before constructing Kokoro().
"""

from __future__ import annotations

import logging
import os

CPU_PROVIDER = "CPUExecutionProvider"

# Prefer order for ONNX_PROVIDER=auto. DirectML is Windows-native only.
ACCEL_PROVIDERS = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "MIGraphXExecutionProvider",
    "ROCMExecutionProvider",
)

_ALIASES = {
    "auto": "auto",
    "cpu": CPU_PROVIDER,
    "cuda": "CUDAExecutionProvider",
    "dml": "DmlExecutionProvider",
    "directml": "DmlExecutionProvider",
    "rocm": "ROCMExecutionProvider",
    "migraphx": "MIGraphXExecutionProvider",
}


def normalize_provider(name: str | None) -> str:
    raw = (name if name is not None else os.getenv("ONNX_PROVIDER", "auto")) or "auto"
    raw = raw.strip()
    if not raw:
        return "auto"
    return _ALIASES.get(raw.lower(), raw)


def available_providers() -> list[str]:
    import onnxruntime as ort

    return list(ort.get_available_providers())


def candidate_providers(requested: str | None = None) -> list[str]:
    """Ordered EPs to try. Explicit requests still fall back to CPU unless CPU-only."""
    choice = normalize_provider(requested)
    if choice == "auto":
        avail = set(available_providers())
        selected = [p for p in ACCEL_PROVIDERS if p in avail]
        if CPU_PROVIDER not in selected:
            selected.append(CPU_PROVIDER)
        return selected or [CPU_PROVIDER]
    if choice == CPU_PROVIDER:
        return [CPU_PROVIDER]
    return [choice, CPU_PROVIDER]


def apply_env_provider(provider: str) -> None:
    """kokoro-onnx constructs the session from ONNX_PROVIDER (one name)."""
    os.environ["ONNX_PROVIDER"] = provider


def create_with_fallback(factory, requested: str | None = None):
    """Call factory() for each candidate after setting ONNX_PROVIDER. CPU last."""
    last_error = None
    tried = []
    for provider in candidate_providers(requested):
        tried.append(provider)
        apply_env_provider(provider)
        try:
            instance = factory()
        except Exception as exc:
            last_error = exc
            logging.warning("ONNX provider %s failed (%s); trying next", provider, exc)
            continue
        logging.info("ONNX provider selected: %s (tried %s)", provider, tried)
        return instance, provider
    raise RuntimeError(
        f"No ONNX provider worked. Tried: {tried}. Last error: {last_error}"
    ) from last_error
