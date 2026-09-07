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

PACE_RATES = {"slow": "-15%", "normal": "+0%", "fast": "+12%", "rush": "+25%"}


async def tts_generate(text: str, voice: str = "en-US-AriaNeural",
                       pace: str = "normal") -> bytes:
    """Generate speech as WAV bytes. pace in slow/normal/fast/rush."""
    import edge_tts

    import asyncio as _asyncio
    rate = PACE_RATES.get(pace, "+0%")
    tag = hashlib.sha256(f"{voice}|{rate}|{text}".encode()).hexdigest()[:12]
    tmp_mp3 = AUDIO_DIR / f"_tmp_{tag}.mp3"
    tmp_mp3.unlink(missing_ok=True)  # never convert a stale partial file
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(tmp_mp3))
            break
        except Exception as e:
            last_err = e
            await _asyncio.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"TTS failed after retries: {last_err}")
    
    tmp_wav = AUDIO_DIR / f"_tmp_{tag}.wav"
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

MAIN_ROOM = "editor"  # "bubble" or "editor". One-line revert.


@app.route("/")
def index():
    # Main room: bubble stage. Revert by setting MAIN_ROOM = "editor".
    if MAIN_ROOM == "bubble":
        html = (STAGE_DIR / "index.html").read_text()
        html = html.replace("<head>", '<head><base href="/stage/">', 1)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    return send_from_directory("static", "editor.html")


@app.route("/edit")
def edit_room():
    """Black Room editor (workshop). Always available regardless of MAIN_ROOM."""
    return send_from_directory("static", "editor.html")


@app.route("/classic")
def classic_room():
    """Frozen pre-bubble editor backup. The revert target."""
    return send_from_directory("static", "editor-classic.html")


REACTIONS_LOG = Path(__file__).parent / "reactions.jsonl"


@app.route("/api/laugh", methods=["POST"])
@app.route("/api/clap", methods=["POST"])
def react():
    """Fire-and-forget audience reaction. Logged with server timestamp
    against the current show for training data."""
    from flask import request as _req
    rtype = "laugh" if _req.path.endswith("/laugh") else "clap"
    entry = {"t": time.time(), "reaction": rtype,
             "show": SHOW_COUNTER[0],
             "audio": (LAST_SET.get("payload") or {}).get("audio")}
    try:
        with open(REACTIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return jsonify({"ok": True, "reaction": rtype})


@app.route("/<path:filename>")
def static_files(filename):
    if filename in ("manifest.json", "sw.js", "icon-192.png",
                    "icon-512.png", "apple-touch-icon.png"):
        return send_from_directory("static", filename)
    if filename.startswith("static/avatars/") and filename.endswith(".vrm"):
        name = filename.split("/")[-1]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            return send_from_directory("static/avatars", name)
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


# ── Performance profiles: character vibe -> default delivery ──────────

VIBE_PROFILES = {
    "paranoid":           {"pace": 1.08, "movement": 0.70, "eye_contact": 0.40,
                           "energy": 0.80, "punchline_hold_ms": 600, "gesture_frequency": 0.70},
    "manic":              {"pace": 1.12, "movement": 0.90, "eye_contact": 0.40,
                           "energy": 0.95, "punchline_hold_ms": 450, "gesture_frequency": 0.85},
    "dangerously optimistic": {"pace": 1.05, "movement": 0.75, "eye_contact": 0.85,
                           "energy": 0.90, "punchline_hold_ms": 500, "gesture_frequency": 0.70},
    "overconfident":      {"pace": 1.02, "movement": 0.60, "eye_contact": 0.90,
                           "energy": 0.80, "punchline_hold_ms": 700, "gesture_frequency": 0.55},
    "exhausted":          {"pace": 0.90, "movement": 0.25, "eye_contact": 0.60,
                           "energy": 0.40, "punchline_hold_ms": 1000, "gesture_frequency": 0.20},
    "melancholic":        {"pace": 0.88, "movement": 0.20, "eye_contact": 0.50,
                           "energy": 0.35, "punchline_hold_ms": 1100, "gesture_frequency": 0.15},
    "passive-aggressive": {"pace": 0.96, "movement": 0.40, "eye_contact": 0.85,
                           "energy": 0.60, "punchline_hold_ms": 800, "gesture_frequency": 0.30},
}
DEFAULT_PROFILE = {"pace": 0.94, "movement": 0.40, "eye_contact": 0.80,
                   "energy": 0.65, "punchline_hold_ms": 850, "gesture_frequency": 0.30}


def profile_for_vibe(vibe: str) -> dict:
    return dict(VIBE_PROFILES.get((vibe or "").lower(), DEFAULT_PROFILE))


@app.route("/api/profile", methods=["GET", "POST"])
def get_profile():
    """Default performance profile for a character vibe."""
    if request.method == "POST":
        vibe = (request.json or {}).get("vibe", "")
    else:
        vibe = request.args.get("vibe", "")
    return jsonify({"ok": True, "vibe": vibe, "profile": profile_for_vibe(vibe)})


# ── Beat audio cache: visual-only edits never rebuild TTS ────────────

BEAT_CACHE = Path(__file__).parent / "beat_cache"
BEAT_CACHE.mkdir(exist_ok=True)


def beat_cache_key(text: str, voice: str, pace: str) -> str:
    return hashlib.sha256(f"{voice}|{pace}|{text}".encode()).hexdigest()[:16]


def beat_wav(text: str, voice: str, pace: str = "normal") -> tuple[bytes, str, bool]:
    """TTS for one beat with cache. Returns (wav, key, cached)."""
    key = beat_cache_key(text, voice, pace)
    path = BEAT_CACHE / f"{key}.wav"
    if path.exists():
        return path.read_bytes(), key, True
    audio = asyncio.run(tts_generate(text, voice, pace))
    if audio:
        path.write_bytes(audio)
    return audio, key, False


@app.route("/api/regen_beat", methods=["POST"])
def regen_beat():
    """Regenerate ONE beat (text/pace/voice change). Everything else reuses cache.
    Body: {"text": "...", "voice": "...", "pace": "slow"}"""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400
    voice = data.get("voice", "en-US-AriaNeural")
    pace = data.get("pace", "normal")
    audio, key, cached = beat_wav(text, voice, pace)
    if not audio:
        return jsonify({"ok": False, "error": "tts failed"}), 502
    samples = wav_to_samples(audio)
    return jsonify({"ok": True, "key": key, "cached": cached,
                    "duration_ms": int(len(samples) / 24000 * 1000)})


@app.route("/api/compose", methods=["POST"])
def compose():
    """Compose full set with exact timing.
    Beats may carry a `key` from /api/regen_beat or a previous compose;
    matching cache entries skip TTS entirely (visual-only edits = instant)."""
    data = request.json
    beats = data.get("beats", [])
    voice = data.get("voice", "en-US-AriaNeural")

    # Generate TTS for each beat (cache-aware)
    beat_audios = []
    for b in beats:
        pace = b.get("pace", "normal")
        key = b.get("key")
        audio = None
        if key:
            cached = BEAT_CACHE / f"{re.sub(r'[^a-f0-9]', '', key)[:16]}.wav"
            if cached.exists():
                audio = cached.read_bytes()
        if audio is None:
            audio, key, _ = beat_wav(b["text"], voice, pace)
            b["key"] = key
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

    full_text = " ".join(b.get("text", "") for b in beats)
    SHOW_COUNTER[0] += 1
    LAST_SET.clear()
    LAST_SET["payload"] = {
        "title": f"Black Room Set #{SHOW_COUNTER[0]}",
        "text": full_text,
        "audio": f"/audio/{filename}",
        "show_number": SHOW_COUNTER[0],
        "segments": _beats_to_segments(beats, offsets),
    }

    return jsonify({
        "ok": True,
        "audio": f"/audio/{filename}",
        "duration_ms": int(duration_ms),
        "beats": offsets,
    })


@app.errorhandler(500)
def _json_500(e):
    # API clients call res.json() unconditionally; an HTML traceback page
    # surfaces as "unexpected character at line 1". Always answer JSON.
    return jsonify({"ok": False, "error": "server error, retry"}), 500


@app.errorhandler(404)
def _json_404(e):
    return jsonify({"ok": False, "error": "not found"}), 404


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(str(AUDIO_DIR), filename)


STAGE_DIR = Path(__file__).parent / "stage"

LAST_SET: dict = {}
SHOW_COUNTER = [0]

EMOTION_BY_BEAT = {"setup": "neutral", "escalation": "tension",
                   "punchline": "surprise", "tag": "playful", "closer": "joy"}


@app.route("/stage")
def stage_page():
    return send_from_directory(str(STAGE_DIR), "index.html")


@app.route("/stage/<path:filename>")
def stage_files(filename):
    if filename in ("index.html", "app.js", "style.css"):
        return send_from_directory(str(STAGE_DIR), filename)
    return jsonify({"ok": False, "error": "not found"}), 404


def _beats_to_segments(beats: list[dict], offsets: list[dict]) -> list[dict]:
    by_id = {o["id"]: o for o in offsets}
    segs = []
    for b in beats:
        o = by_id.get(b.get("id"), {})
        pause = int(b.get("pause_after_ms", 300))
        segs.append({
            "text": b.get("text", ""),
            "start_ms": int(o.get("start_ms", 0)),
            "end_ms": int(o.get("start_ms", 0)) + int(o.get("speech_ms", 0)),
            "emotion": EMOTION_BY_BEAT.get(b.get("type", "setup"), "neutral"),
            "intensity": round(min(1.0, pause / 1400), 2),
            "pace": 1.0,
            "pause_after_ms": pause,
        })
    return segs


@app.route("/api/set", methods=["GET"])
def stage_set():
    """Bubble player feed: last composed Black Room set as segments.
    Falls back to a default Ella minute so the stage always plays."""
    if LAST_SET:
        return jsonify(LAST_SET["payload"])

    minute = ("I host a show where artificial personalities do stand-up comedy. "
              "People keep asking whether the robots are actually funny. Sometimes. "
              "Which is already a terrifyingly strong result. Last week one told me it was "
              "working on its material. I said, you do not have material. You have a "
              "probability distribution and Wi-Fi. Comedy used to be art. Now it is telemetry.")
    beats = detect_beats(minute)
    SHOW_COUNTER[0] += 1
    audio_url = None
    try:
        audio = asyncio.run(tts_generate(minute, "en-US-AriaNeural"))
        if audio:
            fn = f"stage_default_{hashlib.sha256(minute.encode()).hexdigest()[:10]}.wav"
            (AUDIO_DIR / fn).write_bytes(audio)
            audio_url = f"/audio/{fn}"
    except Exception:
        pass
    payload = {"title": "Ella M — Default Set", "text": minute, "audio": audio_url,
               "show_number": SHOW_COUNTER[0],
               "segments": _beats_to_segments(beats, [])}
    return jsonify(payload)


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

    # 2. delivery.json — the persistent performance score (v1)
    profile = profile_for_vibe(character.get("vibe", ""))
    if isinstance(data.get("profile"), dict):
        for k, v in data["profile"].items():
            if k in profile:
                try:
                    profile[k] = float(v)
                except (TypeError, ValueError):
                    pass
    beats_out = []
    for b in beats:
        perf = b.get("performance") or {}
        beats_out.append({
            "id": b.get("id"), "type": b.get("type", "setup"),
            "text": b.get("text", ""),
            "speech": {"pace": b.get("pace", "normal"),
                       "emphasis": float(b.get("emphasis", 0.5))},
            "performance": {
                "expression": perf.get("expression", "neutral"),
                "gesture": perf.get("gesture", "normal"),
                "look": perf.get("look", "audience"),
            },
            "pause_after_ms": int(b.get("pause_after_ms", 300)),
        })
    (bdir / "delivery.json").write_text(json.dumps({
        "version": "freaktown.delivery.v1",
        "voice": {"provider": "edge-tts", "voice_id": voice},
        "profile": profile,
        "beats": beats_out,
    }, indent=2))

    # 3. set.wav (composed clip with exact silence, cache-aware)
    beat_audios = []
    for b in beats:
        pace = b.get("pace", "normal")
        audio, key, _ = beat_wav(b.get("text", ""), voice, pace)
        b["key"] = key
        beat_audios.append({"id": b.get("id"), "audio": audio,
                            "pause_ms": int(b.get("pause_after_ms", 300))})
    wav_bytes, offsets = compose_beats(beat_audios)
    (bdir / "set.wav").write_bytes(wav_bytes)

    # 4. walkout audio + walkout.json (recipe)
    walkout = data.get("walkout") or {}
    if walkout.get("genre"):
        import shutil
        import sound_synth
        recipe = {"genre": walkout.get("genre", "funk"), "mood": walkout.get("mood", "confident"),
                  "energy": walkout.get("energy", "high"), "shape": walkout.get("shape", "hit")}
        seed = int(walkout.get("seed", 0))
        if walkout.get("provider") == "fal":
            # keep the real render: copy from audio cache by recipe hash
            key = hashlib.sha256(json.dumps(
                {"provider": "fal", "model": FAL_MODEL, "prompt_version": WALKOUT_PROMPT_VERSION,
                 **recipe, "seed": seed}, sort_keys=True).encode()).hexdigest()[:12]
            cached = AUDIO_DIR / "walkouts" / f"fal_{key}.mp3"
            if cached.exists():
                shutil.copy(cached, bdir / "walkout.mp3")
            else:  # cache missed: instant render so the bundle is never empty
                full = {**recipe, "duration": 8}
                (bdir / "walkout.wav").write_bytes(sound_synth.generate(full, seed))
        else:
            full = {**recipe, "duration": 8}
            (bdir / "walkout.wav").write_bytes(sound_synth.generate(full, seed))
    bundle_audio = "walkout.mp3" if (bdir / "walkout.mp3").exists() else (
        "walkout.wav" if (bdir / "walkout.wav").exists() else None)
    (bdir / "walkout.json").write_text(json.dumps({
        "genre": walkout.get("genre", ""), "mood": walkout.get("mood", ""),
        "energy": walkout.get("energy", ""), "shape": walkout.get("shape", "hit"),
        "seed": int(walkout.get("seed", 0)),
        "provider": walkout.get("provider", "procedural"),
        "duration": 10 if walkout.get("provider") == "fal" else 8,
        "audio": bundle_audio,
    }, indent=2))

    # 5. portrait.png + visual.json (2D concept locked in the editor)
    portrait = data.get("portrait") or {}
    if portrait.get("url", "").startswith("/portraits/"):
        import shutil
        src = Path(__file__).parent / portrait["url"].lstrip("/")
        if src.exists():
            shutil.copy(src, bdir / "portrait.png")
    (bdir / "visual.json").write_text(json.dumps({
        "model": "flux-1-schnell",
        "seed": portrait.get("seed", 0),
        "prompt": portrait.get("prompt", ""),
        "image": "portrait.png" if (bdir / "portrait.png").exists() else None,
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
    # flatten v1 speech/performance blocks for the editor (which keeps
    # pace top-level and performance nested — same shape it saves)
    flat = []
    for b in delivery.get("beats", []):
        b = dict(b)
        if isinstance(b.get("speech"), dict) and "pace" not in b:
            b["pace"] = b["speech"].get("pace", "normal")
        b.setdefault("performance", {"expression": "neutral", "gesture": "normal",
                                     "look": "audience"})
        flat.append(b)
    return jsonify({"ok": True, "slug": slug, "character": character,
                    "beats": flat, "voice": meta.get("voice", ""),
                    "profile": delivery.get("profile", {}),
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


WALKOUT_GENRES = {
    "funk":       {"instruments": "wah guitar, punchy electric bass, muted brass stabs", "bpm": 118},
    "rock":       {"instruments": "distorted power chords, punchy live drums", "bpm": 138},
    "electronic": {"instruments": "driving synth bass, neon pads, tight electronic drums", "bpm": 128},
    "jazz":       {"instruments": "walking upright bass, brushed drums, muted brass", "bpm": 108},
    "orchestral": {"instruments": "brass section, timpani, sweeping strings", "bpm": 100},
    "comedy":     {"instruments": "tuba, plucked strings, slide whistle accents", "bpm": 100},
    "hip-hop":    {"instruments": "deep 808 bass, crisp snare, hi-hat rolls", "bpm": 92},
    "disco":      {"instruments": "four-on-the-floor drums, funky bassline, string stabs", "bpm": 120},
}

WALKOUT_SHAPES = {
    "hit":    "immediate strong entrance hit, no slow intro, front-loaded impact",
    "groove": "continuous tight groove, loop-like structure",
    "build":  "rapid build in intensity, decisive final hit",
    "fanfare": "short ceremonial fanfare phrase, clear beginning and ending",
    "weird":  "quirky characterful production, unusual sonic detail, comedic",
}

FAL_MODEL = "fal-ai/stable-audio-3/small/music/text-to-audio"
WALKOUT_PROMPT_VERSION = 1


def build_walkout_prompt(recipe: dict) -> str:
    g = WALKOUT_GENRES.get(recipe.get("genre", "funk"), WALKOUT_GENRES["funk"])
    return (
        "TrackType: Music, "
        "10-second instrumental comedy walk-on sting, "
        f"Genre: {recipe.get('genre', 'funk')}, "
        f"{g['instruments']}, "
        f"{recipe.get('mood', 'confident')}, "
        f"{recipe.get('energy', 'high')} energy, "
        f"{g['bpm']} BPM, "
        f"{WALKOUT_SHAPES.get(recipe.get('shape', 'hit'), WALKOUT_SHAPES['hit'])}, "
        "immediate hook in the first half second, "
        "one memorable musical motif, "
        "clean stereo production, "
        "hard decisive ending at exactly 10 seconds, "
        "no vocals, no lyrics"
    )


def _fal_key() -> str:
    key = os.getenv("FAL_KEY", "").strip()
    if key:
        return key
    try:
        with open("/root/.agent-vault/vault.json") as f:
            return str(json.load(f).get("FAL_KEY", "")).strip()
    except Exception:
        return ""


def _generate_walkout_fal(recipe: dict, seed: int) -> bytes:
    """Real walkout via fal Stable Audio 3 Small. Raises on failure."""
    import fal_client
    key = _fal_key()
    if not key:
        raise RuntimeError("no FAL_KEY")
    os.environ["FAL_KEY"] = key
    result = fal_client.subscribe(
        FAL_MODEL,
        arguments={
            "prompt": build_walkout_prompt(recipe),
            "duration": 10,
            "num_inference_steps": 8,
            "seed": seed,
            "output_format": "mp3",
            "negative_prompt": "vocals, singing, spoken words, long intro, long fade out",
        },
    )
    url = result["audio"]["url"]
    import httpx
    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


@app.route("/api/walkout", methods=["POST"])
def walkout():
    """Walkout sting from a recipe. Two engines, one contract.
    Body: {"genre","mood","energy","shape","seed", "mode": "instant"|"real"}
    - instant (default): procedural synth, <1s, free, exact duration
    - real: fal Stable Audio 3 Small, 10s, needs FAL_KEY, falls back to instant
    Cache key covers provider + model + prompt version + recipe + seed."""
    import sound_synth
    data = request.json or {}
    recipe = {
        "genre": str(data.get("genre", "funk"))[:20],
        "mood": str(data.get("mood", "confident"))[:20],
        "energy": str(data.get("energy", "high"))[:20],
        "shape": str(data.get("shape", "hit"))[:20],
    }
    seed = int(data.get("seed", 0))
    mode = str(data.get("mode", "instant")).lower()

    wdir = AUDIO_DIR / "walkouts"
    wdir.mkdir(exist_ok=True)

    if mode == "real":
        key = hashlib.sha256(json.dumps(
            {"provider": "fal", "model": FAL_MODEL,
             "prompt_version": WALKOUT_PROMPT_VERSION,
             **recipe, "seed": seed}, sort_keys=True).encode()).hexdigest()[:12]
        path = wdir / f"fal_{key}.mp3"
        if path.exists():
            return jsonify({"ok": True, "audio": f"/audio/walkouts/fal_{key}.mp3",
                            "recipe": recipe, "seed": seed, "cached": True,
                            "provider": "fal", "duration": 10})
        try:
            path.write_bytes(_generate_walkout_fal(recipe, seed))
            return jsonify({"ok": True, "audio": f"/audio/walkouts/fal_{key}.mp3",
                            "recipe": recipe, "seed": seed, "cached": False,
                            "provider": "fal", "duration": 10})
        except Exception as e:
            return jsonify({"ok": False, "error": f"fal failed ({e}), retry mode=instant",
                            "fallback": "instant"}), 502

    # instant: procedural
    full = {**recipe, "duration": min(11, max(2, float(data.get("duration", 8))))}
    rid = sound_synth.recipe_id(full, seed)
    path = wdir / f"{rid}.wav"
    cached = path.exists()
    if not cached:
        path.write_bytes(sound_synth.generate(full, seed))
    return jsonify({"ok": True, "audio": f"/audio/walkouts/{rid}.wav",
                    "recipe": recipe, "seed": seed, "cached": cached,
                    "provider": "procedural"})


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


@app.route("/f/<slug>")
def watch_set(slug):
    """Public watch page: freak.town/f/<slug>. VRM stage, reactions, vote, remix loop."""
    import html as _html
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if not meta or not (bdir / "set.wav").exists():
        return "No such set (yet). Make one in the Black Room.", 404
    char = meta.get("character", {})
    name = _html.escape(char.get("name", slug))
    premise = _html.escape(char.get("premise", ""))
    has_portrait = (bdir / "portrait.png").exists()
    img = f"/freaks/{slug}/portrait.png" if has_portrait else "/icon-512.png"
    dur = meta.get("duration_s", 0)
    # beat timeline for sync highlight (speech estimated at stage pace)
    beats = []
    try:
        delivery = json.loads((bdir / "delivery.json").read_text())
        t = 0
        for b in delivery.get("beats", []):
            words = len((b.get("text") or "").split())
            speech = int(words / 2.82 * 1000)
            pause = int(b.get("pause_after_ms", 300))
            beats.append({"text": b.get("text", ""), "start": t,
                          "end": t + speech,
                          "face": (b.get("performance") or {}).get("expression", "neutral")})
            t += speech + pause
    except Exception:
        pass
    page = WATCH_TEMPLATE
    for key, val in {
        "__SLUG__": slug, "__NAME__": name, "__PREMISE__": premise,
        "__IMG__": img, "__DUR__": str(dur),
        "__BEATS__": json.dumps(beats),
    }.items():
        page = page.replace(key, val)
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


WATCH_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__NAME__ — Freak Town</title>
<meta property="og:title" content="__NAME__ — Freak Town">
<meta property="og:description" content="__PREMISE__ (__DUR__s set)">
<meta property="og:image" content="__IMG__">
<meta property="og:type" content="music.song">
<meta name="theme-color" content="#ff2fa8">
<script type="importmap">
{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/",
  "@pixiv/three-vrm": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.0/lib/three-vrm.module.js"
}}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;min-height:100vh;display:flex;flex-direction:column}
.top{padding:10px;font-size:12px;letter-spacing:2px;color:#ff2fa8;font-weight:bold}
#stage{position:relative;flex-shrink:0}
#vrmStage{width:100%;height:300px;display:none}
#stageImg{max-width:240px;border-radius:12px;margin:0 auto;display:block}
h1{font-size:22px;margin:8px 0 2px}
.premise{color:#888;font-size:13px;margin-bottom:6px}
#clock{font-size:13px;color:#555;font-variant-numeric:tabular-nums}
#transcript{flex:1;overflow-y:auto;text-align:left;max-width:560px;margin:8px auto;padding:0 16px;font-size:15px;line-height:1.9;color:#555}
.seg.spoken{color:#bbb}
.seg.active{color:#ff2fa8}
.controls{padding:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;border-top:1px solid #1a1a2e;background:#0c0c12;padding-bottom:calc(12px + env(safe-area-inset-bottom))}
button{background:#1a1a2e;border:1px solid #333;color:#eee;padding:12px 22px;border-radius:24px;font-size:15px;cursor:pointer;font-family:inherit}
button.big{background:#ff2fa8;border-color:#ff2fa8;color:#fff;min-height:52px}
#endscreen{display:none;padding:20px}
#endscreen.show{display:block}
.vote{font-size:26px;padding:12px 26px;margin:4px}
#stats{color:#888;font-size:13px;margin:10px 0}
.cta{display:block;margin:8px auto;max-width:340px;width:100%;text-decoration:none}
a.cta{color:#fff}
.ghost{background:none}
</style>
</head><body>
<div class="top">FREAK TOWN · LIVE</div>
<div id="stage">
  <canvas id="vrmStage"></canvas>
  <img id="stageImg" src="__IMG__" alt="">
</div>
<h1>__NAME__</h1>
<div class="premise">__PREMISE__</div>
<div id="clock">00:00 / __DUR__s</div>
<div id="transcript"></div>
<div class="controls" id="liveControls">
  <button class="big" id="playBtn">▶ PLAY</button>
  <button id="laughBtn" disabled>😂 <span id="laughCount">0</span></button>
  <button id="clapBtn" disabled>👏 <span id="clapCount">0</span></button>
</div>
<div id="endscreen">
  <div id="stats"></div>
  <div>
    <button class="vote" onclick="vote('keep')">👍 KEEP</button>
    <button class="vote" onclick="vote('cut')">👎 CUT</button>
  </div>
  <div id="voteMsg" style="color:#00d4ff;margin:8px;"></div>
  <a class="cta" href="/edit?remix=__SLUG__"><button class="big" style="width:100%;">🎤 RESPOND WITH YOUR OWN SET</button></a>
  <a class="cta" href="/"><button style="width:100%;">＋ MAKE YOUR OWN FREAK</button></a>
  <button class="ghost cta" style="width:100%;" onclick="passItOn()">📤 PASS IT ON</button>
</div>
<audio id="a" src="/freaks/__SLUG__/set.wav" preload="auto"></audio>
<script>
const BEATS = __BEATS__;
const SLUG = "__SLUG__";
const Aud = document.getElementById('a');
let timer = null, myLaughs = 0, myClaps = 0, voted = false;

// transcript
const tx = document.getElementById('transcript');
BEATS.forEach((b, i) => {
  const d = document.createElement('div');
  d.className = 'seg'; d.id = 'seg' + i;
  d.textContent = b.text;
  tx.appendChild(d);
});

function fmt(t) {
  t = Math.max(0, t);
  return String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(Math.floor(t % 60)).padStart(2, '0');
}

async function play() {
  try { await Aud.play(); } catch (e) {
    document.getElementById('clock').textContent = 'tap PLAY again (browser blocked it)';
    return;
  }
  document.getElementById('playBtn').style.display = 'none';
  document.getElementById('laughBtn').disabled = false;
  document.getElementById('clapBtn').disabled = false;
  timer = setInterval(tick, 150);
}
document.getElementById('playBtn').onclick = play;

function tick() {
  const t = Aud.currentTime * 1000;
  document.getElementById('clock').textContent = fmt(Aud.currentTime) + ' / __DUR__s';
  let cur = -1;
  BEATS.forEach((b, i) => {
    const el = document.getElementById('seg' + i);
    if (!el) return;
    el.classList.toggle('spoken', t >= b.start);
    const on = t >= b.start && t < b.end + 1200;
    el.classList.toggle('active', on);
    if (on) cur = i;
  });
  const act = cur >= 0 && document.getElementById('seg' + cur);
  if (act) act.scrollIntoView({block: 'nearest'});
  if (window.__vrmFace && cur >= 0) window.__vrmFace(BEATS[cur].face || 'neutral');
  if (Aud.ended) endShow();
}

async function react(type) {
  if (Aud.paused || Aud.ended) return;
  if (type === 'laugh') { myLaughs++; document.getElementById('laughCount').textContent = myLaughs; }
  else { myClaps++; document.getElementById('clapCount').textContent = myClaps; }
  try {
    await fetch('/api/react', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug: SLUG, type, set_time_ms: Math.round(Aud.currentTime * 1000)})});
  } catch (e) {}
}

document.getElementById('laughBtn').onclick = () => react('laugh');
document.getElementById('clapBtn').onclick = () => react('clap');

async function vote(v) {
  if (voted) return;
  voted = true;
  try {
    await fetch('/api/vote', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug: SLUG, vote: v})});
  } catch (e) {}
  document.getElementById('voteMsg').textContent =
    v === 'keep' ? 'Counted. They live to perform another night.' : 'Counted. Brutal. Ella approves.';
}

function endShow() {
  clearInterval(timer);
  document.getElementById('liveControls').style.display = 'none';
  document.getElementById('endscreen').classList.add('show');
  document.getElementById('stats').textContent =
    `You laughed ${myLaughs}× and clapped ${myClaps}× · did they earn another night?`;
  if (window.__vrmIdle) window.__vrmIdle();
}

async function passItOn() {
  const url = location.href;
  try {
    if (navigator.share) { await navigator.share({title: document.title, url}); return; }
  } catch (e) { if (e && e.name === 'AbortError') return; }
  try { await navigator.clipboard.writeText(url); } catch (e) {}
}
Aud.onended = endShow;
</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
let vrm = null, analyser = null, freqData = null, audioCtx = null;
let pAA = 0, pIH = 0, pOH = 0, nextBlink = 0;
const clock = new THREE.Clock();
const FACE = {grin: ['happy', 0.55], deadpan: ['relaxed', 0.7], annoyed: ['angry', 0.6],
              confused: ['surprised', 0.35], surprised: ['surprised', 0.8], neutral: [null, 0]};
window.__vrmFace = (face) => {
  if (!vrm?.expressionManager) return;
  for (const k of ['happy', 'relaxed', 'angry', 'surprised', 'sad']) {
    try { vrm.expressionManager.setValue(k, 0); } catch (e) {}
  }
  const [slot, val] = FACE[face] || [null, 0];
  if (slot) { try { vrm.expressionManager.setValue(slot, val); } catch (e) {} }
};
window.__vrmIdle = () => {
  if (!vrm?.expressionManager) return;
  for (const k of ['happy', 'relaxed', 'angry', 'surprised', 'sad']) {
    try { vrm.expressionManager.setValue(k, 0); } catch (e) {}
  }
};
try {
  const canvas = document.getElementById('vrmStage');
  const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
  camera.position.set(0, 1.35, 2.6);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x332233, 1.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(1, 2, 2);
  scene.add(key);
  const loader = new GLTFLoader();
  loader.register(p => new VRMLoaderPlugin(p));
  const gltf = await loader.loadAsync('/static/avatars/default-v1.vrm');
  vrm = gltf.userData.vrm;
  scene.add(vrm.scene);
  const fit = () => {
    const w = canvas.clientWidth || 300;
    renderer.setSize(w, 300, false);
    camera.aspect = w / 300;
    camera.updateProjectionMatrix();
  };
  fit();
  addEventListener('resize', fit);
  document.getElementById('stageImg').style.display = 'none';
  canvas.style.display = 'block';
  const A = document.getElementById('a');
  const ensureGraph = () => {
    if (audioCtx) { if (audioCtx.state === 'suspended') audioCtx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    audioCtx = new AC();
    const src = audioCtx.createMediaElementSource(A);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.55;
    freqData = new Uint8Array(analyser.frequencyBinCount);
    src.connect(analyser);
    analyser.connect(audioCtx.destination);
  };
  A.addEventListener('play', ensureGraph);
  const band = (lo, hi) => {
    if (!analyser) return 0;
    analyser.getByteFrequencyData(freqData);
    let s = 0, n = 0;
    for (let i = lo; i < Math.min(hi, freqData.length); i++) { s += freqData[i]; n++; }
    return n ? s / n : 0;
  };
  const sm = (p, t, k) => p + (t - p) * k;
  (function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;
    if (vrm?.expressionManager && analyser && !A.paused) {
      pAA = sm(pAA, Math.min(1, band(0, 10) / 200), 0.5);
      pIH = sm(pIH, Math.min(1, band(40, 80) / 180) * 0.7, 0.5);
      pOH = sm(pOH, Math.min(1, band(10, 40) / 220) * 0.7, 0.5);
      try {
        vrm.expressionManager.setValue('aa', pAA);
        vrm.expressionManager.setValue('ih', pIH);
        vrm.expressionManager.setValue('oh', pOH);
      } catch (e) {}
    } else if (vrm?.expressionManager) {
      pAA = sm(pAA, 0, 0.3); pIH = sm(pIH, 0, 0.3); pOH = sm(pOH, 0, 0.3);
      try {
        vrm.expressionManager.setValue('aa', pAA);
        vrm.expressionManager.setValue('ih', pIH);
        vrm.expressionManager.setValue('oh', pOH);
      } catch (e) {}
    }
    if (vrm?.humanoid) {
      const spine = vrm.humanoid.getNormalizedBoneNode('spine');
      if (spine) spine.rotation.y = Math.sin(t * 0.6) * 0.04;
    }
    if (t > nextBlink) {
      nextBlink = t + 2.5 + Math.random() * 2.5;
      try {
        vrm.expressionManager.setValue('blink', 1);
        setTimeout(() => { try { vrm.expressionManager.setValue('blink', 0); } catch (e) {} }, 140);
      } catch (e) {}
    }
    vrm.update(dt);
    renderer.render(scene, camera);
  })();
} catch (e) {
  console.error('vrm stage failed, portrait fallback showing', e);
}
</script>
</body></html>"""


@app.route("/api/react", methods=["POST"])
def react_to_set():
    """Audience reaction from a watch page: {slug, type, set_time_ms}.
    Logged with server timestamp for laugh-curve training data."""
    import time as _time
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45]
    rtype = str(data.get("type", ""))
    if not slug or rtype not in ("laugh", "clap", "crickets", "groan"):
        return jsonify({"ok": False, "error": "bad reaction"}), 400
    try:
        with open(Path(__file__).parent / "reactions.jsonl", "a") as f:
            f.write(json.dumps({"t": _time.time(), "slug": slug, "reaction": rtype,
                                "set_time_ms": int(data.get("set_time_ms", 0))}) + "\n")
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/vote", methods=["POST"])
def vote_on_set():
    """KEEP/CUT verdict from a watch page: {slug, vote}."""
    import time as _time
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45]
    vote = str(data.get("vote", ""))
    if not slug or vote not in ("keep", "cut"):
        return jsonify({"ok": False, "error": "bad vote"}), 400
    try:
        with open(Path(__file__).parent / "votes.jsonl", "a") as f:
            f.write(json.dumps({"t": _time.time(), "slug": slug, "vote": vote}) + "\n")
    except Exception:
        pass
    return jsonify({"ok": True})


def _r2_client():
    import boto3
    with open("/root/.agent-vault/vault.json") as f:
        v = json.load(f)
    return boto3.client("s3", endpoint_url=v["CLOUDFLARE_R2_ENDPOINT"],
                        aws_access_key_id=v["CLOUDFLARE_R2_ACCESS_KEY"],
                        aws_secret_access_key=v["CLOUDFLARE_R2_SECRET_KEY"])


@app.route("/api/share/<slug>", methods=["POST"])
def share_set(slug):
    """Mirror a freak bundle to R2 (f/<slug>/) for durability + future CDN.
    Returns the public watch URL: https://freak.town/f/<slug>"""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if not meta or not (bdir / "set.wav").exists():
        return jsonify({"ok": False, "error": "nothing to share yet"}), 404
    try:
        s3 = _r2_client()
        for fname, ctype in [("set.wav", "audio/wav"), ("portrait.png", "image/png"),
                             ("character.json", "application/json"),
                             ("delivery.json", "application/json"),
                             ("meta.json", "application/json")]:
            p = bdir / fname
            if p.exists():
                s3.upload_file(str(p), "freak-town", f"f/{slug}/{fname}",
                               ExtraArgs={"ContentType": ctype})
    except Exception as e:
        return jsonify({"ok": False, "error": f"r2 upload failed: {str(e)[:100]}"}), 502
    return jsonify({"ok": True, "url": f"https://freak.town/f/{slug}"})


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


@app.route("/api/portrait", methods=["POST"])
def portrait():
    """2D character portrait via Cloudflare FLUX Schnell (free neurons).
    Body: {"species": "moth", "job": "divorce lawyer", "vibe": "exhausted",
           "style": "cartoon", "seed": 0}
    Returns {image: "/portraits/<hash>.png", prompt, cached}."""
    import base64
    import httpx
    data = request.json or {}
    species = str(data.get("species", "creature"))[:60]
    job = str(data.get("job", ""))[:60]
    vibe = str(data.get("vibe", ""))[:40]
    style = str(data.get("style", "cartoon"))[:30]
    seed = int(data.get("seed", 0))

    prompt = f"{vibe} {species}"
    if job:
        prompt += f" working as a {job}"
    prompt += f", {style} portrait, expressive face, plain background"

    # NOTE: flux-1-schnell takes no seed param. FACE omits nonce (stable,
    # cacheable); AGAIN sends a random nonce (always a fresh roll).
    nonce = str(data.get("nonce", "") or "")
    key = hashlib.sha256(f"{prompt}|{seed}|{nonce}".encode()).hexdigest()[:12]
    pdir = Path(__file__).parent / "portraits"
    pdir.mkdir(exist_ok=True)
    path = pdir / f"{key}.png"
    if path.exists():
        return jsonify({"ok": True, "image": f"/portraits/{key}.png",
                        "prompt": prompt, "cached": True})

    tok, acct = _cf_creds()
    if not tok or not acct:
        return jsonify({"ok": False, "error": "no Cloudflare creds"}), 502
    try:
        r = httpx.post(
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell",
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            json={"prompt": prompt, "steps": 4},
            timeout=180)
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"cf {r.status_code}"}), 502
        img = r.json()["result"]["image"]
        if isinstance(img, list):
            img = img[0]
        path.write_bytes(base64.b64decode(img))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]}), 502
    return jsonify({"ok": True, "image": f"/portraits/{key}.png",
                    "prompt": prompt, "cached": False})


@app.route("/portraits/<path:filename>")
def serve_portrait(filename):
    if not re.fullmatch(r"[a-f0-9]{12}\.png", filename):
        return jsonify({"ok": False, "error": "not found"}), 404
    return send_from_directory(str(Path(__file__).parent / "portraits"), filename)


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
