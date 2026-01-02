from __future__ import annotations

"""TTS Client service for communicating with Modal.com inference server.

Supports:
- svara-TTS: Indian languages (19 languages including Hindi, Bengali, Tamil, Telugu, etc.)
- XTTS-v2: Multilingual voice cloning (17 languages including Hindi, English)
- Chatterbox: English voice cloning with emotion control
- Orpheus: English emotional TTS with preset voices
"""

import base64
from pathlib import Path
from typing import AsyncIterator, List, Optional, Union

import httpx

from voiceclone.core.config import get_settings
from voiceclone.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Supported languages for XTTS-v2
XTTS_SUPPORTED_LANGUAGES = [
    "en",  # English
    "es",  # Spanish
    "fr",  # French
    "de",  # German
    "it",  # Italian
    "pt",  # Portuguese
    "pl",  # Polish
    "tr",  # Turkish
    "ru",  # Russian
    "nl",  # Dutch
    "cs",  # Czech
    "ar",  # Arabic
    "zh-cn",  # Chinese (Simplified)
    "ja",  # Japanese
    "hu",  # Hungarian
    "ko",  # Korean
    "hi",  # Hindi
]

# Supported languages for svara-TTS (Indian languages)
SVARA_SUPPORTED_LANGUAGES = [
    "hi",  # Hindi
    "bn",  # Bengali
    "mr",  # Marathi
    "te",  # Telugu
    "kn",  # Kannada
    "ta",  # Tamil
    "gu",  # Gujarati
    "ml",  # Malayalam
    "pa",  # Punjabi
    "as",  # Assamese
    "or",  # Odia
    "bo",  # Bodo
    "doi",  # Dogri
    "bho",  # Bhojpuri
    "mai",  # Maithili
    "mag",  # Magahi
    "cg",  # Chhattisgarhi
    "ne",  # Nepali
    "sa",  # Sanskrit
    "en-in",  # Indian English
]

# Svara emotion tags
SVARA_EMOTIONS = ["happy", "sad", "anger", "fear", "neutral"]

# Combined supported languages
SUPPORTED_LANGUAGES = list(set(XTTS_SUPPORTED_LANGUAGES + SVARA_SUPPORTED_LANGUAGES))


class TTSClientError(Exception):
    """Exception raised for TTS client errors."""

    pass


class TTSClient:
    """Client for Modal.com TTS inference service with multilingual support."""

    def __init__(self):
        self.endpoint = settings.modal_tts_endpoint
        self.timeout = httpx.Timeout(300.0, connect=30.0)  # 5 min for long texts

    def _get_headers(self) -> dict:
        """Get headers for Modal API requests."""
        return {
            "Content-Type": "application/json",
        }

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages for multilingual TTS."""
        return SUPPORTED_LANGUAGES.copy()

    async def synthesize_xtts(
        self,
        text: str,
        audio_path: Union[str, Path],
        language: str = "en",
    ) -> dict:
        """Synthesize speech using XTTS-v2 model (multilingual).

        Args:
            text: Text to synthesize
            audio_path: Path to reference audio file
            language: Language code (en, hi, es, fr, de, etc.)

        Returns:
            Dictionary with audio data and metadata
        """
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise TTSClientError(
                f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}"
            )

        # Read and encode reference audio
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise TTSClientError(f"Audio file not found: {audio_path}")

        audio_base64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")

        payload = {
            "model": "xtts",
            "text": text,
            "audio_prompt_base64": audio_base64,
            "language": language,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise TTSClientError(f"TTS error: {result['error']}")

                return result

        except httpx.HTTPError as e:
            logger.error("HTTP error during TTS request", error=str(e))
            raise TTSClientError(f"Failed to connect to TTS service: {e}") from e

    async def synthesize_chatterbox(
        self,
        text: str,
        audio_path: Union[str, Path],
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> dict:
        """Synthesize speech using Chatterbox model on Modal (English only).

        Args:
            text: Text to synthesize
            audio_path: Path to reference audio file
            exaggeration: Emotion exaggeration factor
            cfg_weight: Classifier-free guidance weight

        Returns:
            Dictionary with audio data and metadata
        """
        # Read and encode reference audio
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise TTSClientError(f"Audio file not found: {audio_path}")

        audio_base64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")

        payload = {
            "model": "chatterbox",
            "text": text,
            "audio_prompt_base64": audio_base64,
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise TTSClientError(f"TTS error: {result['error']}")

                return result

        except httpx.HTTPError as e:
            logger.error("HTTP error during TTS request", error=str(e))
            raise TTSClientError(f"Failed to connect to TTS service: {e}") from e

    async def synthesize_orpheus(
        self,
        text: str,
        voice: str = "tara",
        emotion: Optional[str] = None,
    ) -> dict:
        """Synthesize speech using Orpheus model on Modal (English only).

        Args:
            text: Text to synthesize
            voice: Voice ID (tara, leah, jess, leo, dan, mia, zac, zoe)
            emotion: Optional emotion tag

        Returns:
            Dictionary with audio data and metadata
        """
        payload = {
            "model": "orpheus",
            "text": text,
            "voice": voice,
        }
        if emotion:
            payload["emotion"] = emotion

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise TTSClientError(f"TTS error: {result['error']}")

                return result

        except httpx.HTTPError as e:
            logger.error("HTTP error during TTS request", error=str(e))
            raise TTSClientError(f"Failed to connect to TTS service: {e}") from e

    async def synthesize_svara(
        self,
        text: str,
        language: str = "hi",
        emotion: Optional[str] = None,
        speaker_gender: str = "female",
        audio_path: Optional[Union[str, Path]] = None,
    ) -> dict:
        """Synthesize speech using svara-TTS model on Modal (Indian languages).

        Args:
            text: Text to synthesize
            language: Language code (hi, bn, ta, te, mr, gu, kn, ml, pa, etc.)
            emotion: Optional emotion tag (happy, sad, anger, fear, neutral)
            speaker_gender: Speaker gender (male/female)
            audio_path: Optional reference audio for voice cloning

        Returns:
            Dictionary with audio data and metadata
        """
        # Validate language
        if language not in SVARA_SUPPORTED_LANGUAGES:
            raise TTSClientError(
                f"Unsupported language for svara: {language}. Supported: {SVARA_SUPPORTED_LANGUAGES}"
            )

        # Validate emotion
        if emotion and emotion not in SVARA_EMOTIONS:
            raise TTSClientError(
                f"Unsupported emotion for svara: {emotion}. Supported: {SVARA_EMOTIONS}"
            )

        payload = {
            "model": "svara",
            "text": text,
            "language": language,
            "speaker_gender": speaker_gender,
        }

        if emotion:
            payload["emotion"] = emotion

        # Add reference audio for voice cloning if provided
        if audio_path:
            audio_path = Path(audio_path)
            if audio_path.exists():
                audio_base64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")
                payload["audio_prompt_base64"] = audio_base64

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise TTSClientError(f"TTS error: {result['error']}")

                return result

        except httpx.HTTPError as e:
            logger.error("HTTP error during TTS request", error=str(e))
            raise TTSClientError(f"Failed to connect to TTS service: {e}") from e

    async def synthesize(
        self,
        text: str,
        model: str = "svara",
        audio_path: Optional[Union[str, Path]] = None,
        language: str = "hi",
        voice: str = "tara",
        emotion: Optional[str] = None,
        speaker_gender: str = "female",
        **kwargs,
    ) -> dict:
        """Unified synthesis method with multilingual support.

        Args:
            text: Text to synthesize
            model: Model to use ("svara" for Indian languages, "xtts" for multilingual, "chatterbox" for English, "orpheus" for preset voices)
            audio_path: Reference audio path (required for xtts/chatterbox, optional for svara)
            language: Language code (hi for svara, en for xtts, etc.)
            voice: Voice ID for orpheus
            emotion: Emotion tag for orpheus/svara
            speaker_gender: Speaker gender for svara (male/female)
            **kwargs: Additional model-specific parameters

        Returns:
            Dictionary with audio data and metadata
        """
        if model == "svara":
            # svara-TTS for Indian languages (Hindi, Bengali, Tamil, etc.)
            return await self.synthesize_svara(
                text=text,
                language=language,
                emotion=emotion,
                speaker_gender=speaker_gender,
                audio_path=audio_path,
            )
        elif model == "xtts":
            if not audio_path:
                raise TTSClientError("audio_path is required for xtts model")
            return await self.synthesize_xtts(
                text=text,
                audio_path=audio_path,
                language=language,
            )
        elif model == "chatterbox":
            if not audio_path:
                raise TTSClientError("audio_path is required for chatterbox model")
            return await self.synthesize_chatterbox(
                text=text,
                audio_path=audio_path,
                **kwargs,
            )
        elif model == "orpheus":
            return await self.synthesize_orpheus(
                text=text,
                voice=voice,
                emotion=emotion,
            )
        else:
            raise TTSClientError(
                f"Unknown model: {model}. Use 'svara' (Indian), 'xtts' (multilingual), 'chatterbox' (English), or 'orpheus' (English)"
            )

    async def stream_synthesis(
        self,
        text: str,
        model: str = "xtts",
        audio_path: Optional[Union[str, Path]] = None,
        language: str = "en",
        voice: str = "tara",
        emotion: Optional[str] = None,
        chunk_size: int = 25,
    ) -> AsyncIterator[dict]:
        """Stream synthesized speech chunks.

        Note: Streaming requires Modal function calls, which are handled differently.
        This method provides a simplified interface that falls back to non-streaming
        when HTTP endpoint is used.

        For true streaming, use Modal's native function calls from the VPS.

        Args:
            text: Text to synthesize
            model: Model to use (xtts, chatterbox, orpheus)
            audio_path: Reference audio path (for xtts/chatterbox)
            language: Language code for xtts
            voice: Voice ID (for orpheus)
            emotion: Emotion tag (for orpheus)
            chunk_size: Tokens per chunk

        Yields:
            Dictionary with audio chunks
        """
        # For HTTP endpoint, we do a single request and yield the result
        # True streaming would require Modal's native Python client
        result = await self.synthesize(
            text=text,
            model=model,
            audio_path=audio_path,
            language=language,
            voice=voice,
            emotion=emotion,
        )

        if "error" in result:
            yield {"error": result["error"], "is_final": True}
            return

        # Yield the full audio as a single chunk
        yield {
            "chunk_index": 0,
            "audio_base64": result["audio_base64"],
            "sample_rate": result.get("sample_rate", 24000),
            "language": result.get("language", language),
            "is_final": False,
        }

        yield {
            "is_final": True,
            "total_chunks": 1,
            "duration_seconds": result.get("duration_seconds", 0),
            "processing_time_ms": result.get("processing_time_ms", 0),
        }

    def decode_audio(self, audio_base64: str) -> bytes:
        """Decode base64 audio to bytes.

        Args:
            audio_base64: Base64 encoded audio

        Returns:
            Audio bytes
        """
        return base64.b64decode(audio_base64)


# Singleton instance
_tts_client: Optional[TTSClient] = None


def get_tts_client() -> TTSClient:
    """Get TTS client singleton instance."""
    global _tts_client
    if _tts_client is None:
        _tts_client = TTSClient()
    return _tts_client
