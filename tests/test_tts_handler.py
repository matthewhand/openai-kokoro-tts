import os
import unittest
from unittest.mock import MagicMock, patch
from openai_kokoro_tts.tts_handler import TTSHandler
import numpy as np

class TestTTSHandler(unittest.TestCase):
    @patch.dict(os.environ, {"DEFAULT_VOICE": "af_bella"})  # Mock environment variable
    def setUp(self):
        """Set up TTSHandler for testing."""
        self.tts_handler = TTSHandler()
        # Mock the model.run method to return fake audio data
        self.tts_handler.model = MagicMock()
        # Simulate model output as a numpy array of float32
        self.tts_handler.model.run.return_value = [np.random.randn(24000).astype(np.float32)]

    def test_default_voice(self):
        """Test that the default voice is set correctly from the environment."""
        self.assertEqual(self.tts_handler.default_voice, "af_bella", "Default voice should match the environment variable")

    def test_generate_speech_valid(self):
        """Test speech generation with valid input."""
        text = "Hello, this is a test."
        voice = "af_bella"
        response_format = "mp3"

        try:
            output_file = self.tts_handler.generate_speech(text, voice, response_format)
            self.assertTrue(output_file.endswith(".mp3"), "Generated file should be an MP3")
            # Additionally, check if the file exists
            self.assertTrue(os.path.exists(output_file), f"Output file {output_file} should exist")
            # Clean up the generated file after test
            os.remove(output_file)
        except Exception as e:
            self.fail(f"generate_speech raised an exception: {e}")

    def test_generate_speech_invalid_voice(self):
        """Test fallback to the default voice when an invalid voice is provided."""
        text = "Hello, this is a fallback test."
        invalid_voice = "unknown_voice"
        response_format = "mp3"

        try:
            output_file = self.tts_handler.generate_speech(text, invalid_voice, response_format)
            self.assertTrue(output_file.endswith(".mp3"), "Generated file should still be an MP3")
            # Additionally, check if the file exists
            self.assertTrue(os.path.exists(output_file), f"Output file {output_file} should exist")
            # Clean up the generated file after test
            os.remove(output_file)
        except Exception as e:
            self.fail(f"generate_speech raised an exception for invalid voice: {e}")

            

if __name__ == "__main__":
    unittest.main()
