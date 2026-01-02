from __future__ import annotations

"""Pydantic schemas for voice-related API operations."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VoiceBase(BaseModel):
    """Base schema for voice data."""

    name: str = Field(..., min_length=1, max_length=255, description="Name for the cloned voice")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    language: str = Field(default="en", max_length=10, description="Language code (e.g., 'en', 'es')")
    tags: Optional[List[str]] = Field(None, description="Optional tags for categorization")


class VoiceCreate(VoiceBase):
    """Schema for creating a new voice (used with file upload)."""

    pass


class VoiceUpdate(BaseModel):
    """Schema for updating voice metadata."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    language: Optional[str] = Field(None, max_length=10)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class VoiceResponse(VoiceBase):
    """Schema for voice response."""

    id: str  # Changed from uuid.UUID to str for SQLite compatibility
    original_filename: str
    original_format: str
    duration_seconds: float
    sample_rate: int
    is_active: bool
    processing_status: str
    processing_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoiceListResponse(BaseModel):
    """Schema for paginated voice list response."""

    items: List[VoiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VoiceCloneRequest(BaseModel):
    """Schema for voice cloning request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="en")
    tags: Optional[List[str]] = None


class VoiceCloneResponse(BaseModel):
    """Schema for voice cloning response."""

    voice_id: str  # Changed from uuid.UUID to str
    status: str
    message: str
