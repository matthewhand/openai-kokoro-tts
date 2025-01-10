import argparse
import os
import torch
import soundfile as sf
from openai_kokoro_tts.models import build_model
from openai_kokoro_tts.kokoro import generate

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Standalone CLI for Kokoro TTS inference.")
    parser.add_argument("text", type=str, help="The text to convert to speech.")
    parser.add_argument("--voice", type=str, default="af", help="Voice model to use (default: af).")
    parser.add_argument("--output", type=str, default="output.wav", help="Path to save the generated audio (default: output.wav).")
    parser.add_argument("--model_path", type=str, default="models/kokoro/kokoro-v0_19.pth",
                        help="Path to the Kokoro model file (default: models/kokoro/kokoro-v0_19.pth).")
    parser.add_argument("--voice_dir", type=str, default="models/kokoro/voices",
                        help="Path to the directory containing voicepacks (default: models/kokoro/voices).")
    args = parser.parse_args()

    # Verify paths
    if not os.path.exists(args.model_path):
        print(f"Error: Model file not found at {args.model_path}")
        exit(1)
    if not os.path.isdir(args.voice_dir):
        print(f"Error: Voice directory not found at {args.voice_dir}")
        exit(1)

    # Load the Kokoro model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading model from {args.model_path} on {device}...")
    model = build_model(args.model_path, device)

    # Load the voicepack
    voicepack_path = os.path.join(args.voice_dir, f"{args.voice}.pt")
    if not os.path.exists(voicepack_path):
        print(f"Error: Voicepack file not found for voice '{args.voice}' at {voicepack_path}")
        exit(1)
    print(f"Loading voicepack from {voicepack_path}...")
    voicepack = torch.load(voicepack_path, weights_only=True).to(device)

    # Generate speech
    print(f"Generating speech for text: '{args.text}'...")
    audio, phonemes = generate(model, args.text, voicepack, lang=args.voice[0])

    # Save the output audio
    sf.write(args.output, audio, 24000)  # 24 kHz sampling rate
    print(f"Audio saved to {args.output}")

if __name__ == "__main__":
    main()
