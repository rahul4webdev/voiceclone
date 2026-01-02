# VoiceClone - AI Sales Agent Voice Platform

Real-time Text-to-Speech platform with voice cloning for AI sales agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     VPS (FastAPI Gateway)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ REST API     │  │ Voice Store  │  │ WebSocket Manager     │  │
│  │ /api/v1/*    │  │ (PostgreSQL) │  │ (Audio Streaming)     │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Modal.com (GPU Inference)                    │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │ Chatterbox TTS       │  │ Orpheus TTS                      │ │
│  │ (Primary - Quality)  │  │ (Emotional responses)            │ │
│  └──────────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Voice Cloning**: Clone any voice from 5-10 second audio sample
- **Real-time Streaming**: <200ms latency for live conversations
- **Dual Model Support**: Chatterbox (quality) + Orpheus (emotions)
- **Emotion Control**: Support for emotional speech synthesis
- **Scalable**: Serverless GPU inference via Modal.com

## Quick Start

### 1. VPS Deployment

```bash
# Clone and setup
git clone <repo>
cd voiceclone

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Deploy with Docker
docker-compose up -d
```

### 2. Modal.com Setup

```bash
# Install Modal CLI
pip install modal

# Authenticate
modal token new

# Deploy TTS service
cd modal_inference
modal deploy tts_service.py
```

## API Endpoints

### Voice Management
- `POST /api/v1/voices/clone` - Clone a new voice from audio sample
- `GET /api/v1/voices` - List all cloned voices
- `GET /api/v1/voices/{voice_id}` - Get voice details
- `DELETE /api/v1/voices/{voice_id}` - Delete a voice

### Text-to-Speech
- `POST /api/v1/tts/synthesize` - Generate speech (returns audio file)
- `WebSocket /api/v1/tts/stream` - Real-time streaming TTS

## Environment Variables

See `.env.example` for all configuration options.

## License

MIT
