"""Thin Kokoro-ONNX adapter with provider fallback. No placeholder tokenization or output files."""
import math
import os

import numpy as np

from openai_kokoro_tts.admission import InferenceGate
from openai_kokoro_tts.errors import RequestValidationError
from openai_kokoro_tts.onnx_providers import CPU_PROVIDER, create_with_fallback


class OnnxTTSHandler:
    def __init__(self, default_voice=None, kokoro_factory=None, requested_provider=None, gate=None):
        self.default_voice = default_voice or os.getenv("DEFAULT_VOICE", "af_bella")
        model_path = os.getenv("ONNX_MODEL_PATH", "models/kokoro/kokoro-v0_19.onnx")
        voices_path = os.getenv("VOICES_PATH", "models/kokoro/voices.json")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"ONNX model file not found: {model_path}")
        if not os.path.isfile(voices_path):
            raise FileNotFoundError(f"Kokoro voice file not found: {voices_path}")
        if kokoro_factory is not None:
            self.kokoro = kokoro_factory(model_path, voices_path)
            self.active_provider = CPU_PROVIDER
        else:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro

            def session_factory():
                provider = os.environ.get("ONNX_PROVIDER", CPU_PROVIDER)
                session = ort.InferenceSession(model_path, providers=[provider])
                # ORT silently falls back to CPU when a requested EP is not in the
                # installed wheel; refuse that so active_provider is truthful.
                actual = session.get_providers()
                if not actual or actual[0] != provider:
                    raise RuntimeError("requested ONNX provider is not active")
                return Kokoro.from_session(session, voices_path)

            self.kokoro, self.active_provider = create_with_fallback(
                session_factory, requested=requested_provider
            )
        # Bounded admission (explicit busy response), not an unbounded lock queue.
        self.gate = gate if gate is not None else InferenceGate.from_env()
        self.valid_voices = sorted(self.kokoro.get_voices())
        if self.default_voice not in self.valid_voices:
            raise ValueError("Default voice not found in loaded voice data")

    def get_voices(self):
        return list(self.valid_voices)

    def generate_speech(self, text, voice=None, speed=1.0):
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise RequestValidationError("input must be nonempty text of at most 1000 characters")
        voice = voice or self.default_voice
        if voice not in self.valid_voices:
            raise RequestValidationError("Unknown voice")
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or not 0.5 <= speed <= 2.0
        ):
            raise RequestValidationError("speed must be a number between 0.5 and 2.0")

        # A single shared model is not assumed re-entrant: one inference at a time,
        # bounded waiting, ServerBusyError beyond that (see admission.py).
        with self.gate.admit():
            samples, sample_rate = self.kokoro.create(text, voice=voice, speed=float(speed), lang="en-us")
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
            raise RuntimeError("Kokoro returned invalid mono audio")
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or not 8000 <= sample_rate <= 96000:
            raise RuntimeError("Kokoro returned invalid sample rate")
        if samples.size > int(sample_rate) * 120:
            raise RuntimeError("Generated audio exceeds 120-second limit")
        return samples, int(sample_rate)
