"""Authentication configuration, intentionally fail-closed by default.

``REQUIRE_API_KEY`` accepts exactly ``true`` or ``false`` (case-insensitive,
surrounding whitespace ignored). Unset means ``true``. Anything else, including
an empty string or a typo such as ``flase``, aborts startup instead of silently
disabling authentication.
"""
import hmac
import logging
import os
from functools import wraps

from dotenv import load_dotenv
from flask import jsonify, request

from openai_kokoro_tts.errors import ConfigError

load_dotenv()

log = logging.getLogger(__name__)

PLACEHOLDER_KEYS = frozenset({
    "",
    "your_api_key_here",
    "your_api_key",
    "your_key_here",
    "api_key",
    "apikey",
    "change_me",
    "changeme",
    "replace_me",
    "replaceme",
    "default",
    "placeholder",
    "secret",
    "password",
    "test",
    "none",
    "null",
})


def parse_bool(name, raw):
    """Strict boolean: only ``true`` / ``false`` are recognised."""
    value = (raw or "").strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ConfigError(f"{name} must be 'true' or 'false'")


def getenv_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return parse_bool(name, raw)


def is_placeholder_key(key):
    normalized = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in PLACEHOLDER_KEYS


def load_auth_config(environ=None):
    """Return ``(require_api_key, api_key)`` or raise :class:`ConfigError`."""
    env = os.environ if environ is None else environ
    raw = env.get("REQUIRE_API_KEY")
    require = True if raw is None else parse_bool("REQUIRE_API_KEY", raw)
    api_key = env.get("API_KEY", "")
    if require and is_placeholder_key(api_key):
        raise ConfigError("Set a non-default API_KEY before starting the server")
    return require, api_key


REQUIRE_API_KEY, API_KEY = load_auth_config()
if not REQUIRE_API_KEY:
    log.warning("REQUIRE_API_KEY=false: authentication is DISABLED")


def _token_matches(presented, expected):
    # compare_digest rejects non-ASCII str; compare bytes so a hostile header
    # cannot turn a failed login into a 500.
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def require_api_key(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if not REQUIRE_API_KEY:
            return func(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not _token_matches(auth[7:], API_KEY):
            response = jsonify({"error": "Unauthorized"})
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        return func(*args, **kwargs)
    return decorated
