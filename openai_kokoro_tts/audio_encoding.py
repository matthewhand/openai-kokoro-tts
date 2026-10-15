"""In-memory audio encoding. Content types always match encoded output."""
import io
import subprocess
import wave

import numpy as np


MIME_TYPES = {"wav": "audio/wav", "mp3": "audio/mpeg"}


def encode_audio(samples, sample_rate, output_format):
    if not isinstance(output_format, str) or output_format not in MIME_TYPES:
        raise ValueError("response_format must be wav or mp3")
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 1 or samples.size == 0 or not np.isfinite(samples).all():
        raise ValueError("audio samples must be nonempty, finite and mono")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)) or not 8000 <= sample_rate <= 96000:
        raise ValueError("invalid sample rate")
    if samples.size > int(sample_rate) * 120:
        raise ValueError("audio exceeds duration limit")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as dest:
        dest.setnchannels(1)
        dest.setsampwidth(2)
        dest.setframerate(int(sample_rate))
        dest.writeframes(pcm.tobytes())
    wav_bytes = output.getvalue()
    if output_format == "wav":
        return wav_bytes, MIME_TYPES["wav"]
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "wav",
             "-i", "pipe:0", "-vn", "-codec:a", "libmp3lame", "-b:a", "128k", "-f", "mp3", "pipe:1"],
            input=wav_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("MP3 encoder unavailable or timed out") from exc
    if proc.returncode != 0 or not proc.stdout.startswith(b"ID3"):
        raise RuntimeError("MP3 encoding failed")
    return proc.stdout, MIME_TYPES["mp3"]
