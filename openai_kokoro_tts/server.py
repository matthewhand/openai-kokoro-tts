import os
import logging
import json
import io
import numpy as np
import wave
from flask import Flask, request, jsonify, send_file
from functools import wraps
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler
from openai_kokoro_tts.utils import require_api_key, AUDIO_FORMAT_MIME_TYPES

# Initialize Flask app
app = Flask(__name__)
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

# Configure logging
if DEBUG_MODE:
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("Debug mode enabled.")
else:
    logging.basicConfig(level=logging.INFO)

# Initialize ONNX TTS handler
tts_handler = OnnxTTSHandler()

def process_audio_output(audio, sample_rate=16000):
    """
    Processes the raw audio output from the ONNX model into a WAV file as bytes.

    Args:
        audio (np.ndarray): Raw audio output from the model.
        sample_rate (int): Sampling rate of the audio (default: 16000).

    Returns:
        bytes: Byte representation of the WAV file.
    """
    # Convert to numpy array if necessary
    if not isinstance(audio, np.ndarray):
        audio = np.array(audio)

    # Log the audio properties for debugging
    logging.debug(f"Audio data type: {audio.dtype}, shape: {audio.shape}")

    # Ensure the audio array is one-dimensional
    if len(audio.shape) != 1:
        raise ValueError(f"Unexpected audio shape: {audio.shape}. Expected a 1D array.")

    # Ensure audio is floating-point and clip to the PCM range
    if audio.dtype.kind != 'f':
        audio = audio.astype(np.float32)

    audio = np.clip(audio * 32767, -32768, 32767).astype(np.int16)

    # Write WAV file to an in-memory bytes buffer
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())

    buffer.seek(0)
    return buffer.read()

@app.route('/v1/audio/speech', methods=['POST'])
@require_api_key
def text_to_speech():
    """
    Generate speech from text input and return audio.

    Request payload:
    {
        "input": "Text to convert to speech",
        "voice": "af_bella",  # Optional
        "response_format": "wav",  # Optional
        "speed": 1.0  # Optional
    }

    Returns:
        Audio file in the requested format.
    """
    data = request.json

    if not data or 'input' not in data:
        return jsonify({"error": "Missing 'input' in request body"}), 400

    text = data['input']
    voice = data.get('voice', tts_handler.default_voice)
    response_format = data.get('response_format', 'wav')
    speed = float(data.get('speed', 1.0))

    if response_format not in AUDIO_FORMAT_MIME_TYPES:
        return jsonify({"error": f"Unsupported audio format: {response_format}"}), 400

    try:
        # Generate raw audio using the TTS handler
        audio = tts_handler.generate_speech(text=text, voice=voice, speed=speed)
        audio_bytes = process_audio_output(audio)

        mime_type = AUDIO_FORMAT_MIME_TYPES[response_format]
        return send_file(
            io.BytesIO(audio_bytes),
            mimetype=mime_type,
            as_attachment=True,
            download_name=f"speech.{response_format}"
        )
    except ValueError as e:
        logging.error(f"ValueError during TTS generation: {e}")
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        logging.error(f"RuntimeError during TTS generation: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"Unhandled exception during TTS generation: {e}")
        return jsonify({"error": "Failed to generate speech"}), 500

@app.route('/v1/models', methods=['GET'])
def list_models():
    """
    List available Kokoro-TTS voice models.

    Returns:
        JSON response with available models.
    """
    models = tts_handler.get_voices()
    if DEBUG_MODE:
        logging.debug(f"Available models: {models}")
    return jsonify({"models": models})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 9090))
    logging.info(f"Kokoro-TTS API running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port)
