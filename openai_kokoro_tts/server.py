import os
import logging
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from tts_handler import TTSHandler
from utils import require_api_key, AUDIO_FORMAT_MIME_TYPES

# Load environment variables
load_dotenv()

# Initialize logging
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
LOG_LEVEL = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(level=LOG_LEVEL)

if DEBUG_MODE:
    logging.debug("Debug mode enabled in Flask server.")

# Initialize Flask app
app = Flask(__name__)

# Initialize TTSHandler
tts_handler = TTSHandler()

# Single info log statement for server initialization
logging.info("Flask server for Kokoro-TTS initialized successfully.")

@app.before_request
def log_request_info():
    """
    Log request details for debugging purposes.
    """
    if DEBUG_MODE:
        logging.debug(f"HTTP Request: {request.method} {request.url}")
        headers = {k: v for k, v in request.headers.items()}
        logging.debug(f"Headers: {headers}")
        if request.is_json:
            logging.debug(f"Payload: {request.json}")
        else:
            logging.debug("Payload: Non-JSON or empty.")

@app.route('/v1/audio/speech', methods=['POST'])
@require_api_key
def text_to_speech():
    """
    Generate speech from text input.
    
    JSON Body:
        - text (str): The input text to convert to speech.
        - voice (str, optional): The voice model to use (default: "af").
        - response_format (str, optional): Desired audio format (default: "mp3").
    
    Returns:
        Audio file as a response.
    """
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        text = data.get('input')
        voice = data.get('voice', None)
        response_format = data.get('response_format', "mp3")

        if DEBUG_MODE:
            logging.debug(f"Received request: text='{text}', voice='{voice}', format='{response_format}'")

        # Generate speech
        audio_file_path = tts_handler.generate_speech(text, voice, response_format)
        mime_type = AUDIO_FORMAT_MIME_TYPES.get(response_format.lower(), "audio/mpeg")

        return send_file(audio_file_path, mimetype=mime_type, as_attachment=True, download_name=f"speech.{response_format}")

    except Exception as e:
        logging.error(f"Error generating speech: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/v1/models', methods=['GET'])
@require_api_key
def list_models():
    """
    List available Kokoro-TTS voice models.

    Returns:
        JSON response with available models.
    """
    models = list(tts_handler.voicepacks.keys())
    if DEBUG_MODE:
        logging.debug(f"Available models: {models}")
    return jsonify({"models": models})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 9090))
    logging.info(f"Running Kokoro-TTS server on port {port}")
    app.run(host='0.0.0.0', port=port)
