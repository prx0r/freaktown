#!/usr/bin/env python3
"""Freak Town — Live Script Editor v2.

TTS provider with exact timing control.
Audio compositor owns silence. TTS just speaks.

  python app.py
  open http://localhost:8080
"""

import asyncio
import json
import os
import re
import struct
import subprocess
import time
import wave
from pathlib import Path

from flask import Flask, send_from_directory, jsonify, request

app = Flask(__name__)

AUDIO_DIR = Path(__file__).parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

# ── Provider (edge-tts now, Qwen later) ────────────────────────────

async def tts_generate(text: str, voice: str = "en-US-AriaNeural") -> bytes:
    """Generate speech as WAV bytes."""
    import edge_tts
    
    tmp_mp3 = AUDIO_DIR / f"_tmp_{hash(text) % 100000}.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(tmp_mp3))
    
    tmp_wav = AUDIO_DIR / f"_tmp_{hash(text) % 100000}.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(tmp_mp3),
        "-ar", "24000", "-ac", "1", "-f", "wav", str(tmp_wav)
    ], capture_output=True, timeout=10)
    
    wav_bytes = tmp_wav.read_bytes() if tmp_wav.exists() else b""
    tmp_mp3.unlink(missing_ok=True)
    tmp_wav.unlink(missing_ok=True)
    return wav_bytes


# ── Compositor ──────────────────────────────────────────────────────

def wav_to_samples(wav_bytes: bytes) -> list[int]:
    """Extract samples from WAV."""
    try:
        with wave.open(__import__('io').BytesIO(wav_bytes), 'rb') as w:
            frames = w.readframes(w.getnframes())
            return list(struct.unpack(f'<{len(frames)//2}h', frames))
    except Exception:
        return []


def samples_to_wav(samples: list[int], sr: int = 24000) -> bytes:
    """Convert samples to WAV."""
    buf = __import__('io').BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    return buf.getvalue()


def compose_beats(beat_audios: list[dict], sr: int = 24000) -> bytes:
    """Compose speech chunks with exact silence gaps.
    
    beat_audios: [{"id": "b1", "audio": wav_bytes, "pause_ms": 300}, ...]
    """
    all_samples = []
    
    for ba in beat_audios:
        # Add speech
        if ba["audio"]:
            samples = wav_to_samples(ba["audio"])
            all_samples.extend(samples)
        
        # Add EXACT silence
        silence = int(sr * ba.get("pause_ms", 300) / 1000)
        all_samples.extend([0] * silence)
    
    return samples_to_wav(all_samples, sr)


# ── Beat Detection ──────────────────────────────────────────────────

def detect_beats(text: str) -> list[dict]:
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    beats = []
    
    for i, sent in enumerate(sentences):
        words = sent.split()
        wc = len(words)
        
        beat_type = "setup"
        pause_ms = 300
        stage = "normal"
        sound = "none"
        
        if i > 0 and wc < 8 and len(sentences[i-1].split()) > 15:
            beat_type = "punchline"
            pause_ms = 800
            stage = "hold"
            sound = "rimshot"
        
        if i == len(sentences) - 1:
            beat_type = "closer"
            pause_ms = 1200 if wc < 10 else 600
            stage = "hold"
        
        if i > 0 and beats and beats[-1]["type"] == "punchline" and wc < 12:
            beat_type = "tag"
            pause_ms = 400
        
        beats.append({
            "id": f"b{i+1}",
            "type": beat_type,
            "text": sent,
            "pause_after_ms": pause_ms,
            "stage": stage,
            "sound": sound,
            "word_count": wc,
        })
    
    return beats


# ── Routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "editor.html")


@app.route("/api/parse", methods=["POST"])
def parse_script():
    data = request.json
    text = data.get("text", "")
    beats = detect_beats(text)
    return jsonify({"beats": beats})


@app.route("/api/tts", methods=["POST"])
def tts():
    """Generate TTS for a single beat."""
    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "en-US-AriaNeural")
    beat_id = data.get("beat_id", "default")
    
    audio = asyncio.run(tts_generate(text, voice))
    if audio:
        filename = f"{beat_id}.wav"
        (AUDIO_DIR / filename).write_bytes(audio)
        return jsonify({"ok": True, "audio": f"/audio/{filename}"})
    return jsonify({"ok": False}), 500


@app.route("/api/compose", methods=["POST"])
def compose():
    """Compose full set with exact timing."""
    data = request.json
    beats = data.get("beats", [])
    voice = data.get("voice", "en-US-AriaNeural")
    
    # Generate TTS for each beat
    beat_audios = []
    for b in beats:
        audio = asyncio.run(tts_generate(b["text"], voice))
        beat_audios.append({
            "id": b["id"],
            "audio": audio,
            "pause_ms": b.get("pause_after_ms", 300),
        })
    
    # Compose with exact silence
    wav_bytes = compose_beats(beat_audios)
    
    filename = f"composed_{int(time.time())}.wav"
    (AUDIO_DIR / filename).write_bytes(wav_bytes)
    
    duration_ms = len(wav_bytes) / (24000 * 2) * 1000
    
    return jsonify({
        "ok": True, 
        "audio": f"/audio/{filename}",
        "duration_ms": int(duration_ms),
    })


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(str(AUDIO_DIR), filename)


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  FREAK TOWN — Live Script Editor v2")
    print(f"  TTS: edge-tts | Compositor: exact silence")
    print(f"  http://localhost:{os.getenv('PORT', '8090')}\n")
    port = int(os.getenv("PORT", "8090"))
    app.run(host="0.0.0.0", port=port, debug=True)
