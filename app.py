#!/usr/bin/env python3
"""Freak Town — Live Script Editor.

Single-file web app:
- Shows your script as editable beats
- Play each beat or full set
- Click to edit pauses
- Edit text inline
- Real-time TTS

No database. No framework. Just Flask + edge-tts.

  python app.py
  open http://localhost:8080
"""

import asyncio
import json
import os
import re
import subprocess
import time
from pathlib import Path

from flask import Flask, send_from_directory, jsonify, request

app = Flask(__name__)

AUDIO_DIR = Path(__file__).parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

# ── Beat Detection ──────────────────────────────────────────────────

def detect_beats(text: str) -> list[dict]:
    """Auto-detect comedy beats from raw text."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    beats = []
    
    for i, sent in enumerate(sentences):
        words = sent.split()
        wc = len(words)
        
        beat_type = "setup"
        pause_ms = 300
        stage = "normal"
        sound = "none"
        
        # Punchline: short sentence after long one
        if i > 0 and wc < 8 and len(sentences[i-1].split()) > 15:
            beat_type = "punchline"
            pause_ms = 800
            stage = "hold"
            sound = "rimshot"
        
        # Closer
        if i == len(sentences) - 1:
            beat_type = "closer"
            pause_ms = 1200 if wc < 10 else 600
            stage = "hold"
        
        # Tag: short after punchline
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


# ── TTS ─────────────────────────────────────────────────────────────

def generate_tts(text: str, voice: str = "en-US-AriaNeural", filename: str = None) -> str:
    """Generate TTS audio. Returns filename."""
    if not filename:
        filename = f"beat_{hash(text) % 100000}.mp3"
    
    out_path = AUDIO_DIR / filename
    if out_path.exists():
        return filename
    
    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice).save(str(out_path)))
    except Exception as e:
        print(f"TTS error: {e}")
        return None
    
    return filename


# ── Routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "editor.html")


@app.route("/api/parse", methods=["POST"])
def parse_script():
    """Parse raw text into beats."""
    data = request.json
    text = data.get("text", "")
    beats = detect_beats(text)
    return jsonify({"beats": beats})


@app.route("/api/tts", methods=["POST"])
def tts():
    """Generate TTS for a beat."""
    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "en-US-AriaNeural")
    beat_id = data.get("beat_id", "default")
    
    filename = generate_tts(text, voice, f"{beat_id}.mp3")
    if filename:
        return jsonify({"ok": True, "audio": f"/audio/{filename}"})
    return jsonify({"ok": False}), 500


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(str(AUDIO_DIR), filename)


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  FREAK TOWN — Live Script Editor")
    print(f"  http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
