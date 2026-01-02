"""Modal.com TTS Inference Service with Multilingual Voice Cloning.

Supports:
- XTTS-v2: Multilingual voice cloning (17 languages including Hindi, English)
- Chatterbox: English voice cloning with emotion control
- Orpheus: English emotional TTS with preset voices
"""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Optional

import modal

# Define the Modal app
app = modal.App("voiceclone-tts")

# Supported languages for XTTS-v2
XTTS_SUPPORTED_LANGUAGES = [
    "en",  # English
    "es",  # Spanish
    "fr",  # French
    "de",  # German
    "it",  # Italian
    "pt",  # Portuguese
    "pl",  # Polish
    "tr",  # Turkish
    "ru",  # Russian
    "nl",  # Dutch
    "cs",  # Czech
    "ar",  # Arabic
    "zh-cn",  # Chinese (Simplified)
    "ja",  # Japanese
    "hu",  # Hungarian
    "ko",  # Korean
    "hi",  # Hindi
]

# Define the container image with all dependencies
tts_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "git", "espeak-ng", "libmecab-dev", "mecab-ipadic-utf8")
    .pip_install(
        "torch>=2.1.0",
        "torchaudio>=2.1.0",
        "numpy>=1.26.0",
        "scipy>=1.12.0",
        "soundfile>=0.12.0",
        "transformers>=4.36.0",
        "accelerate>=0.25.0",
        "safetensors>=0.4.0",
        "huggingface_hub",
        "librosa",
        "unidic-lite",  # For Japanese tokenizer
    )
    # Install XTTS-v2 (Coqui TTS) for multilingual voice cloning
    # Using specific version with all dependencies
    .pip_install(
        "TTS==0.22.0",
        "phonemizer",
        "gruut",
    )
    # Install Chatterbox from GitHub (Resemble AI) for English
    .pip_install("git+https://github.com/resemble-ai/chatterbox.git")
    # Install Orpheus dependencies
    .pip_install(
        "snac",
        "einops",
    )
)

# Volume for caching models
model_volume = modal.Volume.from_name("voiceclone-models", create_if_missing=True)
MODEL_CACHE_PATH = "/models"


@app.cls(
    image=tts_image,
    gpu="A10G",  # Good balance of cost and performance
    timeout=300,
    scaledown_window=120,  # Keep warm for 2 minutes
    volumes={MODEL_CACHE_PATH: model_volume},
)
class TTSService:
    """TTS inference service with multilingual support."""

    @modal.enter()
    def load_models(self):
        """Load TTS models when container starts."""
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")

        # Set model cache directory
        os.environ["HF_HOME"] = MODEL_CACHE_PATH
        os.environ["TORCH_HOME"] = MODEL_CACHE_PATH
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE_PATH
        os.environ["COQUI_TOS_AGREED"] = "1"  # Auto-agree to Coqui TOS

        # Load XTTS-v2 model (multilingual)
        print("Loading XTTS-v2 model (multilingual)...")
        try:
            import traceback

            # Set TTS model path and agree to TOS
            os.environ["TTS_HOME"] = MODEL_CACHE_PATH
            os.environ["COQUI_TOS_AGREED"] = "1"

            print(f"Initializing TTS with cache path: {MODEL_CACHE_PATH}")
            print(f"COQUI_TOS_AGREED: {os.environ.get('COQUI_TOS_AGREED')}")

            # Fix for PyTorch 2.6+ weights_only=True default change
            # We need to patch torch.load to use weights_only=False for TTS
            import torch
            import functools
            original_torch_load = torch.load

            @functools.wraps(original_torch_load)
            def patched_torch_load(*args, **kwargs):
                # Force weights_only=False for TTS model loading
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                return original_torch_load(*args, **kwargs)

            torch.load = patched_torch_load

            # Use TTS API
            from TTS.api import TTS

            # Initialize TTS - will download model on first run
            print("Creating TTS instance...")
            tts_instance = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
            print("Moving to GPU...")
            self.xtts = tts_instance.to(self.device)
            self.xtts_sample_rate = 24000

            # Restore original torch.load
            torch.load = original_torch_load

            print("XTTS-v2 model loaded successfully")
            print(f"Supported languages: {XTTS_SUPPORTED_LANGUAGES}")
        except Exception as e:
            import traceback
            print(f"Failed to load XTTS-v2: {e}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            self.xtts = None

        # Load Chatterbox model (English only, but good quality)
        print("Loading Chatterbox model...")
        try:
            from chatterbox.tts import ChatterboxTTS

            self.chatterbox = ChatterboxTTS.from_pretrained(device=self.device)
            self.chatterbox_sample_rate = 24000
            print("Chatterbox model loaded successfully (English only)")
        except Exception as e:
            print(f"Failed to load Chatterbox: {e}")
            self.chatterbox = None

        # Load Orpheus model
        print("Loading Orpheus model...")
        try:
            from orpheus_inference import OrpheusInference

            self.orpheus = OrpheusInference(device=self.device)
            self.orpheus_sample_rate = 24000
            print("Orpheus model loaded successfully")
        except ImportError:
            # Orpheus not installed as package, try loading directly
            try:
                self._load_orpheus_direct()
            except Exception as e:
                print(f"Failed to load Orpheus: {e}")
                self.orpheus = None
        except Exception as e:
            print(f"Failed to load Orpheus: {e}")
            self.orpheus = None

    def _load_orpheus_direct(self):
        """Load Orpheus model directly from HuggingFace."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print("Loading Orpheus from HuggingFace...")
        model_name = "canopylabs/orpheus-tts-0.1-finetune-prod"

        self.orpheus_tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.orpheus_model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map=self.device,
        )

        # Load SNAC decoder for audio
        import snac
        self.snac_model = snac.SNAC.from_pretrained("hubertsiuzdak/snac_24khz").to(self.device)

        self.orpheus = "direct"  # Flag that we're using direct loading
        self.orpheus_sample_rate = 24000
        print("Orpheus loaded from HuggingFace successfully")

    @modal.method()
    def synthesize_xtts(
        self,
        text: str,
        audio_prompt_base64: str,
        language: str = "en",
    ) -> dict:
        """Synthesize speech using XTTS-v2 model (multilingual).

        Args:
            text: Text to synthesize
            audio_prompt_base64: Base64 encoded reference audio (WAV format)
            language: Language code (en, hi, es, fr, de, etc.)

        Returns:
            Dictionary with base64 encoded audio and metadata
        """
        import soundfile as sf
        import tempfile
        import numpy as np

        if self.xtts is None:
            return {"error": "XTTS-v2 model not loaded"}

        # Validate language
        if language not in XTTS_SUPPORTED_LANGUAGES:
            return {
                "error": f"Unsupported language: {language}. Supported: {XTTS_SUPPORTED_LANGUAGES}"
            }

        start_time = time.time()

        # Decode reference audio
        audio_bytes = base64.b64decode(audio_prompt_base64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            audio_prompt_path = tmp.name

        try:
            # Generate speech with voice cloning
            wav = self.xtts.tts(
                text=text,
                speaker_wav=audio_prompt_path,
                language=language,
            )

            # Convert to numpy array if needed
            if not isinstance(wav, np.ndarray):
                wav = np.array(wav)

            # Ensure correct shape
            if wav.ndim > 1:
                wav = wav.squeeze()

            # Encode to base64
            buffer = io.BytesIO()
            sf.write(buffer, wav, self.xtts_sample_rate, format="WAV")
            buffer.seek(0)
            audio_base64 = base64.b64encode(buffer.read()).decode("utf-8")

            processing_time = (time.time() - start_time) * 1000
            duration = len(wav) / self.xtts_sample_rate

            return {
                "audio_base64": audio_base64,
                "sample_rate": self.xtts_sample_rate,
                "duration_seconds": duration,
                "processing_time_ms": processing_time,
                "model": "xtts-v2",
                "language": language,
            }

        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}
        finally:
            os.unlink(audio_prompt_path)

    @modal.method()
    def synthesize_chatterbox(
        self,
        text: str,
        audio_prompt_base64: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
    ) -> dict:
        """Synthesize speech using Chatterbox model (English only).

        Args:
            text: Text to synthesize
            audio_prompt_base64: Base64 encoded reference audio (WAV format)
            exaggeration: Emotion exaggeration factor (0.0-1.0+)
            cfg_weight: Classifier-free guidance weight (0.0-1.0)

        Returns:
            Dictionary with base64 encoded audio and metadata
        """
        import soundfile as sf
        import tempfile

        if self.chatterbox is None:
            return {"error": "Chatterbox model not loaded"}

        start_time = time.time()

        # Decode reference audio
        audio_bytes = base64.b64decode(audio_prompt_base64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            audio_prompt_path = tmp.name

        try:
            # Generate speech
            wav = self.chatterbox.generate(
                text=text,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

            # Convert to numpy if tensor
            if hasattr(wav, "cpu"):
                wav = wav.cpu().numpy()

            # Ensure correct shape
            if wav.ndim > 1:
                wav = wav.squeeze()

            # Encode to base64
            buffer = io.BytesIO()
            sf.write(buffer, wav, self.chatterbox_sample_rate, format="WAV")
            buffer.seek(0)
            audio_base64 = base64.b64encode(buffer.read()).decode("utf-8")

            processing_time = (time.time() - start_time) * 1000
            duration = len(wav) / self.chatterbox_sample_rate

            return {
                "audio_base64": audio_base64,
                "sample_rate": self.chatterbox_sample_rate,
                "duration_seconds": duration,
                "processing_time_ms": processing_time,
                "model": "chatterbox",
                "language": "en",
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            os.unlink(audio_prompt_path)

    @modal.method()
    def synthesize_orpheus(
        self,
        text: str,
        voice: str = "tara",
        emotion: Optional[str] = None,
    ) -> dict:
        """Synthesize speech using Orpheus model (English only).

        Args:
            text: Text to synthesize
            voice: Voice ID (tara, leah, jess, leo, dan, mia, zac, zoe)
            emotion: Optional emotion tag (happy, sad, angry, surprised, neutral)

        Returns:
            Dictionary with base64 encoded audio and metadata
        """
        import soundfile as sf
        import numpy as np

        if self.orpheus is None:
            return {"error": "Orpheus model not loaded"}

        start_time = time.time()

        try:
            # Prepend emotion tag if specified
            if emotion:
                text = f"[{emotion}] {text}"

            if self.orpheus == "direct":
                # Use direct HuggingFace loading
                wav = self._generate_orpheus_direct(text, voice)
            else:
                # Use orpheus package
                audio_chunks = []
                for chunk in self.orpheus.generate_speech(
                    prompt=text,
                    voice=voice,
                ):
                    if isinstance(chunk, tuple):
                        sr, audio = chunk
                    else:
                        audio = chunk
                    audio_chunks.append(audio)
                wav = np.concatenate(audio_chunks)

            # Encode to base64
            buffer = io.BytesIO()
            sf.write(buffer, wav, self.orpheus_sample_rate, format="WAV")
            buffer.seek(0)
            audio_base64 = base64.b64encode(buffer.read()).decode("utf-8")

            processing_time = (time.time() - start_time) * 1000
            duration = len(wav) / self.orpheus_sample_rate

            return {
                "audio_base64": audio_base64,
                "sample_rate": self.orpheus_sample_rate,
                "duration_seconds": duration,
                "processing_time_ms": processing_time,
                "model": "orpheus",
                "language": "en",
            }

        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}

    def _generate_orpheus_direct(self, text: str, voice: str) -> "np.ndarray":
        """Generate audio using direct Orpheus model loading."""
        import torch
        import numpy as np

        # Format prompt for Orpheus
        prompt = f"{voice}: {text}"

        # Tokenize
        inputs = self.orpheus_tokenizer(prompt, return_tensors="pt").to(self.device)

        # Generate
        with torch.no_grad():
            outputs = self.orpheus_model.generate(
                **inputs,
                max_new_tokens=1200,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
            )

        # Extract audio tokens (skip text tokens)
        audio_tokens = outputs[0][inputs.input_ids.shape[1]:]

        # Decode with SNAC
        # Reshape tokens for SNAC (3 codebooks)
        num_frames = len(audio_tokens) // 3
        audio_tokens = audio_tokens[:num_frames * 3].reshape(1, 3, num_frames)

        with torch.no_grad():
            audio = self.snac_model.decode(audio_tokens)

        return audio.squeeze().cpu().numpy()

    @modal.method()
    def health_check(self) -> dict:
        """Check service health and model availability."""
        return {
            "status": "healthy",
            "xtts_loaded": self.xtts is not None,
            "chatterbox_loaded": self.chatterbox is not None,
            "orpheus_loaded": self.orpheus is not None,
            "device": self.device,
            "supported_languages": XTTS_SUPPORTED_LANGUAGES,
        }

    @modal.method()
    def get_supported_languages(self) -> dict:
        """Get list of supported languages."""
        return {
            "xtts": XTTS_SUPPORTED_LANGUAGES,
            "chatterbox": ["en"],
            "orpheus": ["en"],
        }


# Web endpoint for HTTP access
@app.function(
    image=tts_image,
    gpu="A10G",
    timeout=300,
    scaledown_window=120,
    volumes={MODEL_CACHE_PATH: model_volume},
)
@modal.fastapi_endpoint(method="POST")
def synthesize(request: dict) -> dict:
    """HTTP endpoint for TTS synthesis.

    Request body:
    {
        "text": "Text to synthesize",
        "model": "xtts" (multilingual), "chatterbox" (English), or "orpheus" (English),
        "audio_prompt_base64": "base64 encoded WAV audio" (required for xtts/chatterbox),
        "language": "hi" (for xtts, default: en),
        "voice": "tara" (for orpheus, default: tara),
        "emotion": "happy" (optional, for orpheus),
        "exaggeration": 0.5 (optional, for chatterbox),
        "cfg_weight": 0.5 (optional, for chatterbox)
    }

    Returns:
    {
        "audio_base64": "base64 encoded WAV audio",
        "sample_rate": 24000,
        "duration_seconds": 1.5,
        "processing_time_ms": 500,
        "model": "xtts-v2",
        "language": "hi"
    }
    """
    service = TTSService()

    model = request.get("model", "xtts")  # Default to multilingual model
    text = request.get("text", "")

    if not text:
        return {"error": "Text is required"}

    if model == "xtts":
        audio_prompt = request.get("audio_prompt_base64")
        if not audio_prompt:
            return {"error": "audio_prompt_base64 is required for xtts model"}

        return service.synthesize_xtts.remote(
            text=text,
            audio_prompt_base64=audio_prompt,
            language=request.get("language", "en"),
        )

    elif model == "chatterbox":
        audio_prompt = request.get("audio_prompt_base64")
        if not audio_prompt:
            return {"error": "audio_prompt_base64 is required for chatterbox model"}

        return service.synthesize_chatterbox.remote(
            text=text,
            audio_prompt_base64=audio_prompt,
            exaggeration=request.get("exaggeration", 0.5),
            cfg_weight=request.get("cfg_weight", 0.5),
        )

    elif model == "orpheus":
        return service.synthesize_orpheus.remote(
            text=text,
            voice=request.get("voice", "tara"),
            emotion=request.get("emotion"),
        )

    else:
        return {"error": f"Unknown model: {model}. Use 'xtts' (multilingual), 'chatterbox' (English), or 'orpheus' (English)"}


# Health check endpoint
@app.function(image=tts_image, gpu="A10G", timeout=60, scaledown_window=120, volumes={MODEL_CACHE_PATH: model_volume})
@modal.fastapi_endpoint(method="GET")
def health() -> dict:
    """Health check endpoint."""
    service = TTSService()
    return service.health_check.remote()


# Languages endpoint
@app.function(image=tts_image, timeout=30)
@modal.fastapi_endpoint(method="GET")
def languages() -> dict:
    """Get supported languages for each model."""
    return {
        "xtts": {
            "name": "XTTS-v2",
            "languages": XTTS_SUPPORTED_LANGUAGES,
            "description": "Multilingual voice cloning with 17 languages",
            "requires_audio_prompt": True,
        },
        "chatterbox": {
            "name": "Chatterbox",
            "languages": ["en"],
            "description": "English voice cloning with emotion control",
            "requires_audio_prompt": True,
        },
        "orpheus": {
            "name": "Orpheus",
            "languages": ["en"],
            "description": "English emotional TTS with preset voices",
            "requires_audio_prompt": False,
        },
    }


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test the TTS service locally."""
    service = TTSService()

    # Health check
    print("Checking health...")
    health_status = service.health_check.remote()
    print(f"Health: {health_status}")

    # Test Orpheus (doesn't require reference audio)
    print("\nTesting Orpheus (English)...")
    result = service.synthesize_orpheus.remote(
        text="Hello! This is a test of the Orpheus text to speech model.",
        voice="tara",
        emotion="happy",
    )
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(
            f"Success! Duration: {result['duration_seconds']:.2f}s, "
            f"Processing: {result['processing_time_ms']:.0f}ms"
        )

        # Save test audio
        audio_bytes = base64.b64decode(result["audio_base64"])
        with open("test_orpheus.wav", "wb") as f:
            f.write(audio_bytes)
        print("Saved to test_orpheus.wav")
