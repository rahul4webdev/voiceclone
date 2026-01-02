from __future__ import annotations

"""Voice cloning service for managing voice profiles."""

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceclone.core.config import get_settings
from voiceclone.core.logging import get_logger
from voiceclone.models.voice import Voice
from voiceclone.schemas.voice import VoiceCreate, VoiceUpdate
from voiceclone.utils.audio import (
    AudioProcessingError,
    normalize_audio,
    validate_audio_file,
)

logger = get_logger(__name__)
settings = get_settings()


class VoiceServiceError(Exception):
    """Exception raised for voice service errors."""

    pass


class VoiceNotFoundError(VoiceServiceError):
    """Exception raised when voice is not found."""

    pass


class VoiceService:
    """Service for managing voice profiles and cloning."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage_path = Path(settings.voice_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def create_voice(
        self,
        voice_data: VoiceCreate,
        audio_file: BinaryIO,
        filename: str,
    ) -> Voice:
        """Create a new voice profile from an audio sample.

        Args:
            voice_data: Voice metadata
            audio_file: Audio file object
            filename: Original filename

        Returns:
            Created Voice model instance
        """
        # Read file content
        file_content = audio_file.read()

        # Validate audio file
        try:
            audio_info = validate_audio_file(file_content, filename)
        except AudioProcessingError as e:
            raise VoiceServiceError(str(e)) from e

        # Generate unique ID for this voice
        voice_id = uuid.uuid4()
        voice_dir = self.storage_path / str(voice_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        # Save original file
        original_ext = Path(filename).suffix.lower()
        original_path = voice_dir / f"original{original_ext}"
        original_path.write_bytes(file_content)

        # Normalize audio for TTS
        processed_path = voice_dir / "processed.wav"
        try:
            normalized_info = normalize_audio(
                original_path,
                processed_path,
                target_sample_rate=settings.tts_sample_rate,
            )
        except AudioProcessingError as e:
            # Clean up on failure
            shutil.rmtree(voice_dir, ignore_errors=True)
            raise VoiceServiceError(f"Failed to process audio: {e}") from e

        # Create voice record
        voice = Voice(
            id=str(voice_id),
            name=voice_data.name,
            description=voice_data.description,
            original_filename=filename,
            original_format=original_ext.lstrip("."),
            duration_seconds=normalized_info["duration_seconds"],
            sample_rate=normalized_info["sample_rate"],
            processed_audio_path=str(processed_path),
            language=voice_data.language,
            tags=voice_data.tags,
            processing_status="pending",
            # Embeddings will be extracted by Modal service
            chatterbox_data={"audio_path": str(processed_path)},
            orpheus_data=None,
        )

        self.db.add(voice)
        await self.db.flush()

        logger.info(
            "Voice profile created",
            voice_id=str(voice_id),
            name=voice_data.name,
            duration=normalized_info["duration_seconds"],
        )

        return voice

    async def get_voice(self, voice_id: Union[uuid.UUID, str]) -> Voice:
        """Get a voice profile by ID.

        Args:
            voice_id: Voice UUID

        Returns:
            Voice model instance

        Raises:
            VoiceNotFoundError: If voice not found
        """
        voice_id_str = str(voice_id)
        result = await self.db.execute(select(Voice).where(Voice.id == voice_id_str))
        voice = result.scalar_one_or_none()

        if not voice:
            raise VoiceNotFoundError(f"Voice not found: {voice_id}")

        return voice

    async def list_voices(
        self,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> Tuple[List[Voice], int]:
        """List voice profiles with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            active_only: Only return active voices

        Returns:
            Tuple of (list of voices, total count)
        """
        query = select(Voice)

        if active_only:
            query = query.where(Voice.is_active == True)

        # Get total count
        count_result = await self.db.execute(
            select(Voice.id).where(Voice.is_active == True if active_only else True)
        )
        total = len(count_result.all())

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(Voice.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        voices = list(result.scalars().all())

        return voices, total

    async def update_voice(
        self,
        voice_id: Union[uuid.UUID, str],
        update_data: VoiceUpdate,
    ) -> Voice:
        """Update voice metadata.

        Args:
            voice_id: Voice UUID
            update_data: Fields to update

        Returns:
            Updated Voice model instance
        """
        voice = await self.get_voice(voice_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(voice, field, value)

        await self.db.flush()

        logger.info("Voice updated", voice_id=str(voice_id), fields=list(update_dict.keys()))

        return voice

    async def delete_voice(self, voice_id: Union[uuid.UUID, str]) -> None:
        """Delete a voice profile and its files.

        Args:
            voice_id: Voice UUID
        """
        voice = await self.get_voice(voice_id)

        # Delete files
        voice_dir = self.storage_path / str(voice_id)
        if voice_dir.exists():
            shutil.rmtree(voice_dir, ignore_errors=True)

        # Delete database record
        await self.db.delete(voice)

        logger.info("Voice deleted", voice_id=str(voice_id))

    async def update_processing_status(
        self,
        voice_id: Union[uuid.UUID, str],
        status: str,
        error: Optional[str] = None,
        chatterbox_data: Optional[dict] = None,
        orpheus_data: Optional[dict] = None,
    ) -> Voice:
        """Update voice processing status and embeddings.

        Args:
            voice_id: Voice UUID
            status: New status (pending, processing, ready, failed)
            error: Error message if failed
            chatterbox_data: Chatterbox model data
            orpheus_data: Orpheus model data

        Returns:
            Updated Voice model instance
        """
        voice = await self.get_voice(voice_id)

        voice.processing_status = status
        voice.processing_error = error

        if chatterbox_data:
            voice.chatterbox_data = chatterbox_data
        if orpheus_data:
            voice.orpheus_data = orpheus_data

        await self.db.flush()

        logger.info(
            "Voice processing status updated",
            voice_id=str(voice_id),
            status=status,
        )

        return voice

    async def get_voice_audio_path(self, voice_id: Union[uuid.UUID, str]) -> Path:
        """Get the processed audio path for a voice.

        Args:
            voice_id: Voice UUID

        Returns:
            Path to processed audio file

        Raises:
            VoiceNotFoundError: If voice not found
            VoiceServiceError: If audio file not found
        """
        voice = await self.get_voice(voice_id)
        audio_path = Path(voice.processed_audio_path)

        if not audio_path.exists():
            raise VoiceServiceError(f"Audio file not found for voice: {voice_id}")

        return audio_path
