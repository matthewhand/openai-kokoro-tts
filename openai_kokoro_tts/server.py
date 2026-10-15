"""OpenAI-style speech routes. The model is lazy-loaded and no audio is persisted."""
import io
import logging
import math
import os
import threading

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from openai_kokoro_tts.admission import InferenceGate
from openai_kokoro_tts.audio_encoding import MIME_TYPES, encode_audio
from openai_kokoro_tts.errors import RequestValidationError, ServerBusyError
from openai_kokoro_tts.onnx_tts_handler import OnnxTTSHandler
from openai_kokoro_tts.utils import require_api_key

log = logging.getLogger(__name__)


def create_app(handler=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    # Fail startup (not the first request) on malformed admission settings.
    gate = handler.gate if getattr(handler, "gate", None) is not None else InferenceGate.from_env()

    @app.errorhandler(413)
    def request_too_large(_exc):
        return jsonify({"error": "Request body too large"}), 413

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify({"error": exc.name}), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        log.error("Unhandled error (%s)", type(exc).__name__)
        return jsonify({"error": "Internal server error"}), 500

    model = handler
    model_lock = threading.Lock()

    def get_model():
        nonlocal model
        if model is None:
            with model_lock:
                if model is None:
                    model = OnnxTTSHandler(gate=gate)
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
        speed = data.get('speed')
        response_format = data.get('response_format')

        # Validate input text
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            return jsonify({"error": "input must be nonempty text of at most 1000 characters"}), 400

        # Validate voice structure before model load
        if voice is not None:
            if not isinstance(voice, str) or not voice.strip():
                return jsonify({"error": "voice must be a nonempty string"}), 400
            voice = voice.strip()

        # Validate speed before model load
        if speed is None:
            speed = 1.0
        elif (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or not 0.5 <= speed <= 2.0
        ):
            return jsonify({"error": "speed must be a number between 0.5 and 2.0"}), 400

        # Validate response_format before model load
        if response_format is None:
            response_format = 'mp3'
        elif not isinstance(response_format, str) or response_format not in MIME_TYPES:
            return jsonify({"error": "response_format must be wav or mp3"}), 400

        # Lazy model resolution and voice check
        try:
            model_instance = get_model()
        except FileNotFoundError as exc:
            log.error("Model assets missing (%s)", type(exc).__name__)
            return jsonify({"error": "Model assets not found"}), 500
        except Exception as exc:
            log.error("Model initialization failed (%s)", type(exc).__name__)
            return jsonify({"error": "Model initialization failed"}), 500

        target_voice = voice or getattr(model_instance, "default_voice", "af_bella")
        valid_voices = model_instance.get_voices() if hasattr(model_instance, "get_voices") else []
        if valid_voices and target_voice not in valid_voices:
            return jsonify({"error": "Unknown voice"}), 400

        try:
            samples, sample_rate = model_instance.generate_speech(text, voice=target_voice, speed=speed)
            audio_bytes, mime = encode_audio(samples, sample_rate, response_format)
        except RequestValidationError as exc:
            # Only this type has a client-safe, fixed message.
            return jsonify({"error": str(exc)}), 400
        except ServerBusyError:
            response = jsonify({"error": "Server busy, retry shortly"})
            response.status_code = 503
            response.headers["Retry-After"] = "2"
            return response
        except Exception as exc:
            # Any other failure (including a backend ValueError) is not the
            # client's doing and its text may contain request data or paths.
            log.error("Speech generation failed (%s)", type(exc).__name__)
            return jsonify({"error": "Speech generation failed"}), 500

        return send_file(
            io.BytesIO(audio_bytes),
            mimetype=mime,
            as_attachment=True,
            download_name=f"speech.{response_format}",
        )

    @app.route('/v1/models', methods=['GET'])
    @require_api_key
    def list_models():
        try:
            voices = get_model().get_voices()
        except FileNotFoundError as exc:
            log.error("Model assets missing (%s)", type(exc).__name__)
            return jsonify({"error": "Model assets not found"}), 503
        except Exception as exc:
            log.error("Voice list unavailable (%s)", type(exc).__name__)
            return jsonify({"error": "Voice list unavailable"}), 503
        return jsonify({
            "object": "list",
            "data": [{"id": v, "object": "model"} for v in voices],
            "models": voices,
        })

    app.config["INFERENCE_GATE"] = gate
    return app


app = create_app()


def serve():
    """Serve with waitress (production WSGI, real worker threads).

    Threads matter for admission: a cooperative (gevent) server blocked inside
    native ONNX code cannot answer a second request at all, so it can never
    return the explicit 503 busy response. With threads, one worker runs the
    inference, up to ``max_waiting`` wait, and the rest are refused promptly.
    """
    import signal

    from waitress import serve as waitress_serve

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9090"))
    gate = app.config["INFERENCE_GATE"]
    threads = max(4, gate.max_waiting + 3)

    def _stop(_signum, _frame):
        raise KeyboardInterrupt  # waitress closes listeners and exits cleanly

    signal.signal(signal.SIGTERM, _stop)
    log.info("Starting waitress on %s:%d (threads=%d, max_waiting=%d)", host, port, threads, gate.max_waiting)
    waitress_serve(app, host=host, port=port, threads=threads,
                   max_request_body_size=64 * 1024, ident="openai-kokoro-tts")


if __name__ == '__main__':
    serve()
