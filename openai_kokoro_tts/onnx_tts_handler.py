"""Thin Kokoro-ONNX adapter. No placeholder tokenization or output files."""
import os
import threading

import numpy as np


class OnnxTTSHandler:
    def __init__(self, default_voice=None, kokoro_factory=None):
        self.default_voice = default_voice or os.getenv("DEFAULT_VOICE", "af_bella")
        model_path = os.getenv("ONNX_MODEL_PATH", "models/kokoro/kokoro-v0_19.onnx")
        voices_path = os.getenv("VOICES_PATH", "models/kokoro/voices.json")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"ONNX model file not found: {model_path}")
        if not os.path.isfile(voices_path):
            raise FileNotFoundError(f"Kokoro voice file not found: {voices_path}")
        if kokoro_factory is None:
            from kokoro_onnx import Kokoro
            kokoro_factory = Kokoro
        self.kokoro = kokoro_factory(model_path, voices_path)
        self._inference_lock = threading.Lock()
        self.valid_voices = sorted(self.kokoro.get_voices())
        if self.default_voice not in self.valid_voices:
            raise ValueError(f"Default voice {self.default_voice!r} not found in loaded voice data")

    def get_voices(self):
        return list(self.valid_voices)

    def generate_speech(self, text, voice=None, speed=1.0):
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise ValueError("input must be nonempty text of at most 1000 characters")
        voice = voice or self.default_voice
        if voice not in self.valid_voices:
            raise ValueError("Unknown voice")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.5 <= speed <= 2.0:
            raise ValueError("speed must be a number between 0.5 and 2.0")

        # A single shared model is not assumed re-entrant; serialize generation.
        with self._inference_lock:
            samples, sample_rate = self.kokoro.create(text, voice=voice, speed=float(speed), lang="en-us")
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
            raise RuntimeError("Kokoro returned invalid mono audio")
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or not 8000 <= sample_rate <= 96000:
            raise RuntimeError("Kokoro returned invalid sample rate")
        if samples.size > int(sample_rate) * 120:
            raise RuntimeError("Generated audio exceeds 120-second limit")
        return samples, int(sample_rate)
