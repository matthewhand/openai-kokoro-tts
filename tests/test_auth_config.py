"""Strict REQUIRE_API_KEY / API_KEY startup configuration. No model, no network."""
import os
import subprocess
import sys
import unittest

from unittest.mock import patch

from openai_kokoro_tts.errors import ConfigError

GOOD_KEY = "synthetic-fixture-only"

# utils validates auth at import; give this process a synthetic valid config.
with patch.dict(os.environ, {"API_KEY": GOOD_KEY, "REQUIRE_API_KEY": "true"}):
    from openai_kokoro_tts.utils import (
        getenv_bool,
        is_placeholder_key,
        load_auth_config,
        parse_bool,
    )


def import_utils(**env):
    """Import utils in a clean interpreter with exactly this auth environment."""
    base = {k: v for k, v in os.environ.items() if k not in ("API_KEY", "REQUIRE_API_KEY")}
    base.update(env)
    return subprocess.run([sys.executable, "-B", "-c", "import openai_kokoro_tts.utils as u; print(u.REQUIRE_API_KEY)"],
                          env=base, capture_output=True, text=True, timeout=20, check=False)


class ParseBoolTests(unittest.TestCase):
    def test_recognised_values(self):
        for raw, want in (("true", True), ("TRUE", True), (" True ", True),
                          ("false", False), ("FALSE", False), (" false\t", False)):
            with self.subTest(raw=raw):
                self.assertIs(parse_bool("X", raw), want)

    def test_everything_else_is_an_error(self):
        for raw in ("flase", "ture", "", " ", "0", "1", "yes", "no", "y", "n", "t", "f", "off", "on", "None", "disable"):
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                parse_bool("REQUIRE_API_KEY", raw)

    def test_getenv_bool_unset_uses_default_and_set_is_strict(self):
        name = "KOKORO_TEST_UNSET_FLAG"
        os.environ.pop(name, None)
        self.assertIs(getenv_bool(name, True), True)
        self.assertIs(getenv_bool(name, False), False)
        os.environ[name] = "flase"
        self.addCleanup(os.environ.pop, name, None)
        with self.assertRaises(ConfigError):
            getenv_bool(name, False)


class LoadAuthConfigTests(unittest.TestCase):
    def test_default_is_authentication_enabled(self):
        self.assertEqual(load_auth_config({"API_KEY": GOOD_KEY}), (True, GOOD_KEY))

    def test_unset_require_with_missing_key_fails(self):
        with self.assertRaises(ConfigError):
            load_auth_config({})

    def test_explicit_false_allows_missing_key(self):
        self.assertEqual(load_auth_config({"REQUIRE_API_KEY": "false"}), (False, ""))

    def test_malformed_flag_aborts_even_with_good_key(self):
        for raw in ("flase", "", "0", "no", "off"):
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                load_auth_config({"REQUIRE_API_KEY": raw, "API_KEY": GOOD_KEY})

    def test_placeholder_and_missing_keys_rejected(self):
        for key in ("", "   ", "your_api_key_here", "YOUR-API-KEY-HERE", "change_me", "change-me", "changeme",
                    "default", "Replace Me", "placeholder", "secret", "password", "none"):
            with self.subTest(key=key), self.assertRaises(ConfigError):
                load_auth_config({"REQUIRE_API_KEY": "true", "API_KEY": key})
            self.assertTrue(is_placeholder_key(key))

    def test_real_looking_key_accepted(self):
        self.assertFalse(is_placeholder_key("k3y-9f2a7c41d8e65b03"))


class StartupAbortTests(unittest.TestCase):
    """The module-level path that actually runs at server start."""

    def test_typo_in_require_api_key_aborts_startup(self):
        result = import_utils(REQUIRE_API_KEY="flase", API_KEY=GOOD_KEY)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REQUIRE_API_KEY must be 'true' or 'false'", result.stderr)

    def test_server_module_refuses_to_import_with_typo(self):
        base = {k: v for k, v in os.environ.items() if k not in ("API_KEY", "REQUIRE_API_KEY")}
        base.update(REQUIRE_API_KEY="flase", API_KEY=GOOD_KEY)
        result = subprocess.run([sys.executable, "-B", "-c", "import openai_kokoro_tts.server"],
                                env=base, capture_output=True, text=True, timeout=30, check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_default_requires_key(self):
        result = import_utils()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set a non-default API_KEY", result.stderr)

    def test_explicit_false_starts_with_warning(self):
        result = import_utils(REQUIRE_API_KEY="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_valid_true_starts(self):
        result = import_utils(REQUIRE_API_KEY="TRUE", API_KEY=GOOD_KEY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
