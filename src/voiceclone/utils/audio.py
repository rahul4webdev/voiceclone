from __future__ import annotations

"""Audio processing utilities."""

import io
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import soundfile as sf
from pydub import AudioSegment

from voiceclone.core.config import get_settings
from voiceclone.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AudioProcessingError(Exception):
    """Exception raised for audio processing errors."""

    pass


def get_audio_info(file_path: Union[str, Path]) -> dict:
    """Get information about an audio file.

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary with audio info (duration, sample_rate, channels, format)
    """
    try:
        info = sf.info(str(file_path))
        return {
            "duration_seconds": info.duration,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
            "subtype": info.subtype,
        }
    except Exception as e:
        logger.error("Failed to get audio info", path=str(file_path), error=str(e))
        raise AudioProcessingError(f"Failed to read audio file: {e}") from e


def validate_audio_file(
    file_content: bytes,
    filename: str,
    max_size_mb: Optional[int] = None,
) -> dict:
    """Validate an uploaded audio file.

    Args:
        file_content: Raw file content
        filename: Original filename
        max_size_mb: Maximum file size in MB

    Returns:
        Dictionary with validation results and audio info

    Raises:
        AudioProcessingError: If validation fails
    """
    max_size = max_size_mb or settings.max_voice_sample_size_mb

    # Check file size
    size_mb = len(file_content) / (1024 * 1024)
    if size_mb > max_size:
        raise AudioProcessingError(
            f"File size ({size_mb:.2f}MB) exceeds maximum allowed ({max_size}MB)"
        )

    # Check file extension
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_audio_formats:
        raise AudioProcessingError(
            f"Unsupported audio format: {ext}. Allowed: {settings.allowed_audio_formats}"
        )

    # Try to read the audio to validate it's a valid audio file
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        info = get_audio_info(tmp_path)

        # Check minimum duration (need at least 3 seconds for voice cloning)
        if info["duration_seconds"] < 3:
            raise AudioProcessingError(
                f"Audio duration ({info['duration_seconds']:.1f}s) is too short. "
                "Minimum 3 seconds required for voice cloning."
            )

        # Check maximum duration (limit to 60 seconds)
        if info["duration_seconds"] > 60:
            raise AudioProcessingError(
                f"Audio duration ({info['duration_seconds']:.1f}s) is too long. "
                "Maximum 60 seconds allowed."
            )

        return {
            "valid": True,
            "format": ext,
            **info,
        }

    except AudioProcessingError:
        raise
    except Exception as e:
        logger.error("Audio validation failed", filename=filename, error=str(e))
        raise AudioProcessingError(f"Invalid audio file: {e}") from e
    finally:
        # Clean up temp file
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def normalize_audio(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    target_sample_rate: int = 24000,
    target_channels: int = 1,
) -> dict:
    """Normalize audio file for voice cloning.

    Converts to WAV format, resamples to target sample rate,
    and converts to mono.

    Args:
        input_path: Path to input audio file
        output_path: Path for output WAV file
        target_sample_rate: Target sample rate (default 24000 for TTS)
        target_channels: Target number of channels (default 1 for mono)

    Returns:
        Dictionary with normalized audio info
    """
    try:
        # Load audio using pydub (handles various formats)
        audio = AudioSegment.from_file(str(input_path))

        # Convert to mono
        if audio.channels > 1:
            audio = audio.set_channels(target_channels)

        # Resample
        if audio.frame_rate != target_sample_rate:
            audio = audio.set_frame_rate(target_sample_rate)

        # Normalize volume
        audio = audio.normalize()

        # Export as WAV
        audio.export(str(output_path), format="wav")

        # Get info of normalized file
        info = get_audio_info(output_path)

        logger.info(
            "Audio normalized successfully",
            input_path=str(input_path),
            output_path=str(output_path),
            duration=info["duration_seconds"],
            sample_rate=info["sample_rate"],
        )

        return info

    except Exception as e:
        logger.error(
            "Audio normalization failed",
            input_path=str(input_path),
            error=str(e),
        )
        raise AudioProcessingError(f"Failed to normalize audio: {e}") from e


def audio_to_base64(audio_data: np.ndarray, sample_rate: int) -> str:
    """Convert audio numpy array to base64 string.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate of the audio

    Returns:
        Base64 encoded WAV audio
    """
    import base64

    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format="WAV")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def base64_to_audio(base64_data: str) -> Tuple[np.ndarray, int]:
    """Convert base64 string to audio numpy array.

    Args:
        base64_data: Base64 encoded audio

    Returns:
        Tuple of (audio samples, sample rate)
    """
    import base64

    audio_bytes = base64.b64decode(base64_data)
    buffer = io.BytesIO(audio_bytes)
    data, sample_rate = sf.read(buffer)
    return data, sample_rate
