import os
import unittest
from unittest.mock import patch

from openai_kokoro_tts.onnx_providers import (
    CPU_PROVIDER,
    candidate_providers,
    create_with_fallback,
    normalize_provider,
)


class TestOnnxProviders(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_provider("auto"), "auto")
        self.assertEqual(normalize_provider("cpu"), CPU_PROVIDER)
        self.assertEqual(normalize_provider("CUDA"), "CUDAExecutionProvider")
        self.assertEqual(normalize_provider("dml"), "DmlExecutionProvider")
        self.assertEqual(normalize_provider("rocm"), "ROCMExecutionProvider")
        self.assertEqual(normalize_provider("migraphx"), "MIGraphXExecutionProvider")

    @patch("openai_kokoro_tts.onnx_providers.available_providers")
    def test_auto_cpu_only_wheel(self, mock_avail):
        mock_avail.return_value = ["AzureExecutionProvider", CPU_PROVIDER]
        self.assertEqual(candidate_providers("auto"), [CPU_PROVIDER])

    @patch("openai_kokoro_tts.onnx_providers.available_providers")
    def test_auto_prefers_cuda_then_cpu(self, mock_avail):
        mock_avail.return_value = [
            "CUDAExecutionProvider",
            "AzureExecutionProvider",
            CPU_PROVIDER,
        ]
        self.assertEqual(
            candidate_providers("auto"),
            ["CUDAExecutionProvider", CPU_PROVIDER],
        )

    @patch("openai_kokoro_tts.onnx_providers.available_providers")
    def test_auto_directml(self, mock_avail):
        mock_avail.return_value = ["DmlExecutionProvider", CPU_PROVIDER]
        self.assertEqual(
            candidate_providers("auto"),
            ["DmlExecutionProvider", CPU_PROVIDER],
        )

    def test_explicit_cuda_still_falls_back_to_cpu(self):
        self.assertEqual(
            candidate_providers("cuda"),
            ["CUDAExecutionProvider", CPU_PROVIDER],
        )

    def test_explicit_cpu_only(self):
        self.assertEqual(candidate_providers("cpu"), [CPU_PROVIDER])

    def test_create_falls_back_when_first_provider_fails(self):
        calls = []

        def factory():
            provider = os.environ["ONNX_PROVIDER"]
            calls.append(provider)
            if provider == "CUDAExecutionProvider":
                raise RuntimeError("no cuda")
            return f"ok-{provider}"

        with patch(
            "openai_kokoro_tts.onnx_providers.available_providers",
            return_value=["CUDAExecutionProvider", CPU_PROVIDER],
        ):
            instance, chosen = create_with_fallback(factory, requested="auto")
        self.assertEqual(chosen, CPU_PROVIDER)
        self.assertEqual(instance, f"ok-{CPU_PROVIDER}")
        self.assertEqual(calls, ["CUDAExecutionProvider", CPU_PROVIDER])

    def test_create_raises_when_all_fail(self):
        def factory():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError) as ctx:
            create_with_fallback(factory, requested="cpu")
        self.assertIn("Tried:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
