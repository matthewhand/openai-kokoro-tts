import os
import unittest
from unittest.mock import patch
from openai_kokoro_tts.tts_handler import TTSHandler
import torch

class TestTTSHandler(unittest.TestCase):
    @patch.dict(os.environ, {"DEFAULT_VOICE": "af_bella"})  # Mock environment variable
    def setUp(self):
        """Set up TTSHandler for testing."""
        self.mock_voice_dir = "voices"
        os.makedirs(self.mock_voice_dir, exist_ok=True)

        # Adjust the dummy voicepack size to match or exceed tokenized text length
        dummy_voice_size = 100  # Large enough for typical test cases
        dummy_voice = torch.rand(dummy_voice_size)  # Create a random tensor
        torch.save(dummy_voice, os.path.join(self.mock_voice_dir, "af_bella.pt"))
        torch.save(dummy_voice, os.path.join(self.mock_voice_dir, "af_sarah.pt"))

        self.tts_handler = TTSHandler()

    def tearDown(self):
        """Clean up after tests."""
        # Remove the mock voices directory
        for root, dirs, files in os.walk(self.mock_voice_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.mock_voice_dir)

    def test_default_voice(self):
        """Test that the default voice is set correctly from the environment."""
        self.assertEqual(self.tts_handler.default_voice, "af_bella")

    def test_generate_speech_valid(self):
        """Test speech generation with valid input."""
        text = "Hello, this is a test of the openai kokoro tts application."
        voice = "af_bella"
        response_format = "mp3"

        try:
            output_file = self.tts_handler.generate_speech(text, voice, response_format)
            self.assertTrue(output_file.endswith(".mp3"))
            os.remove(output_file)  # Clean up generated file
        except Exception as e:
            self.fail(f"generate_speech raised an exception: {e}")

