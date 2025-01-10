# openai_kokoro_tts/tts_handler.py

import os
import logging
import torch
from models import build_model
from kokoro import generate
from pydub import AudioSegment
import soundfile as sf

DEBUG_MODE = os.getenv('DEBUG', 'false').lower() in ("true", "1", "yes")


class TTSHandler:
    def __init__(self):
        """
        Initialize TTSHandler with the PyTorch-based Kokoro-82M model.
        """
        self.default_voice = os.getenv('DEFAULT_VOICE', 'af_bella')
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Determine the base directory of this script
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # Use VOICE_PATH from the environment or fall back to the relative voices path
        self.voicepack_dir = os.getenv('VOICE_PATH', os.path.join(base_dir, 'models/kokoro/voices'))
        self.voicepacks = self._load_voicepacks()

        # Model initialization
        self.model_path = os.getenv(
            'MODEL_PATH',
            os.path.join(base_dir, 'models/kokoro/kokoro-v0_19.pth')
        )
        self.model = self._load_model()

        # Output directory
        self.output_dir = os.getenv('OUTPUT_DIR', os.path.join(base_dir, 'outputs'))
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            if DEBUG_MODE:
                logging.debug(f"Created output directory at {self.output_dir}")

    def _load_voicepacks(self):
        """
        Load all available voicepacks.

        Returns:
            dict: A dictionary mapping voice names to their loaded voicepacks.
        """
        if not os.path.exists(self.voicepack_dir):
            raise FileNotFoundError(f"Voicepack directory not found: {self.voicepack_dir}")

        voicepacks = {}
        for file in os.listdir(self.voicepack_dir):
            if file.endswith('.pt'):
                voice_name = file.replace('.pt', '')
                file_path = os.path.join(self.voicepack_dir, file)
                try:
                    voicepack = torch.load(file_path, map_location=self.device)
                    voicepacks[voice_name] = voicepack
                    if DEBUG_MODE:
                        logging.debug(f"Loaded voicepack: {voice_name} from {file_path}")
                except Exception as e:
                    logging.error(f"Failed to load voicepack '{voice_name}' from '{file_path}': {e}")
                    continue

        if not voicepacks:
            raise RuntimeError("No voicepacks found in the voicepack directory.")

        return voicepacks

    def _load_model(self):
        """
        Load the Kokoro-82M PyTorch model.

        Returns:
            torch.nn.Module: The loaded PyTorch model.
        """
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        try:
            model = build_model(self.model_path, self.device)
            if DEBUG_MODE:
                logging.debug(f"Model loaded successfully from {self.model_path} on {self.device}")
            return model
        except Exception as e:
            logging.error(f"Failed to load model from '{self.model_path}': {e}")
            raise RuntimeError(f"Failed to load model: {e}")

    def generate_speech(self, text, voice=None, response_format='mp3'):
        """
        Generate speech audio from the provided text using a specific voice.

        Args:
            text (str): The input text to convert to speech.
            voice (str, optional): The voice to use for speech generation. Defaults to the default voice.
            response_format (str, optional): The desired audio format for the output (default is "mp3").

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

        # Language determination based on voice name
        lang = 'en-us' if voice.startswith('a') else 'en-gb'

        if DEBUG_MODE:
            logging.debug(f"Generating speech for text: '{text}' with voice: '{voice}' and format: '{response_format}'")

        try:
            # Generate speech using the Kokoro generate function
            audio, out_ps = generate(self.model, text, voicepack, lang=lang)

            # Define output file path
            output_file = os.path.join(self.output_dir, f"{voice}_output.{response_format}")
            wav_path = os.path.join(self.output_dir, f"{voice}_output.wav")

            # Save the audio data as WAV first
            sf.write(wav_path, audio, 24000)
            if DEBUG_MODE:
                logging.debug(f"Intermediate WAV saved to {wav_path}")

            # Convert WAV to desired format using pydub
            audio_segment = AudioSegment.from_wav(wav_path)
            audio_segment.export(output_file, format=response_format)
            if DEBUG_MODE:
                logging.debug(f"Converted and saved audio to {output_file}")

            # Optionally, remove the intermediate WAV file
            os.remove(wav_path)
            if DEBUG_MODE:
                logging.debug(f"Removed intermediate WAV file: {wav_path}")

            return output_file

        except Exception as e:
            logging.error(f"Failed to generate speech: {e}")
            raise RuntimeError(f"Failed to generate speech: {e}")
