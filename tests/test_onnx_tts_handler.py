import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler


class TestOnnxTTSHandler(unittest.TestCase):
    @classmethod
    @patch.dict(os.environ, {
        "ONNX_MODEL_PATH": "models/kokoro/kokoro-v0_19.onnx",
        "DEFAULT_VOICE": "af_sky"
    })
    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession", autospec=True)
    def setUpClass(cls, mock_inference_session):
        """
        Initialize the OnnxTTSHandler for testing with mocked dependencies.
        """
        cls.mock_session = MagicMock()
        cls.mock_session.run.return_value = [np.zeros((16000,), dtype=np.float32)]
        mock_inference_session.return_value = cls.mock_session
        cls.handler = OnnxTTSHandler()

    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession")
    def test_default_voice(self, mock_inference_session):
        """
        Test that the default voice is set correctly.
        """
        self.assertEqual(self.handler.default_voice, "af_sky")

    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession")
    def test_generate_speech_valid(self, mock_inference_session):
        """
        Test speech generation with valid input.
        """
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = [np.zeros((16000,), dtype=np.float32)]
        mock_inference_session.return_value = mock_session_instance

        text = "Hello, this is a test message."
        output_file = self.handler.generate_speech(text, response_format="mp3")  # Specify mp3 explicitly
        self.assertTrue(output_file.endswith(".mp3"))
        self.assertTrue(os.path.isfile(output_file))
        os.remove(output_file)

    @patch("openai_kokoro_tts.onnx_tts_handler.ort.InferenceSession")
    def test_generate_speech_invalid_voice(self, mock_inference_session):
        """
        Test speech generation with an invalid voice.
        """
        mock_session_instance = MagicMock()
        mock_session_instance.run.return_value = [np.zeros((16000,), dtype=np.float32)]
        mock_inference_session.return_value = mock_session_instance

        text = "Testing with an invalid voice."
        voice = "invalid_voice"
        with self.assertRaises(RuntimeError):
            self.handler.generate_speech(text, voice=voice)

    def test_generate_speech_empty_text(self):
        """
        Test that a ValueError is raised for empty input text.
        """
        with self.assertRaises(ValueError):
            self.handler.generate_speech("")

    def test_missing_model_or_voices_files(self):
        """
        Test that a FileNotFoundError is raised if the ONNX model is missing.
        """
        with patch.dict(os.environ, {"ONNX_MODEL_PATH": "invalid_path.onnx"}):
            with self.assertRaises(FileNotFoundError):
                OnnxTTSHandler()


if __name__ == "__main__":
    unittest.main()
