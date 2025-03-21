import os
import logging
import numpy as np
import onnxruntime as ort
import soundfile as sf


class OnnxTTSHandler:
    def __init__(self, default_voice=None):
        logging.info("Initializing ONNX TTSHandler.")
        self.default_voice = default_voice or os.getenv("DEFAULT_VOICE", "af_bella")
        self.valid_voices = ["af_bella", "af_sky"]
        model_path = os.getenv("ONNX_MODEL_PATH", "models/kokoro/kokoro.onnx")

        if not os.path.isfile(model_path):
            logging.error(f"ONNX model file not found: {model_path}")
            raise FileNotFoundError(f"ONNX model file not found at {model_path}")

        try:
            self.session = ort.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.required_inputs = [input.name for input in self.session.get_inputs()]
            logging.info(f"ONNX model successfully loaded from {model_path}.")
        except Exception as e:
            logging.error(f"Failed to initialize ONNX Runtime session: {e}")
            raise RuntimeError("ONNX Runtime initialization failed.") from e

    def generate_speech(self, text, voice=None, response_format="wav", speed=1.0):
        if not text:
            raise ValueError("Input text cannot be empty.")

        voice = voice or self.default_voice
        if voice not in self.valid_voices:
            raise RuntimeError(f"Invalid voice: {voice}. Valid options are: {self.valid_voices}")

        try:
            tokens = self._text_to_tokens(text)
            style_vector = self._get_style_embedding(voice)
            style = np.tile(style_vector, (tokens.shape[0], 1))
            speed_array = np.array([speed], dtype=np.float32)

            inputs = {
                name: tokens if name == "tokens" else style if name == "style" else speed_array
                for name in self.required_inputs
            }

            audio = self.session.run([self.output_name], inputs)[0]

            # Define output directory based on module location
            module_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(module_dir, "outputs")
            os.makedirs(output_dir, exist_ok=True)

            # Save the audio file
            output_file = os.path.join(output_dir, f"output.{response_format}")
            sf.write(output_file, audio, samplerate=16000, format=response_format.upper())
            logging.info(f"Generated audio saved to {output_file}")

            return output_file
        except Exception as e:
            logging.error(f"Error during ONNX speech generation: {e}")
            raise RuntimeError("Failed to generate speech with ONNX Runtime.") from e

    def _text_to_tokens(self, text):
        return np.array([[ord(char) for char in text]], dtype=np.int64)

    def _get_style_embedding(self, voice):
        style_length = 256
        return np.full((style_length,), 0.5, dtype=np.float32)
