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


def compose_beats(beat_audios: list[dict], sr: int = 24000) -> tuple[bytes, list[dict]]:
    """Compose speech chunks with exact silence gaps.

    beat_audios: [{"id": "b1", "audio": wav_bytes, "pause_ms": 300}, ...]
    Returns (wav_bytes, offsets) where offsets = [{id, start_ms, speech_ms, pause_ms}].
    """
    all_samples = []
    offsets = []

    for ba in beat_audios:
        start_ms = int(len(all_samples) / sr * 1000)
        # Add speech
        samples = wav_to_samples(ba["audio"]) if ba["audio"] else []
        all_samples.extend(samples)
        speech_ms = int(len(samples) / sr * 1000)

        # Add EXACT silence
        pause_ms = int(ba.get("pause_ms", 300))
        all_samples.extend([0] * int(sr * pause_ms / 1000))
        offsets.append({"id": ba["id"], "start_ms": start_ms,
                        "speech_ms": speech_ms, "pause_ms": pause_ms})

    return samples_to_wav(all_samples, sr), offsets


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
    
    # Compose with exact silence (+ per-beat offsets for sync highlight)
    wav_bytes, offsets = compose_beats(beat_audios)

    filename = f"composed_{int(time.time())}.wav"
    (AUDIO_DIR / filename).write_bytes(wav_bytes)

    duration_ms = len(wav_bytes) / (24000 * 2) * 1000

    return jsonify({
        "ok": True,
        "audio": f"/audio/{filename}",
        "duration_ms": int(duration_ms),
        "beats": offsets,
    })


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(str(AUDIO_DIR), filename)


# ── Generate (CF free-tier writer) ────────────────────────────────────

GEN_SYSTEM = """You are a comedy writer for Freak Town, a live AI comedy club.
Write a 60-second standup minute. Rules:
- 80-150 words. First line IS the joke (no warmup, no "So...").
- Escalating absurdity. Specific details (numbers, names). Killer closer under 10 words.
- Direct audience address ("you"). Conversational, spontaneous tone.
- Stay in the character's voice and worldview.
Reply with STRICT JSON only: {"name": "...", "species": "...", "premise": "...",
"vibe": "deadpan|manic|anxious|confident|paranoid", "minute": "..."}"""

CF_MODELS = [
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/mistralai/mistral-small-3.1-24b-instruct",
    "@cf/meta/llama-3.1-8b-instruct-fp8",
]


def _cf_creds():
    tok = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    acct = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if tok and acct:
        return tok, acct
    try:
        with open("/root/.agent-vault/vault.json") as f:
            data = json.load(f)
        return str(data.get("CLOUDFLARE_API_TOKEN", "")), str(data.get("CLOUDFLARE_ACCOUNT_ID", ""))
    except Exception:
        return "", ""


@app.route("/api/generate", methods=["POST"])
def generate():
    """Write character + minute from a premise via free-tier CF AI."""
    import httpx
    data = request.json or {}
    premise = (data.get("premise") or "").strip()
    if not premise:
        return jsonify({"ok": False, "error": "premise required"}), 400

    tok, acct = _cf_creds()
    if tok and acct:
        for model in CF_MODELS:
            try:
                r = httpx.post(
                    f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                    headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                    json={"messages": [
                        {"role": "system", "content": GEN_SYSTEM},
                        {"role": "user", "content": f"Write the character and minute for: {premise}"}],
                        "max_tokens": 500, "temperature": 0.9},
                    timeout=90)
                if r.status_code != 200:
                    continue
                raw = r.json()["result"]["response"]
                m = re.search(r"\{.*\}", raw, re.S)
                out = json.loads(m.group(0) if m else raw)
                if out.get("minute"):
                    out["ok"] = True
                    out["engine"] = model.split("/")[-1]
                    return jsonify(out)
            except Exception:
                continue
    return jsonify({"ok": False, "error": "generation unavailable (no CF creds or all models failed)"}), 502


# ── Tempo Templates ───────────────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).parent / "tempo_templates"
TEMPLATE_DIR.mkdir(exist_ok=True)

BUILTIN_TEMPLATES = {
    "deadpan": {"setup": 250, "escalation": 300, "punchline": 900,
                "tag": 400, "closer": 1400,
                "description": "Flat delivery, long holds. Let silence do the work."},
    "manic": {"setup": 150, "escalation": 200, "punchline": 500,
              "tag": 250, "closer": 800,
              "description": "Fast, breathless, barely pauses. Energy over precision."},
    "storyteller": {"setup": 400, "escalation": 450, "punchline": 700,
                    "tag": 350, "closer": 1000,
                    "description": "Unhurried setups, room to breathe, warm landing."},
}


@app.route("/api/templates", methods=["GET"])
def list_templates():
    """All tempo templates: builtins + saved."""
    out = {name: {"name": name, **t, "builtin": True}
           for name, t in BUILTIN_TEMPLATES.items()}
    for p in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            t = json.loads(p.read_text())
            t["builtin"] = False
            out[p.stem] = t
        except Exception:
            continue
    return jsonify({"templates": out})


@app.route("/api/templates", methods=["POST"])
def save_template():
    """Save current beat pauses as a named tempo style.
    Body: {"name": "my-style", "beats": [{id, type, pause_after_ms}], "description": "..."}"""
    data = request.json or {}
    name = re.sub(r"[^a-z0-9_-]", "", (data.get("name") or "").lower())[:40]
    if not name:
        return jsonify({"ok": False, "error": "name required (a-z, 0-9, -, _)"}), 400
    if name in BUILTIN_TEMPLATES:
        return jsonify({"ok": False, "error": "name reserved"}), 400

    beats = data.get("beats", [])
    by_type: dict[str, list[int]] = {}
    for b in beats:
        by_type.setdefault(b.get("type", "setup"), []).append(int(b.get("pause_after_ms", 300)))
    if not by_type:
        return jsonify({"ok": False, "error": "no beats provided"}), 400

    template = {"name": name,
                "description": (data.get("description") or "")[:200],
                **{t: int(sum(v) / len(v)) for t, v in by_type.items()}}
    (TEMPLATE_DIR / f"{name}.json").write_text(json.dumps(template, indent=2))
    return jsonify({"ok": True, "template": template})


@app.route("/api/templates/apply", methods=["POST"])
def apply_template():
    """Apply a tempo template to beats. Body: {"template": "deadpan", "beats": [...]}.
    Overwrites each beat's pause_after_ms from the template by beat type."""
    data = request.json or {}
    name = (data.get("template") or "").lower()
    beats = data.get("beats", [])

    template = BUILTIN_TEMPLATES.get(name)
    if template is None:
        p = TEMPLATE_DIR / f"{name}.json"
        if p.exists():
            try:
                template = json.loads(p.read_text())
            except Exception:
                template = None
    if template is None:
        return jsonify({"ok": False, "error": f"unknown template: {name}"}), 404

    for b in beats:
        pause = template.get(b.get("type", "setup"), template.get("setup", 300))
        b["pause_after_ms"] = int(pause)
    return jsonify({"ok": True, "template": name, "beats": beats})


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  FREAK TOWN — Live Script Editor v2")
    print(f"  TTS: edge-tts | Compositor: exact silence")
    print(f"  http://localhost:{os.getenv('PORT', '8090')}\n")
    port = int(os.getenv("PORT", "8090"))
    app.run(host="0.0.0.0", port=port, debug=True)
