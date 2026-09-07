#!/usr/bin/env python3
"""Freak Town — Live Script Editor v2.

TTS provider with exact timing control.
Audio compositor owns silence. TTS just speaks.

  python app.py
  open http://localhost:8080
"""

import asyncio
import hashlib
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


@app.route("/<path:filename>")
def static_files(filename):
    if filename in ("manifest.json", "sw.js", "icon-192.png",
                    "icon-512.png", "apple-touch-icon.png"):
        return send_from_directory("static", filename)
    return jsonify({"ok": False, "error": "not found"}), 404


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


@app.route("/freaks/<path:filename>")
def serve_freak(filename):
    return send_from_directory(str(FREAK_DIR), filename)


# ── Freak Bundles: saved sets ─────────────────────────────────────────

FREAK_DIR = Path(__file__).parent / "freaks"
FREAK_DIR.mkdir(exist_ok=True)


def _slug(name: str, text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "freak").lower()).strip("-")[:32] or "freak"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


def _bundle_meta(slug: str) -> dict | None:
    meta_path = FREAK_DIR / slug / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception:
        return None


@app.route("/api/sets", methods=["GET"])
def list_sets():
    """Your Sets library: every saved freak bundle with status."""
    out = []
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if not meta:
            continue
        char = meta.get("character", {})
        out.append({
            "slug": d.name,
            "name": char.get("name", d.name),
            "premise": char.get("premise", ""),
            "beats": meta.get("beat_count", 0),
            "words": meta.get("word_count", 0),
            "duration_s": meta.get("duration_s", 0),
            "voice": meta.get("voice", ""),
            "style": meta.get("style", ""),
            "status": meta.get("status", "draft"),
            "created_at": meta.get("created_at", ""),
            "audio": f"/freaks/{d.name}/set.wav" if (d / "set.wav").exists() else None,
        })
    return jsonify({"sets": out})


@app.route("/api/sets", methods=["POST"])
def save_set():
    """Save character + beats + timings + composed clip as one freak bundle.
    Body: {"character": {name,species,premise,vibe}, "beats": [...],
           "voice": "...", "style": "deadpan", "walkout": "funk/absurd/high" }"""
    import datetime
    data = request.json or {}
    character = data.get("character") or {}
    beats = data.get("beats") or []
    voice = data.get("voice", "en-US-AriaNeural")
    if not beats:
        return jsonify({"ok": False, "error": "no beats to save"}), 400

    name = (character.get("name") or "Guest Freak")[:80]
    full_text = " ".join(b.get("text", "") for b in beats)
    slug = _slug(name, full_text + voice)
    bdir = FREAK_DIR / slug
    bdir.mkdir(exist_ok=True)

    # 1. character.json
    (bdir / "character.json").write_text(json.dumps({
        "name": name,
        "species": (character.get("species") or "")[:60],
        "premise": (character.get("premise") or "")[:300],
        "vibe": (character.get("vibe") or "")[:40],
        "voice": voice,
    }, indent=2))

    # 2. delivery.json (freaktown.delivery.v1, timings included)
    (bdir / "delivery.json").write_text(json.dumps({
        "version": "freaktown.delivery.v1",
        "voice": {"provider": "edge-tts", "voice_id": voice},
        "beats": [{"id": b.get("id"), "type": b.get("type", "setup"),
                   "text": b.get("text", ""),
                   "pause_after_ms": int(b.get("pause_after_ms", 300))}
                  for b in beats],
    }, indent=2))

    # 3. set.wav (composed clip with exact silence)
    beat_audios = []
    for b in beats:
        audio = asyncio.run(tts_generate(b.get("text", ""), voice))
        beat_audios.append({"id": b.get("id"), "audio": audio,
                            "pause_ms": int(b.get("pause_after_ms", 300))})
    wav_bytes, offsets = compose_beats(beat_audios)
    (bdir / "set.wav").write_bytes(wav_bytes)

    # 4. walkout.wav (generated now) + walkout.json (recipe)
    walkout = data.get("walkout") or {}
    if walkout.get("genre"):
        import sound_synth
        recipe = {"genre": walkout.get("genre", "funk"), "mood": walkout.get("mood", "confident"),
                  "energy": walkout.get("energy", "high"), "shape": walkout.get("shape", "hit"),
                  "duration": 8}
        seed = int(walkout.get("seed", 0))
        (bdir / "walkout.wav").write_bytes(sound_synth.generate(recipe, seed))
    (bdir / "walkout.json").write_text(json.dumps({
        "genre": walkout.get("genre", ""), "mood": walkout.get("mood", ""),
        "energy": walkout.get("energy", ""), "shape": walkout.get("shape", "hit"),
        "seed": int(walkout.get("seed", 0)),
        "duration": 8, "audio": "walkout.wav" if (bdir / "walkout.wav").exists() else None,
    }, indent=2))

    words = sum(len(b.get("text", "").split()) for b in beats)
    meta = {"slug": slug,
            "character": {"name": name,
                          "species": (character.get("species") or "")[:60],
                          "premise": (character.get("premise") or "")[:300],
                          "vibe": (character.get("vibe") or "")[:40]},
            "voice": voice,
            "style": (data.get("style") or "")[:40],
            "beat_count": len(beats),
            "word_count": words,
            "duration_s": round(len(wav_bytes) / (24000 * 2), 1),
            "status": "draft",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (bdir / "meta.json").write_text(json.dumps(meta, indent=2))
    return jsonify({"ok": True, "slug": slug, "meta": meta,
                    "audio": f"/freaks/{slug}/set.wav"})


@app.route("/api/sets/<slug>", methods=["GET"])
def get_set(slug):
    """Full bundle: character + beats + audio url."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    if not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set"}), 404
    try:
        character = json.loads((bdir / "character.json").read_text())
        delivery = json.loads((bdir / "delivery.json").read_text())
        meta = json.loads((bdir / "meta.json").read_text())
    except Exception:
        return jsonify({"ok": False, "error": "corrupt bundle"}), 500
    return jsonify({"ok": True, "slug": slug, "character": character,
                    "beats": delivery.get("beats", []), "voice": meta.get("voice", ""),
                    "style": meta.get("style", ""), "status": meta.get("status", "draft"),
                    "audio": f"/freaks/{slug}/set.wav" if (bdir / "set.wav").exists() else None})


@app.route("/api/sets/<slug>/submit", methods=["POST"])
def submit_set(slug):
    """Submit a saved set for the live show. Status: draft -> queued."""
    import datetime
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if meta is None:
        return jsonify({"ok": False, "error": "unknown set"}), 404
    if not (bdir / "set.wav").exists():
        return jsonify({"ok": False, "error": "no composed clip yet"}), 400
    meta["status"] = "queued"
    meta["submitted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (bdir / "meta.json").write_text(json.dumps(meta, indent=2))
    return jsonify({"ok": True, "slug": slug, "status": "queued"})


@app.route("/api/walkout", methods=["POST"])
def walkout():
    """Generate (or fetch cached) walkout sting from a recipe.
    Body: {"genre": "funk", "mood": "absurd", "energy": "high", "shape": "hit",
           "duration": 8, "seed": 0} -> {audio, recipe, cached}"""
    import sound_synth
    data = request.json or {}
    recipe = {
        "genre": str(data.get("genre", "funk"))[:20],
        "mood": str(data.get("mood", "confident"))[:20],
        "energy": str(data.get("energy", "high"))[:20],
        "shape": str(data.get("shape", "hit"))[:20],
        "duration": min(11, max(2, float(data.get("duration", 8)))),
    }
    seed = int(data.get("seed", 0))
    rid = sound_synth.recipe_id(recipe, seed)
    wdir = AUDIO_DIR / "walkouts"
    wdir.mkdir(exist_ok=True)
    path = wdir / f"{rid}.wav"
    cached = path.exists()
    if not cached:
        path.write_bytes(sound_synth.generate(recipe, seed))
    return jsonify({"ok": True, "audio": f"/audio/walkouts/{rid}.wav",
                    "recipe": recipe, "seed": seed, "cached": cached})


FREAK_SPECIES = ["moth", "pigeon", "roomba", "dog", "toaster", "goblin",
                 "goldfish", "skeleton", "traffic cone", "fax machine",
                 "goldfish", "crab", "lamp", "elevator"]
FREAK_JOBS = ["divorce lawyer", "driving instructor", "LinkedIn influencer",
              "customer service rep", "landlord", "life coach", "bouncer",
              "weatherman", "dentist", "mall cop", "podcaster", "notary"]
FREAK_VIBES = ["dangerously optimistic", "paranoid", "exhausted",
               "passive-aggressive", "overconfident", "melancholic"]
FREAK_VOICES = {
    "dangerously optimistic": "en-US-AriaNeural",
    "paranoid": "en-US-GuyNeural",
    "exhausted": "en-US-ChristopherNeural",
    "passive-aggressive": "en-US-SamanthaNeural",
    "overconfident": "en-US-TonyNeural",
    "melancholic": "en-US-JoannaNeural",
}
FREAK_WALKOUT = {
    "moth": ("disco", "chaotic"), "pigeon": ("funk", "menacing"),
    "roomba": ("orchestral", "absurd"), "dog": ("funk", "confident"),
    "toaster": ("electronic", "absurd"), "goblin": ("metal", "menacing"),
    "goldfish": ("ambient", "melancholic"), "skeleton": ("rock", "menacing"),
    "traffic cone": ("comedy", "absurd"), "fax machine": ("electronic", "melancholic"),
    "crab": ("rock", "chaotic"), "lamp": ("jazz", "chill"),
    "elevator": ("orchestral", "melancholic"),
}
FREAK_NAMES = ["Martin", "Bartholomew", "Nolan", "Gerald", "Priscilla",
               "Doug", "Kevin", "Brenda", "Sal", "Margaret", "Todd", "Linda"]


@app.route("/api/randomize", methods=["POST"])
def randomize():
    """Roll a complete freak: species, job, personality, voice, walkout.
    Body (all optional locks): {"species": "pigeon", "vibe": "paranoid"}"""
    import random as _r
    data = request.json or {}
    species = data.get("species") or _r.choice(FREAK_SPECIES)
    job = data.get("job") or _r.choice(FREAK_JOBS)
    vibe = data.get("vibe") or _r.choice(FREAK_VIBES)
    name = data.get("name") or f"{_r.choice(FREAK_NAMES)}"
    genre, mood = FREAK_WALKOUT.get(species, ("comedy", "absurd"))
    voice = FREAK_VOICES.get(vibe, "en-US-AriaNeural")
    premise = f"{vibe} {species} working as a {job}"
    return jsonify({"ok": True,
                    "character": {"name": name, "species": species, "job": job,
                                  "premise": premise, "vibe": vibe, "voice": voice},
                    "walkout": {"genre": genre, "mood": mood, "energy": "high",
                                "shape": "hit", "duration": 8, "seed": _r.randint(0, 99999)},
                    "prompt": f"Write a 60-second standup minute. The comedian is {name}, "
                              f"a {vibe} {species} working as a {job}."})


@app.route("/api/submissions", methods=["GET"])
def list_submissions():
    """Everything queued for the live show."""
    out = []
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if meta and meta.get("status") == "queued":
            out.append({"slug": d.name, "name": meta.get("character", {}).get("name", d.name),
                        "submitted_at": meta.get("submitted_at", ""),
                        "duration_s": meta.get("duration_s", 0),
                        "audio": f"/freaks/{d.name}/set.wav"})
    return jsonify({"submissions": out})


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

def _load_style_model():
    """Data-derived tempo styles (k-means on 225 Kill Tony sets)."""
    try:
        with open(Path(__file__).parent / "models" / "tempo_styles.json") as f:
            return json.load(f)
    except Exception:
        return None


_STYLE_MODEL = _load_style_model()

BUILTIN_TEMPLATES = {
    "deadpan": {"setup": 250, "escalation": 300, "punchline": 900,
                "tag": 400, "closer": 1400,
                "description": "Dash-heavy sniper rhythm. Top Kill Tony avg (4.40). Let silence work."},
    "frantic": {"setup": 150, "escalation": 180, "punchline": 500,
                "tag": 250, "closer": 750,
                "description": "High-energy, exclamation-heavy. Avg 4.30 in the data."},
    "machine-gun": {"setup": 200, "escalation": 250, "punchline": 600,
                    "tag": 300, "closer": 1000,
                    "description": "Rapid-fire short sentences. The dominant club rhythm (119/225 sets)."},
    "storyteller": {"setup": 400, "escalation": 450, "punchline": 700,
                    "tag": 350, "closer": 1000,
                    "description": "Steady medium sentences. Unhurried setups, warm landing."},
    "manic": {"setup": 150, "escalation": 200, "punchline": 500,
              "tag": 250, "closer": 800,
              "description": "Fast, breathless, barely pauses. Energy over precision."},
}

if _STYLE_MODEL:
    for _name, _s in _STYLE_MODEL["clusters"].items():
        if _name in BUILTIN_TEMPLATES:
            BUILTIN_TEMPLATES[_name]["description"] = (
                _s["description"] + f" (n={_s['n']}, avg {_s['avg_score']:.2f}/5)")


def _rhythm_features(text: str) -> list[float]:
    """Same 8 features the style model was trained on (stdlib only)."""
    import statistics
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    wl = [len(s.split()) for s in sents]
    n = max(1, len(sents))
    return [len(sents),
            float(statistics.mean(wl)) if wl else 0.0,
            float(statistics.pstdev(wl)) if len(wl) > 1 else 0.0,
            sum(1 for w in wl if w < 6) / n,
            sum(1 for w in wl if w > 20) / n,
            text.count("?") / n,
            text.count("!") / n,
            (text.count("-") + text.count("—")) / n]


@app.route("/api/match_style", methods=["POST"])
def match_style():
    """Match minute text to nearest data-derived tempo style.
    Body: {"text": "..."} -> {style, distances, note}"""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text or _STYLE_MODEL is None:
        return jsonify({"ok": False, "error": "no text or no style model"}), 400

    feats = _rhythm_features(text)
    mean, scale = _STYLE_MODEL["mean"], _STYLE_MODEL["scale"]
    std = [(f - m) / (s or 1) for f, m, s in zip(feats, mean, scale)]

    dists = {}
    for name, s in _STYLE_MODEL["clusters"].items():
        c = s["centroid_std"]
        dists[name] = round(sum((a - b) ** 2 for a, b in zip(std, c)) ** 0.5, 3)

    best = min(dists, key=dists.get)
    s = _STYLE_MODEL["clusters"][best]
    return jsonify({"ok": True, "style": best, "distances": dists,
                    "note": f"Closest to {best} (avg {s['avg_score']:.2f}/5 across {s['n']} Kill Tony sets)"})


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
