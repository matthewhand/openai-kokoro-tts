import os
import unittest

from openai_kokoro_tts.tts_handler import TTSHandler

class TestTTSHandler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Setup environment for testing."""
        cls.ci_mode = os.getenv("CI", "false").lower() in ("true", "1", "yes")
        cls.gpu_available = torch.cuda.is_available() if not cls.ci_mode else False
        cls.backend = "onnx" if not cls.gpu_available else "torch"
        cls.handler = TTSHandler(backend=cls.backend)

    def test_generate_onnx(self):
        """Test speech generation using ONNX backend."""
        if self.backend != "onnx":
            self.skipTest("Skipping ONNX test in GPU mode.")
        text = "This is a test of the ONNX backend."
        output = self.handler.generate_speech(text)
        self.assertTrue(output.endswith(".mp3"))

    def test_generate_torch(self):
        """Test speech generation using Torch backend."""
        if self.backend != "torch":
            self.skipTest("Skipping Torch test in ONNX mode.")
        text = "This is a test of the Torch backend."
        output = self.handler.generate_speech(text)
        self.assertTrue(output.endswith(".mp3"))

if __name__ == "__main__":
    unittest.main()
