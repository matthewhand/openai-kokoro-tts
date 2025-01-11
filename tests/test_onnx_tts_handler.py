import unittest
from unittest.mock import patch, MagicMock
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler

class TestOnnxTTSHandler(unittest.TestCase):
    """Unit tests for OnnxTTSHandler."""

    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession")
    def test_initialization(self, mock_inference_session):
        """Test that the handler initializes correctly."""
        mock_inference_session.return_value = MagicMock()
        handler = OnnxTTSHandler()
        self.assertIsNotNone(handler.session)
        self.assertEqual(handler.default_voice, "af_bella")

    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession")
    def test_generate_speech(self, mock_inference_session):
        """Test speech generation functionality."""
        mock_session = MagicMock()
        mock_session.run.return_value = [b"mock_audio_data"]
        mock_inference_session.return_value = mock_session

        handler = OnnxTTSHandler()
        text = "Hello, this is a test."

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            output_file = handler.generate_speech(text, voice="af_bella")
            self.assertEqual(output_file, "output.mp3")
            mock_file().write.assert_called_once()

    def test_generate_speech_empty_text(self):
        """Test speech generation with empty input text."""
        handler = OnnxTTSHandler()
        with self.assertRaises(ValueError):
            handler.generate_speech("")

if __name__ == "__main__":
    unittest.main()
