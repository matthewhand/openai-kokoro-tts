import os
import logging
import tempfile
import torch
import soundfile as sf
from models import build_model
from kokoro import generate

# Initialize logging
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
LOG_LEVEL = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(level=LOG_LEVEL)

if DEBUG_MODE:
    logging.debug("Debug mode enabled in TTSHandler.")


class TTSHandler:
    """
    Handles text-to-speech (TTS) operations using Kokoro-TTS.
    Preloads the Kokoro model and voicepacks, and generates speech audio on request.
    """

    def __init__(self, default_voice=None):
        """
        Initialize the TTSHandler.

        Args:
            default_voice (str): The default voice to use for TTS (default is "af").
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.default_voice = default_voice or os.getenv("DEFAULT_VOICE", "af")

        # Base directory for relative paths
        self.base_dir = os.path.abspath(os.path.dirname(__file__))

        # Configurable model path via environment variable
        default_model_path = os.path.join(self.base_dir, "../models/kokoro/kokoro-v0_19.pth")
        self.model_path = os.getenv("MODEL_PATH", default_model_path)

        # Validate model path
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at: {self.model_path}")

        # Load the Kokoro-TTS model
        self.model = self._load_kokoro_model()

        # Default voicepack directory with environment override
        default_voicepack_dir = os.path.join(self.base_dir, "../models/kokoro/voices")
        self.voicepack_dir = os.getenv("VOICEPACK_DIR", default_voicepack_dir)

        # Preload voicepacks
        self.voicepacks = self._load_voicepacks()

        logging.info("TTSHandler initialized successfully.")

    def _load_kokoro_model(self):
        """
        Load the Kokoro-TTS model.

        Returns:
            torch.nn.Module: Preloaded Kokoro model.
        """
        if DEBUG_MODE:
            logging.debug(f"Loading Kokoro model from: {self.model_path}")
        return build_model(self.model_path, self.device)

    def _load_voicepacks(self):
        """
        Preload all available voicepacks.

        Returns:
            dict: A dictionary mapping voice names to their preloaded torch tensors.
        """
        if not os.path.exists(self.voicepack_dir):
            raise FileNotFoundError(f"Voicepack directory not found: {self.voicepack_dir}")

        voicepacks = {}
        for file in os.listdir(self.voicepack_dir):
            if file.endswith(".pt"):
                voice_name = os.path.splitext(file)[0]
                file_path = os.path.join(self.voicepack_dir, file)
                try:
                    voicepacks[voice_name] = torch.load(file_path).to(self.device)
                    if DEBUG_MODE:
                        logging.debug(f"Loaded voicepack: {voice_name} from {file_path}")
                except Exception as e:
                    logging.error(f"Failed to load voicepack {voice_name}: {e}")

        if not voicepacks:
            raise RuntimeError("No voicepacks found in the voicepack directory.")

        return voicepacks

    def generate_speech(self, text, voice=None, response_format="mp3"):
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
        """
        if not text:
            raise ValueError("Input text for TTS generation cannot be empty.")

        # Fallback to default voice if provided voice is invalid or unavailable
        if not voice or voice not in self.voicepacks:
            logging.warning(f"Invalid or unknown voice '{voice}'. Falling back to default voice: '{self.default_voice}'.")
            voice = self.default_voice

        voicepack = self.voicepacks[voice]

        # Kokoro-TTS generation logic
        if DEBUG_MODE:
            logging.debug(f"Generating speech for text: {text}, voice: {voice}")

        audio, phonemes = generate(self.model, text, voicepack, lang=voice[0])

        # Save audio to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{response_format}")
        sf.write(temp_file.name, audio, 24000)  # Kokoro uses 24kHz
        if DEBUG_MODE:
            logging.debug(f"Generated audio saved to: {temp_file.name}")
        return temp_file.name
