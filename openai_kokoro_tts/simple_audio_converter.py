import os
import subprocess
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def convert_audio_format(input_file_path, output_format):
    """
    Converts an audio file to the specified format using FFmpeg.

    Args:
        input_file_path (str): Path to the input audio file.
        output_format (str): Desired output format (e.g., 'mp3', 'wav').

    Returns:
        str: Path to the converted audio file.

    Raises:
        RuntimeError: If the conversion process fails.
    """
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"Input file does not exist: {input_file_path}")
    
    if not output_format:
        raise ValueError("Output format must be specified.")

    # Generate a unique output file path
    base_name, _ = os.path.splitext(input_file_path)
    output_file_path = f"{base_name}_converted.{output_format}"

    logger.debug(f"Converting audio: {input_file_path} -> {output_file_path} (format: {output_format})")

    try:
        # Run FFmpeg to convert the audio file
        subprocess.run(
            [
                "ffmpeg",
                "-i", input_file_path,  # Input file
                "-f", output_format,  # Output format
                "-y",  # Overwrite output file if it exists
                output_file_path,  # Output file path
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.debug(f"Conversion successful: {output_file_path}")
        return output_file_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Error during audio conversion: {e.stderr.decode()}")
        raise RuntimeError(f"Failed to convert audio to {output_format}: {e.stderr.decode()}")

