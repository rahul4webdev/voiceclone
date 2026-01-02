from __future__ import annotations

"""Pydantic schemas for TTS-related API operations."""

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Schema for text-to-speech synthesis request."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to convert to speech",
    )
    voice_id: uuid.UUID = Field(..., description="ID of the cloned voice to use")
    model: Literal["svara", "xtts", "chatterbox", "orpheus"] = Field(
        default="svara",
        description="TTS model to use. 'svara' for Hindi/Indian languages, 'xtts' for multilingual, 'chatterbox' for English, 'orpheus' for emotional speech",
    )
    language: str = Field(
        default="hi",
        description="Language code (hi, bn, ta, te, mr, gu, etc. for svara; en, es, fr, etc. for xtts)",
    )
    emotion: Optional[str] = Field(
        None,
        description="Emotion tag (happy, sad, anger, fear, neutral for svara; happy, sad, angry for orpheus)",
    )
    speaker_gender: Literal["male", "female"] = Field(
        default="female",
        description="Speaker gender for svara model",
    )
    speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Speech speed multiplier",
    )
    output_format: Literal["wav", "mp3"] = Field(
        default="wav",
        description="Output audio format",
    )


class TTSResponse(BaseModel):
    """Schema for TTS synthesis response."""

    audio_url: str = Field(..., description="URL to download the generated audio")
    duration_seconds: float = Field(..., description="Duration of generated audio")
    model_used: str = Field(..., description="TTS model that was used")
    processing_time_ms: float = Field(..., description="Time taken to generate audio")


class TTSStreamRequest(BaseModel):
    """Schema for streaming TTS request (WebSocket)."""

    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: uuid.UUID
    model: Literal["svara", "xtts", "chatterbox", "orpheus"] = "svara"
    language: str = "hi"
    emotion: Optional[str] = None
    speaker_gender: Literal["male", "female"] = "female"


class TTSStreamChunk(BaseModel):
    """Schema for streaming TTS audio chunk."""

    chunk_index: int
    audio_base64: str
    is_final: bool
    sample_rate: int = 24000


class TTSStreamStart(BaseModel):
    """Schema for stream start message."""

    type: Literal["start"] = "start"
    voice_id: uuid.UUID
    model: str
    sample_rate: int


class TTSStreamEnd(BaseModel):
    """Schema for stream end message."""

    type: Literal["end"] = "end"
    total_chunks: int
    total_duration_seconds: float
    processing_time_ms: float


class TTSStreamError(BaseModel):
    """Schema for stream error message."""

    type: Literal["error"] = "error"
    error: str
    code: str
