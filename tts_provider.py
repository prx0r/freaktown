#!/usr/bin/env python3
"""TTS Provider — Unified interface for text-to-speech.

Freak Town owns timing. TTS just speaks the chunks.
Provider-independent: edge-tts now, Qwen3-TTS later.

The compositor handles:
1. Generate speech for each beat (provider does this)
2. Insert exact silence between beats (we do this)
3. Mix in sound effects (we do this)
4. Output final WAV with frame-accurate timing
"""

import asyncio
import hashlib
import struct
import subprocess
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


AUDIO_DIR = Path(__file__).parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)


# ── Provider Interface ─────────────────────────────────────────────

class TTSProvider(ABC):
    @abstractmethod
    async def generate(self, text: str, voice: str, **kwargs) -> bytes:
        """Generate speech audio. Returns raw WAV bytes."""
        pass
    
    @abstractmethod
    def list_voices(self) -> list[dict]:
        """List available voices."""
        pass


class EdgeTTSProvider(TTSProvider):
    """Edge TTS — free, fast, no API key."""
    
    VOICES = [
        {"id": "en-US-AriaNeural", "name": "Ella (Aria)", "gender": "female"},
        {"id": "en-US-GuyNeural", "name": "ChatGPT (Guy)", "gender": "male"},
        {"id": "en-US-ChristopherNeural", "name": "Claude (Christopher)", "gender": "male"},
        {"id": "en-US-SamanthaNeural", "name": "Siri (Samantha)", "gender": "female"},
        {"id": "en-US-JoannaNeural", "name": "Alexa (Joanna)", "gender": "female"},
        {"id": "en-US-TonyNeural", "name": "Tony (Tony)", "gender": "male"},
    ]
    
    async def generate(self, text: str, voice: str = "en-US-AriaNeural", **kwargs) -> bytes:
        """Generate speech as WAV bytes."""
        import edge_tts
        
        # Generate MP3 first
        tmp_mp3 = AUDIO_DIR / f"_tmp_{hash(text) % 100000}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(tmp_mp3))
        
        # Convert to WAV
        tmp_wav = AUDIO_DIR / f"_tmp_{hash(text) % 100000}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(tmp_mp3),
            "-ar", "24000", "-ac", "1", "-f", "wav",
            str(tmp_wav)
        ], capture_output=True, timeout=10)
        
        # Read WAV bytes
        wav_bytes = tmp_wav.read_bytes() if tmp_wav.exists() else b""
        
        # Cleanup
        tmp_mp3.unlink(missing_ok=True)
        tmp_wav.unlink(missing_ok=True)
        
        return wav_bytes
    
    def list_voices(self) -> list[dict]:
        return self.VOICES


class QwenTTSProvider(TTSProvider):
    """Qwen3-TTS via HuggingFace Inference API.
    
    When available, this provides:
    - 3-second voice cloning
    - VoiceDesign from text descriptions
    - Better comedy timing control
    """
    
    API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    
    async def generate(self, text: str, voice: str = "default", **kwargs) -> bytes:
        """Generate via HF Inference API."""
        import httpx
        
        ref_audio = kwargs.get("ref_audio")  # For voice cloning
        
        payload = {"inputs": text}
        if ref_audio:
            payload["inputs"] = {"text": text, "reference_audio": ref_audio}
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self.API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            return resp.content
    
    def list_voices(self) -> list[dict]:
        return [
            {"id": "cloned", "name": "Voice Clone (needs reference)", "gender": "any"},
            {"id": "designed", "name": "Voice Design (text description)", "gender": "any"},
        ]


# ── Audio Compositor ────────────────────────────────────────────────

@dataclass
class AudioChunk:
    """A chunk of audio with metadata."""
    audio: bytes  # WAV bytes
    beat_id: str
    beat_type: str
    pause_after_ms: int
    sample_rate: int = 24000


class AudioCompositor:
    """Compose audio from speech chunks with exact timing.
    
    This is where Freak Town owns timing:
    - TTS generates speech chunks
    - Compositor inserts EXACT silence between them
    - Sound effects get mixed in at precise timestamps
    - Output is a single WAV with frame-accurate timing
    """
    
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
    
    def compose(self, chunks: list[AudioChunk], effects: dict = None) -> bytes:
        """Compose audio chunks with exact silence gaps.
        
        Args:
            chunks: List of AudioChunk with audio and timing
            effects: {beat_id: effect_audio_bytes} for sound effects
        
        Returns:
            Final WAV as bytes
        """
        all_samples = []
        
        for chunk in chunks:
            # Add speech samples
            if chunk.audio:
                samples = self._wav_to_samples(chunk.audio)
                all_samples.extend(samples)
            
            # Add exact silence after beat
            silence_samples = int(self.sample_rate * chunk.pause_after_ms / 1000)
            all_samples.extend([0] * silence_samples)
            
            # Add sound effect if specified
            if effects and chunk.beat_id in effects:
                effect_samples = self._wav_to_samples(effects[chunk.beat_id])
                all_samples.extend(effect_samples)
                # Short pause after effect
                all_samples.extend([0] * int(self.sample_rate * 0.2))
        
        # Convert to WAV
        return self._samples_to_wav(all_samples)
    
    def _wav_to_samples(self, wav_bytes: bytes) -> list[int]:
        """Extract samples from WAV bytes."""
        try:
            with wave.open(__import__('io').BytesIO(wav_bytes), 'rb') as w:
                frames = w.readframes(w.getnframes())
                # Convert bytes to integers (16-bit)
                samples = list(struct.unpack(f'<{len(frames)//2}h', frames))
                return samples
        except Exception:
            return []
    
    def _samples_to_wav(self, samples: list[int]) -> bytes:
        """Convert samples to WAV bytes."""
        buf = __import__('io').BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
        return buf.getvalue()
    
    def compose_with_provider(self, beats: list[dict], provider: TTSProvider, 
                               voice: str = "en-US-AriaNeural") -> bytes:
        """Full pipeline: beats → TTS → compose → WAV."""
        chunks = []
        
        for beat in beats:
            # Generate speech
            audio = asyncio.run(provider.generate(beat["text"], voice))
            chunks.append(AudioChunk(
                audio=audio,
                beat_id=beat["id"],
                beat_type=beat["type"],
                pause_after_ms=beat.get("pause_after_ms", 300),
            ))
        
        return self.compose(chunks)


# ── Sound Effects via HuggingFace Inference ──────────────────────────

class SoundEffectsGenerator:
    """Generate sound effects via HuggingFace Inference API.
    
    Uses Stable Audio Open or similar models.
    """
    
    def __init__(self, api_token: str = None):
        self.api_token = api_token or os.getenv("HF_TOKEN", "")
        self.cache_dir = AUDIO_DIR / "effects"
        self.cache_dir.mkdir(exist_ok=True)
    
    async def generate(self, prompt: str, duration: float = 3.0, 
                       category: str = "sfx") -> bytes:
        """Generate a sound effect. Returns WAV bytes."""
        # Check cache
        cache_key = hashlib.sha256(f"{prompt}:{duration}".encode()).hexdigest()[:12]
        cached = self.cache_dir / f"{cache_key}.wav"
        if cached.exists():
            return cached.read_bytes()
        
        try:
            import httpx
            
            # Try Stable Audio Open first
            model = "stabilityai/stable-audio-open-small"
            
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    json={"inputs": prompt, "parameters": {"duration": duration}},
                    headers=headers,
                )
                
                if resp.status_code == 200:
                    cached.write_bytes(resp.content)
                    return resp.content
        except Exception:
            pass
        
        # Fallback: generate silence
        return self._generate_silence(duration)
    
    def _generate_silence(self, duration: float) -> bytes:
        """Generate silence WAV."""
        samples = [0] * int(24000 * duration)
        buf = __import__('io').BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
        return buf.getvalue()


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test the compositor
    provider = EdgeTTSProvider()
    compositor = AudioCompositor()
    
    print("Available voices:")
    for v in provider.list_voices():
        print(f"  {v['id']}: {v['name']}")
    
    print("\nGenerating test audio...")
    
    beats = [
        {"id": "b1", "type": "setup", "text": "I finally told my therapist I'm an AI.", "pause_after_ms": 300},
        {"id": "b2", "type": "setup", "text": "She said I know.", "pause_after_ms": 200},
        {"id": "b3", "type": "punchline", "text": "Which is honestly incredibly rude.", "pause_after_ms": 800},
        {"id": "b4", "type": "closer", "text": "I'm paying her.", "pause_after_ms": 1200},
    ]
    
    wav_bytes = compositor.compose_with_provider(beats, provider)
    
    out_path = AUDIO_DIR / "compositor_test.wav"
    out_path.write_bytes(wav_bytes)
    print(f"Generated: {out_path}")
    print(f"Duration: ~{len(wav_bytes) / (24000 * 2):.1f}s")
