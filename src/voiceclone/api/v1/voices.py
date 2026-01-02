from __future__ import annotations

"""Voice management API endpoints."""

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from voiceclone.core.database import get_db
from voiceclone.schemas.voice import (
    VoiceCloneResponse,
    VoiceListResponse,
    VoiceResponse,
    VoiceUpdate,
)
from voiceclone.services.voice_service import (
    VoiceNotFoundError,
    VoiceService,
    VoiceServiceError,
)

router = APIRouter(prefix="/voices", tags=["voices"])


async def get_voice_service(
    db: AsyncSession = Depends(get_db),
) -> VoiceService:
    """Dependency for getting VoiceService instance."""
    return VoiceService(db)


@router.post(
    "/clone",
    response_model=VoiceCloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a voice from audio sample",
    description="Upload an audio sample (5-60 seconds) to create a cloned voice profile.",
)
async def clone_voice(
    audio_file: UploadFile = File(..., description="Audio file (WAV, MP3, FLAC, OGG, M4A)"),
    name: str = Form(..., description="Name for the cloned voice"),
    description: Optional[str] = Form(None, description="Optional description"),
    language: str = Form("en", description="Language code"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    service: VoiceService = Depends(get_voice_service),
) -> VoiceCloneResponse:
    """Clone a voice from an uploaded audio sample.

    The audio sample should be:
    - 5-60 seconds in length
    - Clear speech with minimal background noise
    - Supported formats: WAV, MP3, FLAC, OGG, M4A
    """
    from voiceclone.schemas.voice import VoiceCreate

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    voice_data = VoiceCreate(
        name=name,
        description=description,
        language=language,
        tags=tag_list,
    )

    try:
        voice = await service.create_voice(
            voice_data=voice_data,
            audio_file=audio_file.file,
            filename=audio_file.filename or "audio.wav",
        )

        return VoiceCloneResponse(
            voice_id=voice.id,
            status=voice.processing_status,
            message="Voice profile created. Processing will begin shortly.",
        )

    except VoiceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=VoiceListResponse,
    summary="List all voices",
    description="Get a paginated list of all cloned voice profiles.",
)
async def list_voices(
    page: int = 1,
    page_size: int = 20,
    active_only: bool = True,
    service: VoiceService = Depends(get_voice_service),
) -> VoiceListResponse:
    """List all voice profiles with pagination."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    voices, total = await service.list_voices(
        page=page,
        page_size=page_size,
        active_only=active_only,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return VoiceListResponse(
        items=[VoiceResponse.model_validate(v) for v in voices],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{voice_id}",
    response_model=VoiceResponse,
    summary="Get voice details",
    description="Get details of a specific voice profile.",
)
async def get_voice(
    voice_id: str,
    service: VoiceService = Depends(get_voice_service),
) -> VoiceResponse:
    """Get a voice profile by ID."""
    try:
        voice = await service.get_voice(voice_id)
        return VoiceResponse.model_validate(voice)
    except VoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {voice_id}",
        )


@router.patch(
    "/{voice_id}",
    response_model=VoiceResponse,
    summary="Update voice metadata",
    description="Update the metadata of a voice profile.",
)
async def update_voice(
    voice_id: str,
    update_data: VoiceUpdate,
    service: VoiceService = Depends(get_voice_service),
) -> VoiceResponse:
    """Update a voice profile's metadata."""
    try:
        voice = await service.update_voice(voice_id, update_data)
        return VoiceResponse.model_validate(voice)
    except VoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {voice_id}",
        )


@router.delete(
    "/{voice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a voice",
    description="Delete a voice profile and its associated files.",
)
async def delete_voice(
    voice_id: str,
    service: VoiceService = Depends(get_voice_service),
) -> None:
    """Delete a voice profile."""
    try:
        await service.delete_voice(voice_id)
    except VoiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {voice_id}",
        )
