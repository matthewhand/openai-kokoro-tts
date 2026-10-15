"""Exception types that decide how a failure is reported to HTTP clients.

Only :class:`RequestValidationError` carries text that is safe to show a client:
its message must be a fixed, non-interpolated string. Every other exception is a
backend failure and is reported with a generic message; details go to logs as an
exception *type name* only, never as request text, paths or keys.
"""


class ConfigError(ValueError):
    """Invalid startup configuration. Aborts startup; never reaches a client."""


class RequestValidationError(ValueError):
    """The request itself is invalid (HTTP 400). ``str(exc)`` is public."""


class ServerBusyError(RuntimeError):
    """Inference admission was refused or timed out (HTTP 503)."""
