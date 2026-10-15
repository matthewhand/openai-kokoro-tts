"""Deterministic contention tests for bounded inference admission.

Synthetic inference only (threading.Event gates, no model, no sleeps used for
ordering). ``Barrier``/``Event`` make the interleaving exact; timing is only an
upper bound on how long a refused or timed-out request may take.
"""
import os
import threading
import time
import unittest
from pathlib import Path
import tempfile

import numpy as np

from openai_kokoro_tts.admission import InferenceGate
from openai_kokoro_tts.errors import ConfigError, ServerBusyError
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler


class BlockingKokoro:
    """create() signals entry, then blocks until released."""

    def __init__(self, model, voices):
        self.entered = threading.Semaphore(0)
        self.release = threading.Event()
        self.active = 0
        self.high_watermark = 0
        self.calls = 0
        self._lock = threading.Lock()
        self.fail_next = False

    def get_voices(self):
        return ["af_bella"]

    def create(self, text, voice, speed, lang):
        with self._lock:
            self.active += 1
            self.calls += 1
            self.high_watermark = max(self.high_watermark, self.active)
            fail = self.fail_next
            self.fail_next = False
        try:
            self.entered.release()
            self.release.wait(10)
            if fail:
                raise RuntimeError("synthetic backend failure")
            return np.array([0.0, 0.2, -0.2, 0.0], dtype=np.float32), 24000
        finally:
            with self._lock:
                self.active -= 1


class GateConfigTests(unittest.TestCase):
    def test_defaults(self):
        gate = InferenceGate.from_env({})
        self.assertEqual((gate.max_waiting, gate.wait_timeout_s), (1, 10.0))

    def test_env_values(self):
        gate = InferenceGate.from_env({"INFERENCE_MAX_WAITING": " 3 ", "INFERENCE_QUEUE_TIMEOUT_S": "2.5"})
        self.assertEqual((gate.max_waiting, gate.wait_timeout_s), (3, 2.5))

    def test_malformed_values_abort(self):
        for env in (
            {"INFERENCE_MAX_WAITING": "many"}, {"INFERENCE_MAX_WAITING": "-1"}, {"INFERENCE_MAX_WAITING": ""},
            {"INFERENCE_MAX_WAITING": "1.5"},
            {"INFERENCE_QUEUE_TIMEOUT_S": "soon"}, {"INFERENCE_QUEUE_TIMEOUT_S": "0"},
            {"INFERENCE_QUEUE_TIMEOUT_S": "-3"}, {"INFERENCE_QUEUE_TIMEOUT_S": "nan"},
            {"INFERENCE_QUEUE_TIMEOUT_S": "9999"},
        ):
            with self.subTest(env=env), self.assertRaises(ConfigError):
                InferenceGate.from_env(env)


class GateContentionTests(unittest.TestCase):
    def test_free_slot_is_admitted_and_released(self):
        gate = InferenceGate(0, 1)
        for _ in range(3):
            with gate.admit():
                pass
        self.assertEqual(gate.waiting, 0)

    def test_busy_refused_immediately_when_no_waiting_allowed(self):
        gate = InferenceGate(0, 5)
        with gate.admit():
            start = time.monotonic()
            with self.assertRaises(ServerBusyError):
                with gate.admit():
                    self.fail("must not be admitted")
            self.assertLess(time.monotonic() - start, 1.0)

    def test_wait_timeout_is_bounded(self):
        gate = InferenceGate(1, 0.15)
        with gate.admit():
            start = time.monotonic()
            with self.assertRaises(ServerBusyError):
                with gate.admit():
                    self.fail("must not be admitted")
            elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.1)
        self.assertLess(elapsed, 3.0)
        self.assertEqual(gate.waiting, 0)

    def test_slot_released_when_body_raises(self):
        gate = InferenceGate(0, 1)
        with self.assertRaises(RuntimeError):
            with gate.admit():
                raise RuntimeError("synthetic")
        with gate.admit():
            pass


class HandlerContentionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        model = os.path.join(folder.name, "m.onnx")
        voices = os.path.join(folder.name, "v.json")
        Path(model).touch()
        Path(voices).touch()
        saved = {k: os.environ.get(k) for k in ("ONNX_MODEL_PATH", "VOICES_PATH")}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in saved.items()])
        os.environ["ONNX_MODEL_PATH"] = model
        os.environ["VOICES_PATH"] = voices

    def make(self, max_waiting, timeout=5):
        return OnnxTTSHandler(default_voice="af_bella", kokoro_factory=BlockingKokoro,
                              gate=InferenceGate(max_waiting, timeout))

    def start(self, handler, results, name):
        def run():
            try:
                results[name] = handler.generate_speech("Synthetic")
            except Exception as exc:  # noqa: BLE001 - recorded for assertions
                results[name] = exc
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def test_one_running_one_waiting_third_refused(self):
        handler = self.make(max_waiting=1)
        kokoro = handler.kokoro
        results = {}
        first = self.start(handler, results, "first")
        self.assertTrue(kokoro.entered.acquire(timeout=5))          # first is inside inference
        second = self.start(handler, results, "second")
        deadline = time.monotonic() + 5
        while handler.gate.waiting < 1 and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(handler.gate.waiting, 1)                    # second is queued

        with self.assertRaises(ServerBusyError):                     # third: explicit busy
            handler.generate_speech("Synthetic")
        self.assertEqual(kokoro.calls, 1)                            # refused before inference

        kokoro.release.set()
        first.join(5)
        second.join(5)
        self.assertEqual(sorted(k for k, v in results.items() if isinstance(v, tuple)), ["first", "second"])
        self.assertEqual(kokoro.calls, 2)
        self.assertEqual(kokoro.high_watermark, 1)                   # never overlapped
        self.assertEqual(handler.gate.waiting, 0)

    def test_burst_never_overlaps_and_busy_is_the_only_failure(self):
        handler = self.make(max_waiting=2)
        kokoro = handler.kokoro
        kokoro.release.set()                                         # fast synthetic inference
        results = {}
        barrier = threading.Barrier(12)

        def run(i):
            barrier.wait(5)
            try:
                results[i] = handler.generate_speech("Synthetic")
            except Exception as exc:  # noqa: BLE001
                results[i] = exc

        threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(len(results), 12)
        failures = [v for v in results.values() if not isinstance(v, tuple)]
        self.assertTrue(all(isinstance(f, ServerBusyError) for f in failures), failures)
        self.assertGreaterEqual(len(results) - len(failures), 1)
        self.assertEqual(kokoro.high_watermark, 1)
        self.assertEqual(kokoro.calls, len(results) - len(failures))
        self.assertEqual(handler.gate.waiting, 0)

    def test_backend_failure_releases_slot(self):
        handler = self.make(max_waiting=0)
        kokoro = handler.kokoro
        kokoro.release.set()
        kokoro.fail_next = True
        with self.assertRaises(RuntimeError):
            handler.generate_speech("Synthetic")
        audio, rate = handler.generate_speech("Synthetic")          # slot free again
        self.assertEqual(rate, 24000)

    def test_waiter_times_out_while_inference_keeps_running(self):
        handler = self.make(max_waiting=1, timeout=0.2)
        kokoro = handler.kokoro
        results = {}
        first = self.start(handler, results, "first")
        self.assertTrue(kokoro.entered.acquire(timeout=5))
        start = time.monotonic()
        with self.assertRaises(ServerBusyError):
            handler.generate_speech("Synthetic")
        self.assertLess(time.monotonic() - start, 3.0)
        # The timeout never interrupted the running inference.
        self.assertEqual(kokoro.active, 1)
        kokoro.release.set()
        first.join(5)
        self.assertIsInstance(results["first"], tuple)


if __name__ == "__main__":
    unittest.main()
