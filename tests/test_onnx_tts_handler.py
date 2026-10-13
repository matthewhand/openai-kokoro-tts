"""Synthetic CPU contract tests; no model, network, container or hosted CI."""
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
import wave

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


# Minimal HTTP shim; deliberately not a live Flask integration test.
flask = types.ModuleType("flask")
class FakeRequest:
    is_json = True
    data = {}
    headers = {}
    def get_json(self, silent=True):
        return self.data
flask.request = FakeRequest()
flask.jsonify = lambda value: value
flask.send_file = lambda stream, **kw: {"audio": stream.getvalue(), **kw}
class FakeFlask:
    def __init__(self, name):
        self.routes = {}
    def route(self, path, methods):
        def decorator(func):
            self.routes[path] = func
            return func
        return decorator
flask.Flask = FakeFlask
# Use patch.dict rather than silently assuming Flask is installed locally.
from unittest.mock import patch
dot_env = types.ModuleType("dotenv")
dot_env.load_dotenv = lambda: None
with patch.dict(sys.modules, {"flask": flask, "dotenv": dot_env}):
    with patch.dict(os.environ, {"API_KEY": "synthetic-test-only", "REQUIRE_API_KEY": "true"}):
        from openai_kokoro_tts.server import create_app
        # The module-local utils decorator preserves the synthetic configuration.


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(handler=types.SimpleNamespace(
            get_voices=lambda: ["af_bella", "af_sky"],
            generate_speech=lambda *a, **kw: (np.array([0.0, .5], dtype=np.float32), 24000)))
        flask.request.headers = {"Authorization": "Bearer synthetic-test-only"}
        flask.request.is_json = True
        flask.request.data = {"input": "Synthetic test", "response_format": "wav"}

    def test_speech_wav_response(self):
        value = self.app.routes["/v1/audio/speech"]()
        self.assertEqual(value["mimetype"], "audio/wav")
        self.assertEqual(value["download_name"], "speech.wav")
        self.assertTrue(value["audio"].startswith(b"RIFF"))

    def test_models_response(self):
        value = self.app.routes["/v1/models"]()
        self.assertEqual(value["object"], "list")
        self.assertEqual(value["data"][0]["id"], "af_bella")
        self.assertEqual(value["models"], ["af_bella", "af_sky"])

    def test_auth_both_routes(self):
        for path in ("/v1/models", "/v1/audio/speech"):
            with self.subTest(path=path):
                flask.request.headers = {}
                data, code = self.app.routes[path]()
                self.assertEqual((code, data["error"]), (401, "Unauthorized"))
                flask.request.headers = {"Authorization": "Bearer synthetic-test-only"}

    def test_bad_request_validation(self):
        for data in ([], None, {"input": ""}, {"input": "a" * 1001}, {"input": "ok", "speed": True}, {"input": "ok", "response_format": "aac"}):
            with self.subTest(data=str(data)[:20]):
                flask.request.data = data
                _, code = self.app.routes["/v1/audio/speech"]()
                self.assertEqual(code, 400)

    def test_wrong_content_type(self):
        flask.request.is_json = False
        _, code = self.app.routes["/v1/audio/speech"]()
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
