"""API v1 router combining all endpoints."""

from fastapi import APIRouter

from voiceclone.api.v1.tts import router as tts_router
from voiceclone.api.v1.voices import router as voices_router

router = APIRouter(prefix="/api/v1")

# Include all v1 routers
router.include_router(voices_router)
router.include_router(tts_router)
