import unittest
from unittest.mock import patch, MagicMock
from openai_kokoro_tts.transformers_tts_handler import TransformersTTSHandler

class TestTransformersTTSHandler(unittest.TestCase):
    """Unit tests for TransformersTTSHandler."""

    @patch("openai_kokoro_tts.transformers_tts_handler.AutoModelForSeq2SeqLM")
    @patch("openai_kokoro_tts.transformers_tts_handler.AutoTokenizer")
    @patch("openai_kokoro_tts.transformers_tts_handler.pipeline")
    def test_initialization(self, mock_pipeline, mock_tokenizer, mock_model):
        """Test that the handler initializes correctly."""
        mock_pipeline.return_value = MagicMock()
        mock_tokenizer.from_pretrained.return_value = MagicMock()
        mock_model.from_pretrained.return_value = MagicMock()

        handler = TransformersTTSHandler()
        self.assertIsNotNone(handler.pipeline)
        self.assertEqual(handler.default_voice, "af_bella")

    @patch("openai_kokoro_tts.transformers_tts_handler.pipeline")
    def test_generate_speech(self, mock_pipeline):
        """Test speech generation functionality."""
        mock_pipeline.return_value = MagicMock()
        handler = TransformersTTSHandler()

        text = "Hello, this is a test."
        mock_pipeline.return_value.__call__.return_value = b"mock_audio_data"

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            output_file = handler.generate_speech(text, voice="af_bella")
            self.assertEqual(output_file, "output.mp3")
            mock_file().write.assert_called_once()

    def test_generate_speech_empty_text(self):
        """Test speech generation with empty input text."""
        handler = TransformersTTSHandler()
        with self.assertRaises(ValueError):
            handler.generate_speech("")

if __name__ == "__main__":
    unittest.main()
