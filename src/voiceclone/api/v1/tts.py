from __future__ import annotations

"""Text-to-Speech API endpoints."""

import base64
import io
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from voiceclone.core.database import get_db
from voiceclone.core.logging import get_logger
from voiceclone.schemas.tts import TTSRequest, TTSResponse
from voiceclone.services.tts_client import TTSClient, TTSClientError, get_tts_client
from voiceclone.services.voice_service import (
    VoiceNotFoundError,
    VoiceService,
    VoiceServiceError,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])


async def get_voice_service(
    db: AsyncSession = Depends(get_db),
) -> VoiceService:
    """Dependency for getting VoiceService instance."""
    return VoiceService(db)


@router.post(
    "/synthesize",
    response_model=TTSResponse,
    summary="Synthesize speech",
    description="Convert text to speech using a cloned voice.",
)
async def synthesize_speech(
    request: TTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
    tts_client: TTSClient = Depends(get_tts_client),
) -> TTSResponse:
    """Synthesize speech from text using a cloned voice.

    Returns a URL to download the generated audio file.
    """
    start_time = time.time()

    # Get voice profile
    try:
        voice = await voice_service.get_voice(request.voice_id)
    except VoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {request.voice_id}",
        )

    # Check voice is ready
    if voice.processing_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voice is not ready for synthesis. Status: {voice.processing_status}",
        )

    # Get audio path for chatterbox
    try:
        audio_path = await voice_service.get_voice_audio_path(request.voice_id)
    except VoiceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Call TTS service
    try:
        result = await tts_client.synthesize(
            text=request.text,
            model=request.model,
            audio_path=audio_path if request.model in ("chatterbox", "xtts") else None,
            language=request.language,
            voice="tara",  # Orpheus default voice
            emotion=request.emotion,
            speaker_gender=request.speaker_gender,
        )
    except TTSClientError as e:
        logger.error("TTS synthesis failed", error=str(e), voice_id=str(request.voice_id))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS service error: {e}",
        )

    processing_time = (time.time() - start_time) * 1000

    # For now, return base64 audio URL (in production, save to storage and return URL)
    # The audio_url will be a data URL for simplicity
    audio_url = f"data:audio/wav;base64,{result['audio_base64']}"

    return TTSResponse(
        audio_url=audio_url,
        duration_seconds=result.get("duration_seconds", 0),
        model_used=result.get("model", request.model),
        processing_time_ms=processing_time,
    )


@router.post(
    "/synthesize/audio",
    summary="Synthesize and return audio directly",
    description="Convert text to speech and return the audio file directly.",
    response_class=StreamingResponse,
)
async def synthesize_audio(
    request: TTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
    tts_client: TTSClient = Depends(get_tts_client),
) -> StreamingResponse:
    """Synthesize speech and return audio file directly.

    Returns the audio file as a streaming response.
    """
    # Get voice profile
    try:
        voice = await voice_service.get_voice(request.voice_id)
    except VoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {request.voice_id}",
        )

    # Check voice is ready
    if voice.processing_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voice is not ready for synthesis. Status: {voice.processing_status}",
        )

    # Get audio path
    try:
        audio_path = await voice_service.get_voice_audio_path(request.voice_id)
    except VoiceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Call TTS service
    try:
        result = await tts_client.synthesize(
            text=request.text,
            model=request.model,
            audio_path=audio_path if request.model in ("chatterbox", "xtts") else None,
            language=request.language,
            voice="tara",
            emotion=request.emotion,
            speaker_gender=request.speaker_gender,
        )
    except TTSClientError as e:
        logger.error("TTS synthesis failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS service error: {e}",
        )

    # Decode audio and return as stream
    audio_bytes = tts_client.decode_audio(result["audio_base64"])
    audio_stream = io.BytesIO(audio_bytes)

    # Determine content type
    content_type = "audio/wav" if request.output_format == "wav" else "audio/mpeg"

    return StreamingResponse(
        audio_stream,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="speech.{request.output_format}"',
            "X-Duration-Seconds": str(result.get("duration_seconds", 0)),
            "X-Processing-Time-Ms": str(result.get("processing_time_ms", 0)),
        },
    )


@router.get(
    "/models",
    summary="List available TTS models",
    description="Get information about available TTS models.",
)
async def list_models() -> dict:
    """List available TTS models and their capabilities."""
    return {
        "models": [
            {
                "id": "svara",
                "name": "svara-TTS",
                "description": "Indian languages TTS with emotion control (19 languages)",
                "features": ["emotion_tags", "indian_languages", "voice_cloning"],
                "requires_reference_audio": False,
                "supported_languages": [
                    "hi", "bn", "mr", "te", "kn", "ta", "gu", "ml", "pa",
                    "as", "or", "bo", "doi", "bho", "mai", "mag", "cg", "ne", "sa", "en-in"
                ],
                "emotion_tags": ["happy", "sad", "anger", "fear", "neutral"],
                "recommended_for": "Hindi and Indian languages - best quality",
            },
            {
                "id": "xtts",
                "name": "XTTS-v2",
                "description": "Multilingual voice cloning with 17 languages",
                "features": ["voice_cloning", "multilingual"],
                "requires_reference_audio": True,
                "supported_languages": [
                    "en", "es", "fr", "de", "it", "pt", "pl", "tr",
                    "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"
                ],
            },
            {
                "id": "chatterbox",
                "name": "Chatterbox",
                "description": "High-quality voice cloning with emotion control",
                "features": ["voice_cloning", "emotion_exaggeration"],
                "requires_reference_audio": True,
                "supported_languages": ["en"],
            },
            {
                "id": "orpheus",
                "name": "Orpheus",
                "description": "Emotional speech synthesis with preset voices",
                "features": ["emotion_tags", "preset_voices"],
                "requires_reference_audio": False,
                "supported_languages": ["en"],
                "preset_voices": ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"],
                "emotion_tags": ["happy", "sad", "angry", "surprised", "neutral"],
            },
        ]
    }
