import os
import logging
import numpy as np
from kokoro_onnx import Kokoro

DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

class TTSHandler:
    def __init__(self):
        """
        Initialize TTSHandler with default voice and load the Kokoro ONNX model.
        """
        logging.info("Initializing TTSHandler.")
        self.default_voice = os.getenv("DEFAULT_VOICE", "af_bella")
        model_path = os.getenv("MODEL_PATH", "models/kokoro/kokoro-v0_19.onnx")
        voices_path = os.getenv("VOICES_PATH", "models/kokoro/voices.json")

        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"ONNX model file not found at {model_path}")
        if not os.path.isfile(voices_path):
            raise FileNotFoundError(f"Voices file not found at {voices_path}")

        # Initialize Kokoro-ONNX
        self.kokoro = Kokoro(model_path, voices_path)

    def generate_speech(self, text, voice=None, response_format="mp3"):
        """
        Generate speech audio from the provided text using a specific voice.

        Args:
            text (str): The input text to convert to speech.
            voice (str, optional): The voice to use (default is set in the environment or "af_bella").
            response_format (str, optional): The desired output format (default: "mp3").

        Returns:
            str: Path to the generated audio file.
        """
        if not text:
            raise ValueError("Input text cannot be empty.")
        
        voice = voice or self.default_voice
        valid_formats = ['wav', 'mp3', 'ogg', 'flac']
        if response_format.lower() not in valid_formats:
            raise ValueError(f"Unsupported format: {response_format}")

        logging.debug(f"Generating audio with text: '{text}', voice: '{voice}'")

        try:
            # Generate audio
            audio = self._mock_text_to_audio() if DEBUG_MODE else self.kokoro.generate(text, voice)

            # Save the audio to a file
            output_file = f"output.{response_format}"
            with open(output_file, "wb") as f:
                f.write(audio)
            
            logging.info(f"Audio saved to {output_file}")
            return output_file
        except Exception as e:
            logging.error(f"Error during TTS generation: {e}")
            raise RuntimeError("Failed to generate speech.") from e
