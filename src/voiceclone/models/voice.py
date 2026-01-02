from __future__ import annotations

"""Voice model for storing cloned voice data."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from voiceclone.core.database import Base


class Voice(Base):
    """Model for storing cloned voice profiles."""

    __tablename__ = "voices"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Original audio file info
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_format: Mapped[str] = mapped_column(String(10), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)

    # Processed audio path (normalized WAV)
    processed_audio_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Voice embeddings stored as JSON
    # For Chatterbox: stores reference to audio file path
    # For Orpheus: stores gpt_cond_latent and speaker_embedding
    chatterbox_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    orpheus_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Metadata
    language: Mapped[str] = mapped_column(String(10), default="en")
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, processing, ready, failed
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<Voice(id={self.id}, name='{self.name}', status='{self.processing_status}')>"
