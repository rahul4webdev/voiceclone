# Modal.com TTS Service Deployment Guide

This guide explains how to deploy the TTS inference service to Modal.com.

## Prerequisites

1. **Modal.com Account**: Sign up at [modal.com](https://modal.com)
2. **Python 3.10+**: Installed on your local machine
3. **Modal CLI**: Install with `pip install modal`

## Step 1: Authenticate with Modal

```bash
# Install Modal CLI
pip install modal

# Authenticate (opens browser for login)
modal token new
```

This will open your browser to authenticate. After authentication, your credentials are stored locally.

## Step 2: Verify Authentication

```bash
# Check your Modal setup
modal profile current

# You should see your workspace name
```

## Step 3: Deploy the TTS Service

Navigate to the `modal_inference` directory and deploy:

```bash
cd modal_inference

# Deploy the service
modal deploy tts_service.py
```

### Expected Output

```
✓ Created objects.
├── 🔨 Created mount /root/voiceclone/modal_inference/tts_service.py
├── 🔨 Created function synthesize.
├── 🔨 Created TTSService.
└── 🔨 Created web endpoint https://your-workspace--voiceclone-tts-synthesize.modal.run

View app at https://modal.com/apps/your-workspace/voiceclone-tts
```

**Important**: Copy the web endpoint URL - you'll need it for the VPS configuration.

## Step 4: Get Your Endpoint URL

After deployment, Modal provides a URL like:
```
https://your-workspace--voiceclone-tts-synthesize.modal.run
```

This is your `MODAL_TTS_ENDPOINT` for the VPS configuration.

## Step 5: Test the Deployment

### Test via CLI

```bash
# Run the local entrypoint to test
modal run tts_service.py
```

### Test via HTTP

```bash
# Test Orpheus (doesn't require reference audio)
curl -X POST "https://your-workspace--voiceclone-tts-synthesize.modal.run" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "orpheus",
    "text": "Hello, this is a test of the Orpheus text to speech model.",
    "voice": "tara",
    "emotion": "happy"
  }'
```

## Step 6: Configure VPS

Add the Modal endpoint to your VPS `.env` file:

```bash
MODAL_TTS_ENDPOINT=https://your-workspace--voiceclone-tts-synthesize.modal.run
```

## GPU Selection

The default configuration uses `A10G` GPU. You can modify this in `tts_service.py`:

| GPU | VRAM | Cost/hr | Use Case |
|-----|------|---------|----------|
| `T4` | 16GB | ~$0.59 | Testing, low volume |
| `A10G` | 24GB | ~$1.10 | **Recommended** - Good balance |
| `A100` | 40GB | ~$2.10 | High volume, lowest latency |
| `H100` | 80GB | ~$3.95 | Maximum performance |

To change GPU, edit the `@app.cls` decorator:

```python
@app.cls(
    image=tts_image,
    gpu="T4",  # Change this
    timeout=300,
    container_idle_timeout=60,
)
```

## Monitoring & Logs

### View Logs

```bash
# View recent logs
modal app logs voiceclone-tts

# Stream logs in real-time
modal app logs voiceclone-tts --follow
```

### View in Dashboard

Visit [modal.com/apps](https://modal.com/apps) to see:
- Request count and latency
- GPU utilization
- Error rates
- Cost breakdown

## Cost Optimization

### Container Idle Timeout

The `container_idle_timeout=60` setting means containers stay warm for 60 seconds after the last request. Adjust based on your traffic:

- **High traffic**: Increase to 120-300 seconds (reduces cold starts)
- **Low traffic**: Decrease to 30 seconds (reduces idle costs)

### Cold Start Behavior

First request after idle period takes ~30-60 seconds (model loading). Subsequent requests are fast (~200ms).

To minimize cold starts:
1. Increase `container_idle_timeout`
2. Use Modal's `keep_warm` feature for always-on:

```python
@app.cls(
    gpu="A10G",
    keep_warm=1,  # Keep 1 container always running
)
```

**Note**: `keep_warm` incurs continuous charges.

## Updating the Service

To update after code changes:

```bash
cd modal_inference
modal deploy tts_service.py
```

Modal handles zero-downtime deployments automatically.

## Secrets Management (Optional)

For sensitive configuration, use Modal secrets:

```bash
# Create a secret
modal secret create voiceclone-config \
  --key API_KEY=your-api-key

# Use in code
@app.cls(
    secrets=[modal.Secret.from_name("voiceclone-config")],
)
```

## Troubleshooting

### "GPU quota exceeded"

Modal has usage limits. Check your quota at [modal.com/settings/usage](https://modal.com/settings/usage).

### "Module not found" errors

Ensure all dependencies are in the Modal image:

```python
tts_image = (
    modal.Image.debian_slim()
    .pip_install("your-package")  # Add missing packages
)
```

### Slow first request

This is expected (cold start). Use `keep_warm=1` for production.

### Out of memory

Try a larger GPU or reduce batch size.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Modal.com                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    voiceclone-tts App                        │ │
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐   │ │
│  │  │ Web Endpoint    │  │ TTSService Class                │   │ │
│  │  │ /synthesize     │──│ - Chatterbox Model (GPU)        │   │ │
│  │  │                 │  │ - Orpheus Model (GPU)           │   │ │
│  │  └─────────────────┘  │ - Model Volume Cache            │   │ │
│  │                       └─────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                               ▲                                  │
└───────────────────────────────│──────────────────────────────────┘
                                │ HTTPS
                                │
┌───────────────────────────────│──────────────────────────────────┐
│                         Your VPS                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    VoiceClone API                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │ │
│  │  │ Voice Store │  │ TTS Client  │──│ WebSocket Streaming │  │ │
│  │  │ (PostgreSQL)│  │             │  │                     │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Next Steps

1. Deploy the TTS service: `modal deploy tts_service.py`
2. Copy the endpoint URL
3. Configure your VPS with the endpoint
4. Test end-to-end with a voice clone

For VPS deployment, see [VPS_DEPLOYMENT.md](./VPS_DEPLOYMENT.md).
