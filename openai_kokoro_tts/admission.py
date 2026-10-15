"""Bounded admission in front of a single, non-interruptible inference slot.

One model instance runs one inference at a time. A plain lock would let any
number of requests pile up behind it, each holding a worker and a client
connection for as long as the queue is long. This gate bounds both:

* at most ``max_waiting`` requests may wait for the running one; the next is
  refused immediately with :class:`ServerBusyError`;
* a waiting request gives up after ``wait_timeout_s``.

The timeout bounds WAITING only. Once a request holds the slot, native ONNX
Runtime execution cannot be cancelled from Python, so a running inference is
bounded by input limits (<= 1000 characters, <= 120 s of audio), not by a clock.
"""
import contextlib
import os
import threading

from openai_kokoro_tts.errors import ConfigError, ServerBusyError

DEFAULT_MAX_WAITING = 1
DEFAULT_WAIT_TIMEOUT_S = 10.0


class InferenceGate:
    def __init__(self, max_waiting=DEFAULT_MAX_WAITING, wait_timeout_s=DEFAULT_WAIT_TIMEOUT_S):
        if isinstance(max_waiting, bool) or not isinstance(max_waiting, int) or max_waiting < 0:
            raise ConfigError("max_waiting must be an integer >= 0")
        if isinstance(wait_timeout_s, bool) or not isinstance(wait_timeout_s, (int, float)) or not 0 < wait_timeout_s <= 300:
            raise ConfigError("wait_timeout_s must be a number in (0, 300]")
        self.max_waiting = max_waiting
        self.wait_timeout_s = float(wait_timeout_s)
        self._slot = threading.Lock()
        self._state = threading.Lock()
        self._waiting = 0

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        raw_wait = env.get("INFERENCE_MAX_WAITING")
        raw_timeout = env.get("INFERENCE_QUEUE_TIMEOUT_S")
        try:
            max_waiting = DEFAULT_MAX_WAITING if raw_wait is None else int(raw_wait.strip())
        except ValueError:
            raise ConfigError("INFERENCE_MAX_WAITING must be an integer >= 0") from None
        try:
            timeout = DEFAULT_WAIT_TIMEOUT_S if raw_timeout is None else float(raw_timeout.strip())
        except ValueError:
            raise ConfigError("INFERENCE_QUEUE_TIMEOUT_S must be a number in (0, 300]") from None
        return cls(max_waiting, timeout)

    @property
    def waiting(self):
        with self._state:
            return self._waiting

    @contextlib.contextmanager
    def admit(self):
        """Hold the inference slot, or raise :class:`ServerBusyError`."""
        # Fast path: slot free, no queueing.
        if self._slot.acquire(blocking=False):
            acquired = True
        else:
            with self._state:
                if self._waiting >= self.max_waiting:
                    raise ServerBusyError("inference busy")
                self._waiting += 1
            try:
                acquired = self._slot.acquire(timeout=self.wait_timeout_s)
            finally:
                with self._state:
                    self._waiting -= 1
            if not acquired:
                raise ServerBusyError("inference wait timed out")
        try:
            yield
        finally:
            self._slot.release()
