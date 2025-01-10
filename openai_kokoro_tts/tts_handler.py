# openai_kokoro_tts/tts_handler.py

import os
import logging
import torch
import numpy as np
import onnxruntime
import soundfile as sf
from pydub import AudioSegment

DEBUG_MODE = os.getenv('DEBUG', 'false').lower() in ("true", "1", "yes")


class TTSHandler:
    def __init__(self):
        """
        Initialize TTSHandler.
        """
        self.default_voice = os.getenv('DEFAULT_VOICE', 'af_bella')

        # Determine the base directory of this script
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # Use VOICE_PATH from the environment or fall back to the relative voices path
        self.voicepack_dir = os.getenv('VOICE_PATH', os.path.join(base_dir, '../models/kokoro/voices'))
        self.voicepacks = self._load_voicepacks()

        # ONNX model initialization
        self.model_path = os.getenv(
            'MODEL_PATH',
            os.path.join(base_dir, '../models/kokoro/kokoro-v0_19.onnx')
        )
        self.model = self._load_model()

        # Output directory
        self.output_dir = os.getenv('OUTPUT_DIR', os.path.join(base_dir, '../outputs'))
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            if DEBUG_MODE:
                logging.debug(f"Created output directory at {self.output_dir}")

    def _load_voicepacks(self):
        """
        Preload all available voicepacks.

        Returns:
            dict: A dictionary mapping voice names to their preloaded numpy arrays.
        """
        if not os.path.exists(self.voicepack_dir):
            raise FileNotFoundError(f"Voicepack directory not found: {self.voicepack_dir}")

        voicepacks = {}
        for file in os.listdir(self.voicepack_dir):
            if file.endswith('.pt'):
                voice_name = file.replace('.pt', '')
                file_path = os.path.join(self.voicepack_dir, file)
                try:
                    # Load the PyTorch tensor and convert to NumPy array
                    loaded_voicepack = torch.load(file_path).numpy()
                    voicepacks[voice_name] = loaded_voicepack
                    if DEBUG_MODE:
                        logging.debug(
                            f"Loaded voicepack: {voice_name} "
                            f"from {file_path} with shape {loaded_voicepack.shape}"
                        )
                except Exception as e:
                    logging.error(f"Failed to load voicepack '{voice_name}' from '{file_path}': {e}")
                    continue

        if not voicepacks:
            raise RuntimeError("No voicepacks found in the voicepack directory.")

        return voicepacks

    def _load_model(self):
        """
        Load the ONNX model.

        Returns:
            onnxruntime.InferenceSession: The ONNX model session.
        """
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"ONNX model not found: {self.model_path}")

        if DEBUG_MODE:
            logging.debug(f"Loading ONNX model from {self.model_path}")

        try:
            return onnxruntime.InferenceSession(self.model_path)
        except Exception as e:
            logging.error(f"Failed to load ONNX model from '{self.model_path}': {e}")
            raise RuntimeError(f"Failed to load ONNX model: {e}")

    def _preprocess_text(self, text):
        """
        Convert input text to tokens.

        Args:
            text (str): The input text.

        Returns:
            list[int]: Tokenized representation of the text.
        """
        # Placeholder for real text preprocessing logic
        return [ord(c) for c in text]

    def generate_speech(self, text, voice=None, response_format='mp3'):
        """
        Generate speech audio from the provided text using a specific voice.

        Args:
            text (str): The input text to convert to speech.
            voice (str): The voice to use for speech generation. Defaults to the default voice.
            response_format (str): The desired audio format for the output (default is "mp3").

        Returns:
            str: The path to the generated audio file.

        Raises:
            ValueError: If input text is empty.
            RuntimeError: If speech generation fails.
        """
        if not text:
            raise ValueError("Input text for TTS generation cannot be empty.")

        # Fallback to default voice if provided voice is invalid or unavailable
        if not voice or voice not in self.voicepacks:
            logging.warning(
                f'Invalid or unknown voice "{voice}". Falling back to default voice: "{self.default_voice}".'
            )
            voice = self.default_voice

        voicepack = self.voicepacks[voice]

        # Check the original shape before any manipulation
        if DEBUG_MODE:
            logging.debug(f"Original voicepack shape: {voicepack.shape}")

        # Handle different voicepack shapes
        if voicepack.ndim == 3 and voicepack.shape[0] > 1 and voicepack.shape[1] == 1 and voicepack.shape[2] == 256:
            # Shape: (511, 1, 256) -> Select the first vector
            voicepack = voicepack[0, 0, :]  # Shape: (256,)
            if DEBUG_MODE:
                logging.debug(f"Selected first style vector: {voicepack.shape}")
        elif voicepack.ndim == 2 and voicepack.shape[0] > 1 and voicepack.shape[1] == 256:
            # Shape: (512, 256) -> Select the first vector
            voicepack = voicepack[0, :]  # Shape: (256,)
            if DEBUG_MODE:
                logging.debug(f"Selected first style vector: {voicepack.shape}")
        elif voicepack.ndim == 1 and voicepack.shape[0] == 256:
            # Shape: (256,)
            pass  # Already correct
        else:
            logging.error(f"Unexpected voicepack shape after processing: {voicepack.shape}")
            raise RuntimeError("Invalid voicepack shape. Expected shape (256,).")

        # Ensure 'style' has shape (1, 256)
        if voicepack.ndim == 1 and voicepack.shape[0] == 256:
            style = voicepack[None, :].astype(np.float32)  # Shape: (1, 256)
            if DEBUG_MODE:
                logging.debug(f"Reshaped style to: {style.shape}")
        else:
            logging.error(f"Unexpected voicepack shape after processing: {voicepack.shape}")
            raise RuntimeError("Invalid voicepack shape. Expected shape (256,).")

        # Preprocess text into tokens
        tokens = self._preprocess_text(text)
        tokens = np.array(tokens, dtype=np.int64)[None, :]  # Shape: (1, T)
        if DEBUG_MODE:
            logging.debug(f"Tokenized text: {tokens}")

        # ONNX model inference
        inputs = {
            'tokens': tokens,           # Shape: (1, T)
            'style': style,             # Shape: (1, 256)
            'speed': np.ones((1,), dtype=np.float32)  # Shape: (1,)
        }

        if DEBUG_MODE:
            logging.debug(
                f"Model inputs: tokens shape {inputs['tokens'].shape}, "
                f"style shape {inputs['style'].shape}, speed shape {inputs['speed'].shape}"
            )

        try:
            outputs = self.model.run(None, inputs)
            if DEBUG_MODE:
                logging.debug(f"Model outputs: {outputs}")
        except Exception as e:
            logging.error(f"Model inference failed: {e}")
            raise RuntimeError("Failed to generate speech.")

        # Validate model output
        if not outputs or not isinstance(outputs, list) or len(outputs) < 1:
            logging.error("Model did not return valid audio data.")
            raise RuntimeError("Failed to generate speech.")

        audio_data = outputs[0]
        if not isinstance(audio_data, np.ndarray) or audio_data.size == 0:
            logging.error("Model returned an empty or invalid output array.")
            raise RuntimeError("Failed to generate speech.")

        # Define output file path
        output_file = os.path.join(self.output_dir, f"{voice}_output.{response_format}")
        if DEBUG_MODE:
            logging.debug(f"Output file path: {output_file}")

        # Save the audio data to a file using soundfile and pydub for proper encoding
        try:
            # Assume the model outputs raw float audio samples with a sampling rate of 24000 Hz
            wav_path = os.path.join(self.output_dir, f"{voice}_output.wav")
            sf.write(wav_path, audio_data, 24000)  # Save as WAV first
            if DEBUG_MODE:
                logging.debug(f"Intermediate WAV saved to {wav_path}")

            # Convert WAV to desired format using pydub
            audio = AudioSegment.from_wav(wav_path)
            audio.export(output_file, format=response_format)
            if DEBUG_MODE:
                logging.debug(f"Converted and saved audio to {output_file}")

            # Optionally, remove the intermediate WAV file
            os.remove(wav_path)
            if DEBUG_MODE:
                logging.debug(f"Removed intermediate WAV file: {wav_path}")

        except Exception as e:
            logging.error(f"Failed to process and save audio file '{output_file}': {e}")
            raise RuntimeError(f"Failed to process and save audio file: {e}")

        return output_file
