import os
import logging
import numpy as np
import onnxruntime as ort

class OnnxTTSHandler:
    """
    Text-to-Speech (TTS) Handler leveraging ONNX Runtime for CPU-efficient inference.
    """

    def __init__(self):
        logging.info("Initializing ONNX TTSHandler.")

        # Load default voice setting from environment or fallback
        self.default_voice = os.getenv("DEFAULT_VOICE", "af_bella")
        logging.debug(f"Default voice set to: {self.default_voice}")

        # List of valid voices
        self.valid_voices = ["af_bella", "af_sky"]

        # Resolve and validate ONNX model path
        model_path = os.getenv("ONNX_MODEL_PATH", "models/kokoro/kokoro-v0_19.onnx")
        logging.info(f"Loading ONNX model from: {model_path}")

        if not os.path.isfile(model_path):
            logging.error(f"ONNX model file not found: {model_path}")
            raise FileNotFoundError(f"ONNX model file not found at {model_path}")

        # Initialize ONNX Runtime session
        try:
            self.session = ort.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.required_inputs = [input.name for input in self.session.get_inputs()]
            logging.info(f"ONNX model successfully loaded from {model_path}.")
            logging.debug(f"Model inputs: {self.required_inputs}")
        except Exception as e:
            logging.error(f"Failed to initialize ONNX Runtime session: {e}")
            raise RuntimeError("ONNX Runtime initialization failed.") from e

    def generate_speech(self, text, voice=None, response_format="mp3"):
        """
        Generate speech from input text using the specified or default voice.

        Args:
            text (str): The input text to convert to speech.
            voice (str, optional): The voice to use for speech synthesis. Defaults to the configured default voice.
            response_format (str, optional): The format of the audio output. Defaults to "mp3".

        Returns:
            str: The path to the generated audio file.

        Raises:
            ValueError: If the input text is empty.
            RuntimeError: If an invalid voice is provided or if inference fails.
        """
        if not text:
            raise ValueError("Input text cannot be empty.")

        voice = voice or self.default_voice
        logging.debug(f"Using voice: {voice}")

        # Check if the provided voice is valid
        if voice not in self.valid_voices:
            raise RuntimeError(f"Invalid voice: {voice}. Valid options are: {self.valid_voices}")

        try:
            # Tokenize text
            tokens = self._text_to_tokens(text)
            logging.debug(f"Input tokens for ONNX model: {tokens}")

            # Define additional inputs for the model
            style = np.ones((1,), dtype=np.float32)  # Mock style input
            speed = np.array([1.0], dtype=np.float32)  # Default speed

            # Prepare inputs for inference
            inputs = {
                name: tokens if name == "tokens" else style if name == "style" else speed
                for name in self.required_inputs
            }
            logging.debug(f"Model inputs: {inputs}")

            # Perform inference
            audio = self.session.run([self.output_name], inputs)[0]

            # Save audio to file
            output_file = f"output.{response_format}"
            with open(output_file, "wb") as f:
                f.write(audio.astype("float32").tobytes())
            logging.info(f"Generated audio saved to {output_file}")

            return output_file
        except Exception as e:
            logging.error(f"Error during ONNX speech generation: {e}")
            raise RuntimeError("Failed to generate speech with ONNX Runtime.") from e

    def _text_to_tokens(self, text):
        """
        Convert input text into numeric tokens for the ONNX model.

        Args:
            text (str): The text to convert.

        Returns:
            np.ndarray: A NumPy array of numeric tokens.
        """
        return np.array([ord(char) for char in text], dtype=np.int64)

    def get_voices(self):
        """
        Returns the list of valid voices available in this TTS handler.

        Returns:
            list[str]: A list of valid voice names.
        """
        return self.valid_voices
