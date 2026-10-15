"""Real Flask request-boundary tests with synthetic, non-model audio.

No network, model weights, Docker, inferencing, or hosted CI.
"""
import io
import os
import subprocess
import sys
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import numpy as np

# Auth is captured by utils at import time; force a synthetic value for this
# isolated test process before the server module is imported.
with patch.dict(os.environ, {"API_KEY": "synthetic-fixture-only", "REQUIRE_API_KEY": "true"}):
    from openai_kokoro_tts.server import create_app


class FakeHandler:
    default_voice = "af_bella"

    def get_voices(self):
        return ["af_bella", "af_sky"]

    def generate_speech(self, text, voice=None, speed=1.0):
        if voice and voice not in self.get_voices():
            raise ValueError("Unknown voice")
        # Distinct synthetic samples expose cross-request result reuse.
        last = text.rsplit(maxsplit=1)[-1]
        amplitude = (int(last) + 1) / 100 if last.isdecimal() else .25
        return np.array([0, amplitude, -.25, 0], dtype=np.float32), 24000


class FlaskIntegrationTests(unittest.TestCase):
    def setUp(self):
        app = create_app(handler=FakeHandler())
        app.config["TESTING"] = True
        self.app = app
        self.client = app.test_client()
        self.auth = {"Authorization": "Bearer synthetic-fixture-only"}

    def post(self, payload, headers=None):
        return self.client.post("/v1/audio/speech", json=payload, headers=self.auth if headers is None else headers)

    def test_speech_is_real_wav_response(self):
        response = self.post({"input": "Synthetic greeting", "response_format": "wav"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/wav")
        self.assertIn("speech.wav", response.headers["Content-Disposition"])
        with wave.open(io.BytesIO(response.data), "rb") as reader:
            self.assertEqual(reader.getframerate(), 24000)
            self.assertEqual(reader.getnchannels(), 1)
            self.assertEqual(reader.getnframes(), 4)

    def test_default_mp3_is_encoded(self):
        response = self.post({"input": "Synthetic greeting"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertIn("speech.mp3", response.headers["Content-Disposition"])
        self.assertTrue(response.data.startswith(b"ID3"))

    def test_models_shape_and_auth(self):
        response = self.client.get("/v1/models", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["models"], ["af_bella", "af_sky"])
        self.assertEqual(response.json["object"], "list")
        self.assertEqual(response.json["data"][0]["id"], "af_bella")
        for path in ("/v1/models", "/v1/audio/speech"):
            with self.subTest(path=path):
                response = self.client.get(path) if path.endswith("models") else self.client.post(path, json={"input": "hello"})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json["error"], "Unauthorized")

    def test_missing_key_fails_closed_at_import(self):
        for placeholder in ("", "   ", "your_api_key_here", "change_me", "default"):
            with self.subTest(key=placeholder):
                env = dict(os.environ, API_KEY=placeholder, REQUIRE_API_KEY="true")
                result = subprocess.run([sys.executable, "-B", "-c", "import openai_kokoro_tts.utils"],
                                        env=env, capture_output=True, text=True, timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Set a non-default API_KEY", result.stderr)

    def test_wrong_token_cannot_generate(self):
        response = self.post({"input": "hello"}, headers={"Authorization": "Bearer not-the-key"})
        self.assertEqual(response.status_code, 401)

    def test_bad_payload(self):
        for obj in (
            [], None, "string", 123, {}, {"input": ""}, {"input": "   "}, {"input": "x"*1001},
            {"input": 123}, {"input": ["hello"]},
            {"input": "hello", "voice": 3}, {"input": "hello", "voice": ""},
            {"input": "hello", "voice": "   "}, {"input": "hello", "voice": ["af_bella"]},
            {"input": "hello", "voice": "bogus"},
            {"input": "hello", "speed": True}, {"input": "hello", "speed": False},
            {"input": "hello", "speed": "fast"}, {"input": "hello", "speed": float("nan")},
            {"input": "hello", "speed": float("inf")}, {"input": "hello", "speed": 0.1},
            {"input": "hello", "speed": 2.5},
            {"input": "hello", "response_format": "aac"},
            {"input": "hello", "response_format": ["wav"]},
            {"input": "hello", "response_format": {"type": "wav"}},
            {"input": "hello", "response_format": 123},
        ):
            with self.subTest(payload=str(obj)[:40]):
                response = self.post(obj)
                self.assertEqual(response.status_code, 400)

    def test_wrong_media_type_or_bad_json(self):
        self.assertEqual(self.client.post("/v1/audio/speech", data=b"text", content_type="text/plain", headers=self.auth).status_code, 400)
        self.assertEqual(self.client.post("/v1/audio/speech", data=b"{oops", content_type="application/json", headers=self.auth).status_code, 400)

    def test_large_body_rejected_before_parsing(self):
        response = self.client.post("/v1/audio/speech", data=b" "*20000,
                                    content_type="application/json", headers=self.auth)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["error"], "Request body too large")

    def test_generator_error_does_not_leak_text(self):
        class FailingHandler(FakeHandler):
            def generate_speech(self, *args, **kwargs):
                raise RuntimeError("private synthetic secret")
        app = create_app(handler=FailingHandler())
        app.config["TESTING"] = True
        with self.assertLogs("openai_kokoro_tts.server", level="ERROR") as logs:
            response = app.test_client().post("/v1/audio/speech", json={"input": "test"}, headers=self.auth)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"private synthetic secret", response.data)
        self.assertNotIn("private synthetic secret", " ".join(logs.output))

    def test_concurrent_clients_have_separate_wav_responses(self):
        def task(i):
            with self.app.test_client() as client:
                response = client.post("/v1/audio/speech",
                    json={"input": "hello " + str(i), "response_format": "wav"}, headers=self.auth)
                return response.status_code, response.data
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(task, range(12)))
        self.assertTrue(all(status == 200 and data.startswith(b"RIFF") for status, data in responses))
        self.assertEqual(len({data for _, data in responses}), len(responses))
    def test_missing_assets_and_initialization_failures(self):
        with patch.dict(os.environ, {"ONNX_MODEL_PATH": "/nonexistent/path/kokoro.onnx"}):
            app = create_app(handler=None)
            app.config["TESTING"] = True
            client = app.test_client()

            # Speech returns 500 when assets missing
            resp_speech = client.post("/v1/audio/speech", json={"input": "test"}, headers=self.auth)
            self.assertEqual(resp_speech.status_code, 500)
            self.assertEqual(resp_speech.json["error"], "Model assets not found")

            # Models route returns 503 when assets missing
            resp_models = client.get("/v1/models", headers=self.auth)
            self.assertEqual(resp_models.status_code, 503)
            self.assertEqual(resp_models.json["error"], "Model assets not found")


if __name__ == "__main__":
    unittest.main()
