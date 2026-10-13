"""Synthetic CPU contract tests; no model, network, container or hosted CI."""
import io
import os
import subprocess
import wave
from pathlib import Path
import tempfile
import threading
import time
import unittest

import numpy as np

from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler
from openai_kokoro_tts.audio_encoding import encode_audio


class FakeKokoro:
    def __init__(self, model, voices):
        self.active = 0
        self.high_watermark = 0

    def get_voices(self):
        return ["af_bella", "af_sky"]

    def create(self, text, voice, speed, lang):
        self.active += 1
        self.high_watermark = max(self.active, self.high_watermark)
        assert lang == "en-us"
        assert voice in self.get_voices()
        try:
            # Release the GIL so a missing inference lock causes real overlap.
            time.sleep(0.008)
            return np.array([0.0, 0.25, -0.25, 0.0], dtype=np.float32), 24000
        finally:
            self.active -= 1


class HandlerTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.model = os.path.join(folder.name, "model.onnx")
        self.voices = os.path.join(folder.name, "voices.bin")
        Path(self.model).touch()
        Path(self.voices).touch()
        previous = {k: os.environ.get(k) for k in ("ONNX_MODEL_PATH", "VOICES_PATH")}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in previous.items()])
        os.environ["ONNX_MODEL_PATH"] = self.model
        os.environ["VOICES_PATH"] = self.voices
        self.handler = OnnxTTSHandler(kokoro_factory=FakeKokoro)

    def test_uses_kokoro_create(self):
        audio, rate = self.handler.generate_speech("Synthetic", "af_sky", 1.25)
        self.assertEqual((audio.shape, rate), ((4,), 24000))
        self.assertEqual(self.handler.get_voices(), ["af_bella", "af_sky"])

    def test_invalid_voice_and_speed(self):
        for voice, speed in [("bad", 1), (None, float("nan")), (None, True), (None, .1), (None, 2.1)]:
            with self.subTest(voice=voice, speed=speed), self.assertRaises(ValueError):
                self.handler.generate_speech("test", voice, speed)

    def test_bounded_input(self):
        for value in (None, 9, "", "  ", "a" * 1001):
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                self.handler.generate_speech(value)

    def test_no_saved_audio_file(self):
        self.handler.generate_speech("Synthetic")
        self.assertFalse(any(Path(self.model).parent.glob("*.wav")))

    def test_missing_voice_assets(self):
        os.remove(self.voices)
        with self.assertRaises(FileNotFoundError):
            OnnxTTSHandler(kokoro_factory=FakeKokoro)

    def test_nonfinite_audio_rejected(self):
        self.handler.kokoro.create = lambda *a, **kw: (np.array([float("nan")]), 24000)
        with self.assertRaises(RuntimeError):
            self.handler.generate_speech("bad")

    def test_calls_share_one_lock(self):
        errors = []
        def worker():
            try:
                self.handler.generate_speech("Synthetic")
            except Exception as exc:
                errors.append(exc)
        workers = [threading.Thread(target=worker) for _ in range(8)]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.handler.kokoro.high_watermark, 1)


class EncodingTests(unittest.TestCase):
    def test_wav_header_and_rate(self):
        data, mime = encode_audio(np.array([0, .5, -.5], dtype=np.float32), 24000, "wav")
        self.assertEqual(mime, "audio/wav")
        with wave.open(io.BytesIO(data), "rb") as reader:
            self.assertEqual((reader.getnframes(), reader.getframerate(), reader.getnchannels()), (3, 24000, 1))

    def test_invalid_inputs(self):
        for samples, rate, fmt in [([], 24000, "wav"), ([float("inf")], 24000, "wav"), ([0], 16000, "aac"), ([0], 0, "wav")]:
            with self.subTest(fmt=fmt, rate=rate), self.assertRaises(ValueError):
                encode_audio(samples, rate, fmt)

    def test_mp3_synthetic_audio(self):
        # Requires only a local ffmpeg binary, not any inference or model weights.
        data, mime = encode_audio(np.zeros(2400, dtype=np.float32), 24000, "mp3")
        self.assertEqual(mime, "audio/mpeg")
        self.assertTrue(data.startswith(b"ID3"))
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=codec_name,sample_rate,channels", "-of", "default=noprint_wrappers=1",
                                "-i", "pipe:0"], input=data, capture_output=True, timeout=10, check=False)
        self.assertEqual(probe.returncode, 0, probe.stderr.decode(errors="replace"))
        self.assertIn(b"codec_name=mp3", probe.stdout)
        self.assertIn(b"sample_rate=24000", probe.stdout)
        self.assertIn(b"channels=1", probe.stdout)




if __name__ == "__main__":
    unittest.main()
