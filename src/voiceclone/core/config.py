"""Application configuration settings."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "voiceclone"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database (supports both PostgreSQL and SQLite)
    database_url: str = Field(
        default="postgresql://voiceclone:voiceclone@localhost:5432/voiceclone"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Modal.com
    modal_token_id: str = ""
    modal_token_secret: str = ""
    modal_workspace: str = ""
    modal_tts_endpoint: str = ""  # Will be set after Modal deployment

    # Voice Storage
    voice_storage_path: str = "/app/data/voices"
    max_voice_sample_size_mb: int = 50
    allowed_audio_formats: List[str] = Field(
        default=["wav", "mp3", "flac", "ogg", "m4a"]
    )

    # TTS Settings
    default_tts_model: Literal["svara", "chatterbox", "orpheus", "xtts"] = "svara"
    tts_sample_rate: int = 24000
    tts_chunk_size: int = 4096
    max_text_length: int = 5000

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
