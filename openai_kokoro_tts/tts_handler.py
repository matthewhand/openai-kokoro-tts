import os
import torch
import logging
from kokoro.models import build_model
from kokoro.kokoro import generate

DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

class TTSHandler:
    def __init__(self):
        """
        Initialize TTSHandler with default voice, load voicepacks, and build the model.
        """
        logging.info("Initializing TTSHandler.")
        self.default_voice = os.getenv("DEFAULT_VOICE", "af_bella")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load model
        model_path = os.getenv("MODEL_PATH", "models/kokoro/kokoro-v0_19.pth")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        
        logging.info(f"Loading model from {model_path}")
        self.model = build_model(model_path, self.device)

        # Load voicepacks
        voicepack_dir = os.getenv("VOICEPACK_DIR", "voices")
        if not os.path.isdir(voicepack_dir):
            raise FileNotFoundError(f"Voicepack directory {voicepack_dir} not found.")
        
        self.voicepacks = {}
        for file in os.listdir(voicepack_dir):
            if file.endswith(".pt"):
                voice_name = os.path.splitext(file)[0]
                voice_path = os.path.join(voicepack_dir, file)
                logging.info(f"Loading voicepack: {voice_name}")
                voicepack = torch.load(voice_path).to(self.device)
                
                # Debug: Print structure of the voicepack
                logging.debug(f"Voicepack {voice_name} structure: {voicepack.shape if isinstance(voicepack, torch.Tensor) else 'Invalid format'}")
                
                # Ensure correct format
                if voicepack.dim() == 1:
                    voicepack = voicepack.unsqueeze(0)  # Reshape if needed
                
                self.voicepacks[voice_name] = voicepack

    def generate_speech(self, text, voice=None, response_format="mp3"):
        """
        Generate speech audio from the provided text using a specific voice.
        """
        if not text:
            raise ValueError("Input text cannot be empty.")
        
        voice = voice or self.default_voice
        if voice not in self.voicepacks:
            logging.warning(f"Invalid voice '{voice}', using default '{self.default_voice}'.")
            voice = self.default_voice
        
        voicepack = self.voicepacks[voice]
        lang = voice[0]

        logging.debug(f"Generating audio with voice: {voice}, text: {text}")
        try:
            audio, _ = generate(self.model, text, voicepack, lang=lang)
            output_file = f"output.{response_format}"
            with open(output_file, "wb") as f:
                f.write(audio.astype("float32").tobytes())
            return output_file
        except Exception as e:
            logging.error(f"Error in generate: {e}")
            raise
