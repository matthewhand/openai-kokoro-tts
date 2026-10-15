"""Real HTTP sockets + the production WSGI server (waitress) + synthetic inference.

Proves the explicit busy response is reachable over HTTP: one request is inside
(blocked, non-interruptible) inference, one waits, the rest get 503 immediately.
No model, no real inference.
"""
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import numpy as np

KEY = "synthetic-fixture-only"
with patch.dict(os.environ, {"API_KEY": KEY, "REQUIRE_API_KEY": "true"}):
    from openai_kokoro_tts.admission import InferenceGate
    from openai_kokoro_tts.server import create_app

from waitress import create_server


class BlockingHandler:
    default_voice = "af_bella"

    def __init__(self):
        self.gate = InferenceGate(max_waiting=1, wait_timeout_s=10)
        self.entered = threading.Semaphore(0)
        self.release = threading.Event()
        self.active = 0
        self.high_watermark = 0
        self._lock = threading.Lock()

    def get_voices(self):
        return ["af_bella"]

    def generate_speech(self, text, voice=None, speed=1.0):
        with self.gate.admit():
            with self._lock:
                self.active += 1
                self.high_watermark = max(self.high_watermark, self.active)
            try:
                self.entered.release()
                self.release.wait(15)
                return np.zeros(2400, dtype=np.float32), 24000
            finally:
                with self._lock:
                    self.active -= 1


def post(port, results, key):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/audio/speech",
        data=json.dumps({"input": "hello", "response_format": "wav"}).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            results[key] = (response.status, time.monotonic() - started, dict(response.headers))
    except urllib.error.HTTPError as exc:
        results[key] = (exc.code, time.monotonic() - started, dict(exc.headers))


class ServerContentionTests(unittest.TestCase):
    def setUp(self):
        self.handler = BlockingHandler()
        app = create_app(handler=self.handler)
        self.server = create_server(app, host="127.0.0.1", port=0, threads=4)
        self.port = self.server.effective_port
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.handler.release.set()
        self.server.close()
        self.thread.join(10)

    def test_overflow_gets_503_while_inference_is_blocked(self):
        results = {}
        threads = []

        def launch(key):
            t = threading.Thread(target=post, args=(self.port, results, key), daemon=True)
            t.start()
            threads.append(t)

        launch("running")
        self.assertTrue(self.handler.entered.acquire(timeout=10))     # first is in inference
        launch("waiting")
        deadline = time.monotonic() + 10
        while self.handler.gate.waiting < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.handler.gate.waiting, 1)

        for key in ("busy-1", "busy-2", "busy-3"):
            launch(key)
        deadline = time.monotonic() + 10
        while len([k for k in results if k.startswith("busy")]) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)

        for key in ("busy-1", "busy-2", "busy-3"):
            status, elapsed, headers = results[key]
            self.assertEqual(status, 503, key)
            self.assertLess(elapsed, 5.0, "busy must be prompt, not queued behind inference")
            self.assertEqual(headers.get("Retry-After"), "2")
        self.assertNotIn("running", results)                          # still blocked in native-like call

        self.handler.release.set()
        for t in threads:
            t.join(15)
        self.assertEqual(results["running"][0], 200)
        self.assertEqual(results["waiting"][0], 200)
        self.assertEqual(self.handler.high_watermark, 1)


if __name__ == "__main__":
    unittest.main()
