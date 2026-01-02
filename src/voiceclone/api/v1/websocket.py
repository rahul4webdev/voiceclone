from __future__ import annotations

"""WebSocket endpoints for real-time TTS streaming."""

import asyncio
import json
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from voiceclone.core.database import async_session_maker
from voiceclone.core.logging import get_logger
from voiceclone.schemas.tts import (
    TTSStreamChunk,
    TTSStreamEnd,
    TTSStreamError,
    TTSStreamRequest,
    TTSStreamStart,
)
from voiceclone.services.tts_client import TTSClientError, get_tts_client
from voiceclone.services.voice_service import VoiceNotFoundError, VoiceService

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections for TTS streaming."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("WebSocket connected", client_id=client_id)

    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info("WebSocket disconnected", client_id=client_id)

    async def send_json(self, client_id: str, data: dict) -> None:
        """Send JSON data to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)

    async def send_bytes(self, client_id: str, data: bytes) -> None:
        """Send binary data to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_bytes(data)


manager = ConnectionManager()


async def process_tts_stream(
    client_id: str,
    request: TTSStreamRequest,
    websocket: WebSocket,
) -> None:
    """Process TTS request and stream audio chunks.

    Args:
        client_id: Unique client identifier
        request: TTS stream request data
        websocket: WebSocket connection
    """
    start_time = time.time()
    tts_client = get_tts_client()

    # Get voice service with a new session
    async with async_session_maker() as session:
        voice_service = VoiceService(session)

        # Get voice profile
        try:
            voice = await voice_service.get_voice(request.voice_id)
        except VoiceNotFoundError:
            error = TTSStreamError(
                error=f"Voice not found: {request.voice_id}",
                code="VOICE_NOT_FOUND",
            )
            await websocket.send_json(error.model_dump())
            return

        # Check voice is ready
        if voice.processing_status != "ready":
            error = TTSStreamError(
                error=f"Voice not ready. Status: {voice.processing_status}",
                code="VOICE_NOT_READY",
            )
            await websocket.send_json(error.model_dump())
            return

        # Get audio path
        try:
            audio_path = await voice_service.get_voice_audio_path(request.voice_id)
        except Exception as e:
            error = TTSStreamError(error=str(e), code="AUDIO_PATH_ERROR")
            await websocket.send_json(error.model_dump())
            return

    # Send stream start message
    start_msg = TTSStreamStart(
        voice_id=request.voice_id,
        model=request.model,
        sample_rate=24000,
    )
    await websocket.send_json(start_msg.model_dump())

    # Stream TTS chunks
    total_chunks = 0
    total_duration = 0.0

    try:
        async for chunk in tts_client.stream_synthesis(
            text=request.text,
            model=request.model,
            audio_path=audio_path if request.model == "chatterbox" else None,
            emotion=request.emotion,
        ):
            if "error" in chunk:
                error = TTSStreamError(error=chunk["error"], code="TTS_ERROR")
                await websocket.send_json(error.model_dump())
                return

            if chunk.get("is_final"):
                total_duration = chunk.get("duration_seconds", 0)
                break

            # Send audio chunk
            audio_chunk = TTSStreamChunk(
                chunk_index=chunk["chunk_index"],
                audio_base64=chunk["audio_base64"],
                is_final=False,
                sample_rate=chunk.get("sample_rate", 24000),
            )
            await websocket.send_json(audio_chunk.model_dump())
            total_chunks += 1

    except TTSClientError as e:
        error = TTSStreamError(error=str(e), code="TTS_CLIENT_ERROR")
        await websocket.send_json(error.model_dump())
        return

    # Send stream end message
    processing_time = (time.time() - start_time) * 1000
    end_msg = TTSStreamEnd(
        total_chunks=total_chunks,
        total_duration_seconds=total_duration,
        processing_time_ms=processing_time,
    )
    await websocket.send_json(end_msg.model_dump())

    logger.info(
        "TTS stream completed",
        client_id=client_id,
        chunks=total_chunks,
        duration=total_duration,
        processing_time_ms=processing_time,
    )


@router.websocket("/api/v1/tts/stream")
async def tts_stream_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time TTS streaming.

    Protocol:
    1. Client connects to WebSocket
    2. Client sends JSON request with TTSStreamRequest format
    3. Server sends TTSStreamStart message
    4. Server streams TTSStreamChunk messages with audio data
    5. Server sends TTSStreamEnd message when complete
    6. Connection can be reused for multiple requests

    Example client request:
    {
        "text": "Hello, how can I help you?",
        "voice_id": "uuid-here",
        "model": "chatterbox",
        "emotion": null
    }
    """
    client_id = str(uuid.uuid4())

    await manager.connect(websocket, client_id)

    try:
        while True:
            # Wait for incoming message
            data = await websocket.receive_text()

            try:
                request_data = json.loads(data)
                request = TTSStreamRequest(**request_data)
            except json.JSONDecodeError:
                error = TTSStreamError(error="Invalid JSON", code="INVALID_JSON")
                await websocket.send_json(error.model_dump())
                continue
            except ValidationError as e:
                error = TTSStreamError(
                    error=f"Validation error: {e.errors()}",
                    code="VALIDATION_ERROR",
                )
                await websocket.send_json(error.model_dump())
                continue

            # Process TTS request
            await process_tts_stream(client_id, request, websocket)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
    finally:
        manager.disconnect(client_id)


@router.websocket("/api/v1/tts/stream/binary")
async def tts_stream_binary_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for binary audio streaming.

    Similar to /stream but sends raw audio bytes instead of base64.
    More efficient for real-time playback.

    Protocol:
    1. Client sends JSON text frame with TTSStreamRequest
    2. Server sends JSON text frame with TTSStreamStart
    3. Server sends binary frames with raw PCM audio data
    4. Server sends JSON text frame with TTSStreamEnd
    """
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                request_data = json.loads(data)
                request = TTSStreamRequest(**request_data)
            except (json.JSONDecodeError, ValidationError) as e:
                error = TTSStreamError(error=str(e), code="PARSE_ERROR")
                await websocket.send_json(error.model_dump())
                continue

            # Get voice and audio path (same as above)
            async with async_session_maker() as session:
                voice_service = VoiceService(session)
                try:
                    voice = await voice_service.get_voice(request.voice_id)
                    audio_path = await voice_service.get_voice_audio_path(request.voice_id)
                except Exception as e:
                    error = TTSStreamError(error=str(e), code="VOICE_ERROR")
                    await websocket.send_json(error.model_dump())
                    continue

            if voice.processing_status != "ready":
                error = TTSStreamError(
                    error="Voice not ready",
                    code="VOICE_NOT_READY",
                )
                await websocket.send_json(error.model_dump())
                continue

            # Send start message
            start_msg = TTSStreamStart(
                voice_id=request.voice_id,
                model=request.model,
                sample_rate=24000,
            )
            await websocket.send_json(start_msg.model_dump())

            # Stream binary audio
            tts_client = get_tts_client()
            start_time = time.time()
            total_chunks = 0

            try:
                async for chunk in tts_client.stream_synthesis(
                    text=request.text,
                    model=request.model,
                    audio_path=audio_path if request.model == "chatterbox" else None,
                    emotion=request.emotion,
                ):
                    if "error" in chunk:
                        error = TTSStreamError(error=chunk["error"], code="TTS_ERROR")
                        await websocket.send_json(error.model_dump())
                        break

                    if chunk.get("is_final"):
                        # Send end message
                        end_msg = TTSStreamEnd(
                            total_chunks=total_chunks,
                            total_duration_seconds=chunk.get("duration_seconds", 0),
                            processing_time_ms=(time.time() - start_time) * 1000,
                        )
                        await websocket.send_json(end_msg.model_dump())
                        break

                    # Send raw audio bytes
                    import base64
                    audio_bytes = base64.b64decode(chunk["audio_base64"])
                    await websocket.send_bytes(audio_bytes)
                    total_chunks += 1

            except TTSClientError as e:
                error = TTSStreamError(error=str(e), code="TTS_ERROR")
                await websocket.send_json(error.model_dump())

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(client_id)
