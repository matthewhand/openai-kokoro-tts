"""Authentication configuration, intentionally fail-closed by default."""
import hmac
import os
from functools import wraps

from dotenv import load_dotenv
from flask import jsonify, request

load_dotenv()


def getenv_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ("yes", "y", "true", "1", "t")


REQUIRE_API_KEY = getenv_bool("REQUIRE_API_KEY", True)
API_KEY = os.getenv("API_KEY", "")
if REQUIRE_API_KEY and (not API_KEY or API_KEY == "your_api_key_here"):
    raise ValueError("Set a non-default API_KEY before starting the server")


def require_api_key(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if not REQUIRE_API_KEY:
            return func(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], API_KEY):
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return decorated
