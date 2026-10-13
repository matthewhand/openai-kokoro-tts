"""OpenAI-style speech routes. The model is lazy-loaded and no audio is persisted."""
import io
import logging
import os
import threading

from flask import Flask, jsonify, request, send_file

from openai_kokoro_tts.audio_encoding import MIME_TYPES, encode_audio
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler
from openai_kokoro_tts.utils import require_api_key

log = logging.getLogger(__name__)


def create_app(handler=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    @app.errorhandler(413)
    def request_too_large(_exc):
        return jsonify({"error": "Request body too large"}), 413
    model = handler
    model_lock = threading.Lock()

    def get_model():
        nonlocal model
        if model is None:
            with model_lock:
                if model is None:
                    model = OnnxTTSHandler()
        return model

    @app.route('/v1/audio/speech', methods=['POST'])
    @require_api_key
    def text_to_speech():
        if not request.is_json:
            return jsonify({"error": "Expected a JSON object"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        text = data.get('input')
        voice = data.get('voice')
        speed = data.get('speed', 1.0)
        response_format = data.get('response_format', 'mp3')
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            return jsonify({"error": "input must be nonempty text of at most 1000 characters"}), 400
        if voice is not None and (not isinstance(voice, str) or not voice):
            return jsonify({"error": "voice must be a nonempty string"}), 400
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.5 <= speed <= 2.0:
            return jsonify({"error": "speed must be a number between 0.5 and 2.0"}), 400
        if response_format not in MIME_TYPES:
            return jsonify({"error": "response_format must be wav or mp3"}), 400
        try:
            samples, sample_rate = get_model().generate_speech(text, voice=voice, speed=speed)
            audio_bytes, mime = encode_audio(samples, sample_rate, response_format)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            log.error("Speech generation failed (%s)", type(exc).__name__)
            return jsonify({"error": "Speech generation failed"}), 500
        return send_file(io.BytesIO(audio_bytes), mimetype=mime, as_attachment=True,
                         download_name=f"speech.{response_format}")

    @app.route('/v1/models', methods=['GET'])
    @require_api_key
    def list_models():
        try:
            voices = get_model().get_voices()
        except Exception as exc:
            log.error("Voice list unavailable (%s)", type(exc).__name__)
            return jsonify({"error": "Voice list unavailable"}), 503
        return jsonify({"object": "list", "data": [{"id": v, "object": "model"} for v in voices], "models": voices})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "9090")))
