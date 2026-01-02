# VoiceClone API Documentation

## Overview

VoiceClone is a real-time Text-to-Speech platform with voice cloning capabilities, designed for AI sales agents and conversational AI applications.

**Base URL:** `https://voiceclone.gahfaudio.in`

**API Version:** v1

---

## Authentication

Currently, the API is open. For production, add your authentication token:

```
Authorization: Bearer <your-api-token>
```

---

## Available TTS Models

| Model | Languages | Voice Cloning | Best For |
|-------|-----------|---------------|----------|
| `svara` | 19 Indian languages | Yes (optional) | Hindi, Bengali, Tamil, Telugu, etc. |
| `xtts` | 17 languages | Yes (required) | Multilingual content |
| `chatterbox` | English only | Yes (required) | High-quality English |
| `orpheus` | English only | No (preset voices) | Emotional English speech |

---

## REST API Endpoints

### 1. Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "app": "voiceclone",
  "env": "production"
}
```

---

### 2. List Available Models

```http
GET /api/v1/tts/models
```

**Response:**
```json
{
  "models": [
    {
      "id": "svara",
      "name": "svara-TTS",
      "description": "Indian languages TTS with emotion control (19 languages)",
      "supported_languages": ["hi", "bn", "mr", "te", "kn", "ta", "gu", "ml", "pa", ...],
      "emotion_tags": ["happy", "sad", "anger", "fear", "neutral"],
      "requires_reference_audio": false
    },
    ...
  ]
}
```

---

### 3. Create Voice Profile

Before synthesizing speech, create a voice profile with a reference audio sample.

```http
POST /api/v1/voices/
Content-Type: multipart/form-data
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Voice profile name |
| `description` | string | No | Voice description |
| `audio_file` | file | Yes | Reference audio (WAV, MP3, FLAC) - 10-30 seconds recommended |
| `language` | string | No | Primary language (default: "hi") |

**Example (cURL):**
```bash
curl -X POST "https://voiceclone.gahfaudio.in/api/v1/voices/" \
  -F "name=Sales Agent Voice" \
  -F "description=Professional Hindi voice for sales calls" \
  -F "language=hi" \
  -F "audio_file=@reference_audio.wav"
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Sales Agent Voice",
  "description": "Professional Hindi voice for sales calls",
  "language": "hi",
  "processing_status": "ready",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### 4. Synthesize Speech (JSON Response)

```http
POST /api/v1/tts/synthesize
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "नमस्ते, मैं आपकी कैसे मदद कर सकता हूं?",
  "voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "svara",
  "language": "hi",
  "emotion": "happy",
  "speaker_gender": "female",
  "output_format": "wav"
}
```

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to synthesize (max 5000 chars) |
| `voice_id` | uuid | Yes | - | Voice profile ID |
| `model` | string | No | "svara" | TTS model (svara, xtts, chatterbox, orpheus) |
| `language` | string | No | "hi" | Language code |
| `emotion` | string | No | null | Emotion tag (model-specific) |
| `speaker_gender` | string | No | "female" | For svara: "male" or "female" |
| `speed` | float | No | 1.0 | Speech speed (0.5-2.0) |
| `output_format` | string | No | "wav" | Output format (wav, mp3) |

**Response:**
```json
{
  "audio_url": "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAA...",
  "duration_seconds": 2.5,
  "model_used": "svara-tts",
  "processing_time_ms": 850
}
```

**Example (Python):**
```python
import httpx
import base64

async def synthesize_speech(text: str, voice_id: str, language: str = "hi"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://voiceclone.gahfaudio.in/api/v1/tts/synthesize",
            json={
                "text": text,
                "voice_id": voice_id,
                "model": "svara",
                "language": language,
                "emotion": "neutral",
                "speaker_gender": "female"
            },
            timeout=60.0
        )
        result = response.json()

        # Extract base64 audio
        audio_data = result["audio_url"].split(",")[1]
        audio_bytes = base64.b64decode(audio_data)

        return audio_bytes, result["duration_seconds"]
```

---

### 5. Synthesize Speech (Direct Audio Response)

For direct audio streaming without base64 encoding:

```http
POST /api/v1/tts/synthesize/audio
Content-Type: application/json
```

**Request Body:** Same as `/synthesize`

**Response:** Binary audio file with headers:
- `Content-Type: audio/wav` or `audio/mpeg`
- `X-Duration-Seconds: 2.5`
- `X-Processing-Time-Ms: 850`

**Example (Python):**
```python
import httpx

async def get_audio_stream(text: str, voice_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://voiceclone.gahfaudio.in/api/v1/tts/synthesize/audio",
            json={
                "text": text,
                "voice_id": voice_id,
                "model": "svara",
                "language": "hi"
            },
            timeout=60.0
        )

        # Save or stream the audio
        with open("output.wav", "wb") as f:
            f.write(response.content)

        duration = float(response.headers.get("X-Duration-Seconds", 0))
        return duration
```

---

## WebSocket Streaming API

For real-time, low-latency TTS in AI sales agents, use the WebSocket API.

### Connection

```
wss://voiceclone.gahfaudio.in/ws/tts
```

### Message Flow

```
Client                              Server
   |                                   |
   |-- Connect ----------------------->|
   |                                   |
   |-- Synthesis Request ------------->|
   |                                   |
   |<-- Stream Start ------------------|
   |<-- Audio Chunk 1 -----------------|
   |<-- Audio Chunk 2 -----------------|
   |<-- Audio Chunk N -----------------|
   |<-- Stream End --------------------|
   |                                   |
   |-- Close Connection -------------->|
```

### Request Message

```json
{
  "type": "synthesize",
  "text": "नमस्ते, मैं आपकी कैसे मदद कर सकता हूं?",
  "voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "svara",
  "language": "hi",
  "emotion": "happy",
  "speaker_gender": "female"
}
```

### Response Messages

**Stream Start:**
```json
{
  "type": "start",
  "voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "svara-tts",
  "sample_rate": 24000
}
```

**Audio Chunk:**
```json
{
  "type": "chunk",
  "chunk_index": 0,
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAA...",
  "is_final": false,
  "sample_rate": 24000
}
```

**Stream End:**
```json
{
  "type": "end",
  "total_chunks": 5,
  "total_duration_seconds": 2.5,
  "processing_time_ms": 850
}
```

**Error:**
```json
{
  "type": "error",
  "error": "Voice not found",
  "code": "VOICE_NOT_FOUND"
}
```

### WebSocket Client Example (Python)

```python
import asyncio
import websockets
import json
import base64
import wave
import io

class VoiceCloneStreamingClient:
    def __init__(self, base_url: str = "wss://voiceclone.gahfaudio.in"):
        self.ws_url = f"{base_url}/ws/tts"
        self.sample_rate = 24000

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        language: str = "hi",
        model: str = "svara",
        emotion: str = None,
        on_audio_chunk: callable = None
    ):
        """Stream TTS audio chunks in real-time.

        Args:
            text: Text to synthesize
            voice_id: Voice profile ID
            language: Language code
            model: TTS model to use
            emotion: Optional emotion tag
            on_audio_chunk: Callback function for each audio chunk

        Returns:
            Complete audio bytes
        """
        audio_chunks = []

        async with websockets.connect(self.ws_url) as ws:
            # Send synthesis request
            request = {
                "type": "synthesize",
                "text": text,
                "voice_id": voice_id,
                "model": model,
                "language": language,
            }
            if emotion:
                request["emotion"] = emotion

            await ws.send(json.dumps(request))

            # Receive chunks
            while True:
                message = await ws.recv()
                data = json.loads(message)

                if data["type"] == "start":
                    self.sample_rate = data.get("sample_rate", 24000)
                    print(f"Stream started: {data['model']}")

                elif data["type"] == "chunk":
                    chunk_bytes = base64.b64decode(data["audio_base64"])
                    audio_chunks.append(chunk_bytes)

                    # Real-time callback for immediate playback
                    if on_audio_chunk:
                        await on_audio_chunk(chunk_bytes, data["chunk_index"])

                elif data["type"] == "end":
                    print(f"Stream complete: {data['total_duration_seconds']:.2f}s")
                    break

                elif data["type"] == "error":
                    raise Exception(f"TTS Error: {data['error']}")

        return b"".join(audio_chunks)

    def save_audio(self, audio_bytes: bytes, filename: str):
        """Save raw audio bytes to WAV file."""
        with wave.open(filename, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio_bytes)


# Usage Example
async def main():
    client = VoiceCloneStreamingClient()

    # Define callback for real-time audio playback
    async def play_chunk(audio_bytes: bytes, chunk_index: int):
        print(f"Received chunk {chunk_index}: {len(audio_bytes)} bytes")
        # Here you would send to audio player

    # Stream synthesis
    audio = await client.synthesize_stream(
        text="नमस्ते, मैं आपका AI सेल्स एजेंट हूं। आज मैं आपकी कैसे मदद कर सकता हूं?",
        voice_id="your-voice-id-here",
        language="hi",
        model="svara",
        emotion="happy",
        on_audio_chunk=play_chunk
    )

    # Save complete audio
    client.save_audio(audio, "output.wav")

if __name__ == "__main__":
    asyncio.run(main())
```

### WebSocket Client Example (JavaScript/Node.js)

```javascript
const WebSocket = require('ws');

class VoiceCloneClient {
    constructor(baseUrl = 'wss://voiceclone.gahfaudio.in') {
        this.wsUrl = `${baseUrl}/ws/tts`;
    }

    async synthesize(text, voiceId, options = {}) {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(this.wsUrl);
            const audioChunks = [];

            ws.on('open', () => {
                const request = {
                    type: 'synthesize',
                    text: text,
                    voice_id: voiceId,
                    model: options.model || 'svara',
                    language: options.language || 'hi',
                    emotion: options.emotion || null,
                    speaker_gender: options.speakerGender || 'female'
                };
                ws.send(JSON.stringify(request));
            });

            ws.on('message', (data) => {
                const message = JSON.parse(data);

                switch (message.type) {
                    case 'start':
                        console.log(`Stream started: ${message.model}`);
                        break;

                    case 'chunk':
                        const chunk = Buffer.from(message.audio_base64, 'base64');
                        audioChunks.push(chunk);

                        // Emit chunk for real-time playback
                        if (options.onChunk) {
                            options.onChunk(chunk, message.chunk_index);
                        }
                        break;

                    case 'end':
                        console.log(`Complete: ${message.total_duration_seconds}s`);
                        ws.close();
                        resolve({
                            audio: Buffer.concat(audioChunks),
                            duration: message.total_duration_seconds,
                            processingTime: message.processing_time_ms
                        });
                        break;

                    case 'error':
                        ws.close();
                        reject(new Error(message.error));
                        break;
                }
            });

            ws.on('error', reject);
        });
    }
}

// Usage
const client = new VoiceCloneClient();

client.synthesize(
    'नमस्ते, मैं आपका AI सेल्स एजेंट हूं।',
    'your-voice-id',
    {
        model: 'svara',
        language: 'hi',
        emotion: 'happy',
        onChunk: (chunk, index) => {
            console.log(`Chunk ${index}: ${chunk.length} bytes`);
            // Stream to audio player here
        }
    }
).then(result => {
    require('fs').writeFileSync('output.wav', result.audio);
    console.log(`Saved: ${result.duration}s`);
});
```

---

## AI Sales Agent Integration

### Real-Time Conversation Flow

```python
import asyncio
from voiceclone_client import VoiceCloneStreamingClient

class AISalesAgent:
    def __init__(self, voice_id: str):
        self.voice_id = voice_id
        self.tts_client = VoiceCloneStreamingClient()
        self.audio_queue = asyncio.Queue()

    async def speak(self, text: str, emotion: str = "neutral"):
        """Convert agent response to speech and stream to caller."""

        async def stream_to_caller(chunk: bytes, index: int):
            # Add to audio queue for telephony system
            await self.audio_queue.put(chunk)

        await self.tts_client.synthesize_stream(
            text=text,
            voice_id=self.voice_id,
            language="hi",
            model="svara",
            emotion=emotion,
            on_audio_chunk=stream_to_caller
        )

        # Signal end of audio
        await self.audio_queue.put(None)

    async def handle_conversation(self, user_input: str):
        """Process user input and generate spoken response."""

        # Generate response using your LLM
        response_text, detected_emotion = await self.generate_response(user_input)

        # Speak the response with appropriate emotion
        await self.speak(response_text, emotion=detected_emotion)

    async def generate_response(self, user_input: str):
        # Your LLM integration here
        # Returns (response_text, emotion)
        pass


# Example conversation flow
async def sales_call():
    agent = AISalesAgent(voice_id="your-sales-voice-id")

    # Greeting
    await agent.speak(
        "नमस्ते! मैं ABC कंपनी से बोल रहा हूं। क्या आपके पास दो मिनट हैं?",
        emotion="happy"
    )

    # Handle user responses...
    await agent.handle_conversation("हां, बताइए")
```

### Emotion Mapping for Sales

```python
SALES_EMOTION_MAP = {
    # Greeting/Opening
    "greeting": "happy",

    # Product explanation
    "explanation": "neutral",

    # Handling objections
    "objection_handling": "neutral",

    # Urgency/Limited offer
    "urgency": "happy",

    # Empathy/Understanding concerns
    "empathy": "sad",

    # Closing/Call-to-action
    "closing": "happy",

    # Farewell
    "farewell": "happy"
}
```

---

## Language Codes Reference

### svara-TTS (Indian Languages)

| Code | Language |
|------|----------|
| `hi` | Hindi |
| `bn` | Bengali |
| `mr` | Marathi |
| `te` | Telugu |
| `ta` | Tamil |
| `gu` | Gujarati |
| `kn` | Kannada |
| `ml` | Malayalam |
| `pa` | Punjabi |
| `as` | Assamese |
| `or` | Odia |
| `bho` | Bhojpuri |
| `mai` | Maithili |
| `ne` | Nepali |
| `en-in` | Indian English |

### XTTS-v2 (Multilingual)

| Code | Language |
|------|----------|
| `en` | English |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `it` | Italian |
| `pt` | Portuguese |
| `ru` | Russian |
| `zh-cn` | Chinese |
| `ja` | Japanese |
| `ko` | Korean |
| `ar` | Arabic |
| `hi` | Hindi |

---

## Error Codes

| Code | Description |
|------|-------------|
| `VOICE_NOT_FOUND` | Voice profile ID does not exist |
| `VOICE_NOT_READY` | Voice profile is still processing |
| `INVALID_LANGUAGE` | Unsupported language code |
| `INVALID_MODEL` | Unknown TTS model |
| `TEXT_TOO_LONG` | Text exceeds 5000 character limit |
| `TTS_SERVICE_ERROR` | Modal inference service error |
| `AUDIO_FORMAT_ERROR` | Invalid reference audio format |

---

## Rate Limits

| Tier | Requests/Minute | Max Text Length |
|------|-----------------|-----------------|
| Free | 10 | 1000 chars |
| Basic | 60 | 3000 chars |
| Pro | 300 | 5000 chars |
| Enterprise | Unlimited | 10000 chars |

---

## Best Practices

### 1. Voice Sample Quality
- Use 10-30 seconds of clear speech
- Avoid background noise
- Use WAV or FLAC format (lossless)
- Match the language of intended output

### 2. Text Preprocessing
```python
def preprocess_text(text: str) -> str:
    # Normalize numbers
    text = text.replace("₹", "rupees ")

    # Add pauses with punctuation
    text = text.replace("...", ", ")

    # Limit length
    if len(text) > 5000:
        text = text[:5000]

    return text
```

### 3. Streaming for Low Latency
- Use WebSocket API for real-time applications
- Start playing audio as chunks arrive
- Buffer 2-3 chunks before playback for smoothness

### 4. Error Handling
```python
async def safe_synthesize(text, voice_id):
    try:
        return await tts_client.synthesize(text, voice_id)
    except TTSClientError as e:
        if "VOICE_NOT_FOUND" in str(e):
            # Use fallback voice
            return await tts_client.synthesize(text, FALLBACK_VOICE_ID)
        raise
```

---

## Support

- **Documentation:** https://voiceclone.gahfaudio.in/docs
- **API Status:** https://voiceclone.gahfaudio.in/health
- **GitHub:** https://github.com/rahul4webdev/voiceclone
