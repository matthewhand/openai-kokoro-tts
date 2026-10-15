"""HTTP error contract: validation 400, busy 503, backend failure sanitised 5xx.

Synthetic private markers are planted in request text, voices and backend
exception messages; none may appear in any response body or log record.
"""
import logging
import os
import unittest
from unittest.mock import patch

import numpy as np

KEY = "synthetic-fixture-only"
with patch.dict(os.environ, {"API_KEY": KEY, "REQUIRE_API_KEY": "true"}):
    from openai_kokoro_tts.errors import RequestValidationError, ServerBusyError
    from openai_kokoro_tts.server import create_app

PRIVATE_TEXT = "PRIVATE-REQUEST-TEXT-7f3a"
PRIVATE_PATH = r"C:\Users\private-user\models\secret-kokoro.onnx"
PRIVATE_KEY = "sk-private-api-key-marker-91c2"
MARKERS = (PRIVATE_TEXT, "private-user", "secret-kokoro", PRIVATE_KEY, "Traceback")
AUTH = {"Authorization": f"Bearer {KEY}"}


class Handler:
    default_voice = "af_bella"

    def __init__(self, exc=None):
        self.exc = exc

    def get_voices(self):
        return ["af_bella"]

    def generate_speech(self, text, voice=None, speed=1.0):
        if self.exc is not None:
            raise self.exc
        return np.array([0, .2, -.2, 0], dtype=np.float32), 24000


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage() + " " + (str(record.exc_info) if record.exc_info else ""))


class ErrorDisclosureTests(unittest.TestCase):
    def call(self, handler, payload=None, **kw):
        app = create_app(handler=handler)
        app.config["TESTING"] = False  # exercise the real error handlers
        capture = Capture()
        root = logging.getLogger()
        root.addHandler(capture)
        self.addCleanup(root.removeHandler, capture)
        old = root.level
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.setLevel, old)
        payload = payload or {"input": PRIVATE_TEXT, "response_format": "wav"}
        response = app.test_client().post("/v1/audio/speech", json=payload, headers=AUTH, **kw)
        return response, capture

    def assert_clean(self, response, capture):
        body = response.get_data(as_text=True)
        blob = body + " ".join(capture.lines) + " ".join(f"{k}:{v}" for k, v in response.headers)
        for marker in MARKERS:
            self.assertNotIn(marker, blob, marker)

    def test_backend_valueerror_is_not_echoed_and_is_5xx(self):
        for message in (f"bad text {PRIVATE_TEXT}", f"cannot open {PRIVATE_PATH}", f"key {PRIVATE_KEY}"):
            with self.subTest(message=message[:12]):
                response, capture = self.call(Handler(ValueError(message)))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json, {"error": "Speech generation failed"})
                self.assert_clean(response, capture)

    def test_other_backend_exceptions_are_sanitised(self):
        for exc in (RuntimeError(PRIVATE_PATH), OSError(PRIVATE_PATH), KeyError(PRIVATE_TEXT),
                    Exception(PRIVATE_KEY), MemoryError(PRIVATE_TEXT)):
            with self.subTest(exc=type(exc).__name__):
                response, capture = self.call(Handler(exc))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json, {"error": "Speech generation failed"})
                self.assert_clean(response, capture)

    def test_request_validation_error_is_400_with_fixed_public_text(self):
        response, capture = self.call(Handler(RequestValidationError("Unknown voice")))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "Unknown voice"})

    def test_unknown_voice_does_not_echo_the_voice(self):
        response, capture = self.call(Handler(), {"input": "hello", "voice": PRIVATE_TEXT})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "Unknown voice"})
        self.assert_clean(response, capture)

    def test_busy_is_503_with_retry_after_and_no_detail(self):
        response, capture = self.call(Handler(ServerBusyError(PRIVATE_TEXT)))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"error": "Server busy, retry shortly"})
        self.assertEqual(response.headers["Retry-After"], "2")
        self.assert_clean(response, capture)

    def test_response_format_type_confusion_is_400_not_500(self):
        for fmt in (["wav"], {"type": "wav"}, 7, 1.5, True, "WAV", "", "aac", "wav ", ["mp3", "wav"]):
            with self.subTest(fmt=repr(fmt)):
                response, _ = self.call(Handler(), {"input": "hello", "response_format": fmt})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json, {"error": "response_format must be wav or mp3"})

    def test_input_validation_never_echoes_request_text(self):
        for payload in ({"input": PRIVATE_TEXT * 100}, {"input": PRIVATE_TEXT, "speed": PRIVATE_TEXT},
                        {"input": PRIVATE_TEXT, "voice": 5}):
            with self.subTest(keys=sorted(payload)):
                response, capture = self.call(Handler(), payload)
                self.assertEqual(response.status_code, 400)
                self.assert_clean(response, capture)

    def test_unknown_route_and_method_are_json(self):
        client = create_app(handler=Handler()).test_client()
        r404 = client.get("/nope", headers=AUTH)
        r405 = client.get("/v1/audio/speech", headers=AUTH)
        self.assertEqual((r404.status_code, r405.status_code), (404, 405))
        self.assertIn("error", r404.json)
        self.assertIn("error", r405.json)

    def test_model_init_failure_is_sanitised(self):
        app = create_app(handler=None)
        with patch("openai_kokoro_tts.server.OnnxTTSHandler", side_effect=ValueError(PRIVATE_PATH)):
            capture = Capture()
            logging.getLogger().addHandler(capture)
            self.addCleanup(logging.getLogger().removeHandler, capture)
            r = app.test_client().post("/v1/audio/speech", json={"input": "hello"}, headers=AUTH)
            m = app.test_client().get("/v1/models", headers=AUTH)
        self.assertEqual((r.status_code, m.status_code), (500, 503))
        for response in (r, m):
            self.assert_clean(response, capture)


class AuthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(handler=Handler()).test_client()

    def endpoints(self):
        return (("get", "/v1/models", None), ("post", "/v1/audio/speech", {"input": "hello"}))

    def test_wrong_missing_and_malformed_tokens_are_401_on_both_endpoints(self):
        bad = [
            {}, {"Authorization": ""}, {"Authorization": "Bearer "}, {"Authorization": "Bearer wrong"},
            {"Authorization": KEY}, {"Authorization": f"Basic {KEY}"}, {"Authorization": f"bearer {KEY}"},
            {"Authorization": f"Bearer {KEY} "}, {"Authorization": f"Bearer  {KEY}"},
            {"Authorization": f"Bearer {KEY}x"}, {"Authorization": f"Bearer {KEY[:-1]}"},
            {"Authorization": "Bearer caf\u00e9-\u00fc"},           # non-ASCII must not 500
        ]
        for method, path, body in self.endpoints():
            for headers in bad:
                with self.subTest(path=path, auth=headers.get("Authorization", "<none>")[:20]):
                    response = getattr(self.client, method)(path, headers=headers, **({"json": body} if body else {}))
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json, {"error": "Unauthorized"})
                    self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_correct_token_passes_both_endpoints(self):
        self.assertEqual(self.client.get("/v1/models", headers=AUTH).status_code, 200)
        self.assertEqual(self.client.post("/v1/audio/speech", json={"input": "hello", "response_format": "wav"},
                                          headers=AUTH).status_code, 200)

    def test_auth_checked_before_validation_and_model_load(self):
        with patch("openai_kokoro_tts.server.OnnxTTSHandler") as factory:
            client = create_app(handler=None).test_client()
            for method, path, body in self.endpoints():
                getattr(client, method)(path, **({"json": {"input": ""}} if body else {}))
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
