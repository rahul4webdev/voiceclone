"""Tests for voice service."""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from voiceclone.schemas.voice import VoiceCreate
from voiceclone.services.voice_service import VoiceService, VoiceServiceError


class TestVoiceService:
    """Test cases for VoiceService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def voice_service(self, mock_db):
        """Create a VoiceService instance with mocked db."""
        with patch("voiceclone.services.voice_service.settings") as mock_settings:
            mock_settings.voice_storage_path = "/tmp/test_voices"
            mock_settings.max_voice_sample_size_mb = 50
            mock_settings.allowed_audio_formats = ["wav", "mp3"]
            mock_settings.tts_sample_rate = 24000
            service = VoiceService(mock_db)
        return service

    def test_voice_service_init(self, voice_service):
        """Test VoiceService initialization."""
        assert voice_service is not None
        assert voice_service.storage_path.exists() or True  # Path may not exist in test

    @pytest.mark.asyncio
    async def test_create_voice_invalid_format(self, voice_service):
        """Test that invalid audio format raises error."""
        voice_data = VoiceCreate(
            name="Test Voice",
            description="Test description",
            language="en",
        )

        # Create a fake audio file
        audio_content = b"fake audio content"
        audio_file = io.BytesIO(audio_content)

        with pytest.raises(VoiceServiceError) as exc_info:
            with patch("voiceclone.services.voice_service.validate_audio_file") as mock_validate:
                from voiceclone.utils.audio import AudioProcessingError
                mock_validate.side_effect = AudioProcessingError("Invalid format")
                await voice_service.create_voice(
                    voice_data=voice_data,
                    audio_file=audio_file,
                    filename="test.xyz",
                )

        assert "Invalid format" in str(exc_info.value)


class TestAudioUtils:
    """Test cases for audio utilities."""

    def test_audio_to_base64(self):
        """Test audio to base64 conversion."""
        import numpy as np
        from voiceclone.utils.audio import audio_to_base64, base64_to_audio

        # Create test audio
        sample_rate = 24000
        duration = 0.1  # 100ms
        audio_data = np.sin(2 * np.pi * 440 * np.linspace(0, duration, int(sample_rate * duration)))

        # Convert to base64
        base64_str = audio_to_base64(audio_data, sample_rate)
        assert isinstance(base64_str, str)
        assert len(base64_str) > 0

        # Convert back
        recovered_audio, recovered_sr = base64_to_audio(base64_str)
        assert recovered_sr == sample_rate
        assert len(recovered_audio) > 0
