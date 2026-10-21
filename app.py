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
import sys
import time
import wave
from pathlib import Path

from flask import Flask, send_from_directory, send_file, jsonify, request

from party import party_bp
from lab import lab_bp
from cauldron_show import show_bp
from face_profiles import detect_face_profile, to_pog_face

app = Flask(__name__)
app.register_blueprint(party_bp)
app.register_blueprint(lab_bp)
app.register_blueprint(show_bp)

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


def espeak_wav(text: str, voice: str = "") -> bytes:
    """Offline fallback TTS (espeak). Robotic but instant, unthrottled.
    Used only when edge-tts fails; re-render later for the real voice."""
    import subprocess as _sp
    import tempfile as _tf
    feminine = any(k in (voice or "") for k in
                   ["Aria", "Jenny", "Jane", "Samantha", "Joanna", "Michelle", "Emma", "Ava"])
    espeak_voice = "en+f3" if feminine else "en+m3"
    with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out = tmp.name
    try:
        _sp.run(["espeak", "-v", espeak_voice, "-s", "175", "--stdout", text],
                stdout=open(out, "wb"), timeout=30, check=False)
        conv = out + ".c.wav"
        _sp.run(["ffmpeg", "-y", "-i", out, "-ar", "24000", "-ac", "1",
                 "-f", "wav", conv], capture_output=True, timeout=20)
        data = Path(conv).read_bytes() if Path(conv).exists() else b""
        Path(conv).unlink(missing_ok=True)
        return data
    finally:
        Path(out).unlink(missing_ok=True)


def beat_wav(text: str, voice: str, pace: str = "normal") -> tuple[bytes, str, bool]:
    """TTS for one beat with cache. Returns (wav, key, cached).
    Falls back to offline espeak when edge-tts is throttled, so audio
    ALWAYS produces. Re-render later for the real voice."""
    key = beat_cache_key(text, voice, pace)
    path = BEAT_CACHE / f"{key}.wav"
    if path.exists():
        return path.read_bytes(), key, True
    robot = BEAT_CACHE / f"{key}.robot.wav"
    if robot.exists():
        return robot.read_bytes(), key, True
    try:
        audio = asyncio.run(tts_generate(text, voice, pace))
    except Exception:
        audio = b""
    if not audio:
        audio = espeak_wav(text, voice)
        if audio:
            # mark fallback provenance in cache key namespace
            path = BEAT_CACHE / f"{key}.robot.wav"
            path.write_bytes(audio)
            return audio, key, False
        raise RuntimeError("all TTS failed")
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


@app.route("/api/beat_audio/<key>", methods=["GET"])
def beat_audio(key):
    """Serve one cached beat wav for voice audition. Key is the hex
    returned by /api/regen_beat — nothing else on disk is reachable."""
    key = re.sub(r"[^a-f0-9]", "", key)[:16]
    for cand in (BEAT_CACHE / f"{key}.wav", BEAT_CACHE / f"{key}.robot.wav"):
        if cand.exists():
            return send_from_directory(str(BEAT_CACHE), cand.name,
                                       mimetype="audio/wav")
    return jsonify({"ok": False, "error": "unknown beat"}), 404


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


def _char_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "freak").lower()).strip("-")[:32] or "freak"


def resolve_bundle(char_slug: str, set_slug: str) -> str | None:
    """Map freak.town/<character>/<set> to a bundle dir.
    Matches character slug + set_name slug (or bundle-dir suffix fallback)."""
    char_slug = re.sub(r"[^a-z0-9-]", "", char_slug)[:32]
    set_slug = re.sub(r"[^a-z0-9-]", "", set_slug)[:45]
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if not meta:
            continue
        char = meta.get("character", {})
        if _char_slug(char.get("name", "")) != char_slug:
            continue
        named = re.sub(r"[^a-z0-9]+", "-", (meta.get("set_name") or "").lower()).strip("-")[:45]
        if named == set_slug or d.name == set_slug or d.name.endswith("-" + set_slug):
            return d.name
    return None


def canonical_url(slug: str) -> str:
    """Public canonical URL: /@<character>/<set> when named, else /f/<slug>.
    /f/<slug> is the immutable share alias, kept forever. The @ form is the
    permanent human-readable identity (and protects /live /studio /api /f
    from colliding with character names)."""
    meta = _bundle_meta(slug) or {}
    char = meta.get("character", {})
    named = re.sub(r"[^a-z0-9]+", "-", (meta.get("set_name") or "").lower()).strip("-")[:45]
    if named:
        return f"https://freak.town/@{_char_slug(char.get('name', ''))}/{named}"
    return f"https://freak.town/f/{slug}"


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
            "set_name": meta.get("set_name", ""),
            "url": canonical_url(d.name),
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

    try:
        slug, meta, _ = _save_bundle(data)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "slug": slug, "meta": meta,
                    "audio": f"/freaks/{slug}/set.wav",
                    "url": canonical_url(slug)})


def _lineage(parent_slug: str | None) -> dict:
    """Reply lineage: {relation, parent, root, depth}. Root walks parents (cap 20)."""
    if not parent_slug:
        return {"relation": "original", "parent": None, "root": None, "depth": 0}
    parent_slug = re.sub(r"[^a-z0-9_-]", "", parent_slug)[:45]
    pmeta = _bundle_meta(parent_slug)
    if not pmeta:
        return {"relation": "reply", "parent": parent_slug, "root": parent_slug, "depth": 1}
    plin = pmeta.get("lineage") or {}
    root = plin.get("root") or parent_slug
    depth = min(int(plin.get("depth", 0)) + 1, 99)
    return {"relation": "reply", "parent": parent_slug, "root": root, "depth": depth}


def _save_bundle(data: dict):
    """Persist a freak bundle. Shared by /api/sets and /api/respond.
    Returns (slug, meta). Accepts optional relation/parent_slug for replies."""
    import datetime
    character = data.get("character") or {}
    beats = data.get("beats") or []
    voice = data.get("voice", "en-US-AriaNeural")
    if not beats:
        raise ValueError("no beats to save")

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
                # contract fields, with legacy face/body fallback so old
                # drafts don't lose directing work on save.
                "expression": perf.get("expression") or perf.get("face", "neutral"),
                "gesture": perf.get("gesture") or perf.get("body", "normal"),
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
    # Measured beat timings — the ms-resolution source for downstream
    # cue/word-timing resolution (killella MotionCue resolver reads this).
    (bdir / "offsets.json").write_text(json.dumps({
        "version": "freaktown.offsets.v1",
        "sample_rate": 24000,
        "offsets": offsets,
    }, indent=2))

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
    set_name = re.sub(r"[^a-z0-9]+", "-", str(data.get("set_name") or "").lower()).strip("-")[:45]
    meta = {"slug": slug,
            "set_name": set_name,
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
            "creator": str(data.get("creator") or "")[:64],
            "lineage": _lineage(data.get("parent_slug")),
            "response_seeds": data.get("response_seeds") or [],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (bdir / "meta.json").write_text(json.dumps(meta, indent=2))
    # seed response ideas in background so YOUR TURN never spins
    _seed_responses_async(slug)
    # guaranteed body: every saved freak walks on with a BASIC rig in
    # milliseconds. MAKE THEM 3D can replace it with AI later.
    try:
        if _avatar_runtime(slug) is None:
            _basic_build(slug, bdir, meta, "basic", [])
    except Exception:
        pass
    return slug, meta, offsets


@app.route("/api/preload/<slug>", methods=["GET"])
def preload_set(slug):
    """StageRuntime preload spec for a bundle — the SAME shape rehearsal,
    watch pages, and live all consume (PreloadSpec):
    {avatarUrl|null, portrait, audioUrl, plan, wordTimings, walkoutUrl}.
    Audio + performance are the READY gate; avatar is optional (§21):
    portrait carries the show until 3D is ready. Never black."""
    from backend.services.freaktown.bundle import (
        build_performance_manifest, bundle_to_score, estimate_spans,
        performance_avatar, resolve_avatar, spans_from_offsets,
        words_from_beats,
    )
    from backend.services.freaktown.cues import resolve_cues
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    if not bdir.is_dir() or not (bdir / "set.wav").exists():
        return jsonify({"ok": False, "error": "unknown set"}), 404
    try:
        character = json.loads((bdir / "character.json").read_text())
        delivery = json.loads((bdir / "delivery.json").read_text())
        meta = json.loads((bdir / "meta.json").read_text())
    except Exception:
        return jsonify({"ok": False, "error": "corrupt bundle"}), 500
    try:
        offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
    except Exception:
        offsets = []
    try:
        score = bundle_to_score(delivery)
    except ValueError as e:
        return jsonify({"ok": False, "error": f"invalid delivery: {e}"}), 422
    duration_ms = int(float(meta.get("duration_s", 0)) * 1000) or None
    spans = spans_from_offsets(offsets) if offsets else estimate_spans(
        delivery.get("beats", []), duration_ms)
    words = words_from_beats(delivery.get("beats", []), spans)
    by_id = {s.beat_id: s for s in spans}
    manifest = build_performance_manifest(
        f"local-{slug}", character, score, words, f"/freaks/{slug}/set.wav",
        duration_ms or (spans[-1].end_ms if spans else 0),
        avatar=performance_avatar(_avatar_record(slug)))
    cues = resolve_cues(manifest, offsets=offsets or None,
                        duration_ms=duration_ms)
    avatar_url, avatar_source = resolve_avatar(manifest)
    if avatar_source == "sealed":  # local R2 refs aren't fetchable here
        avatar_url, avatar_source = None, "none"
    portrait = f"/freaks/{slug}/portrait.png" if (bdir / "portrait.png").exists() else None
    walkout = None
    for f in ("walkout.mp3", "walkout.wav"):
        if (bdir / f).exists():
            walkout = f"/freaks/{slug}/{f}"
            break
    face_prof = {"profile": "NONE", "pog_face_v1": []}
    try:
        _fp = (json.loads((bdir / "avatar.json").read_text())
               .get("face_profile", {}) or {})
        face_prof = {"profile": _fp.get("profile", "NONE"),
                     "pog_face_v1": _fp.get("pog_face_v1", [])}
    except Exception:
        pass
    return jsonify({
        "ok": True, "slug": slug,
        "avatarUrl": avatar_url if avatar_source in ("local", "provided") else None,
        "avatarSource": avatar_source,
        "face_profile": face_prof,
        "portrait": portrait,
        "audioUrl": f"/freaks/{slug}/set.wav",
        "plan": {"duration_ms": manifest["audio"]["duration_ms"],
                 "cues": cues["motion"], "camera": cues["camera"],
                 "sfx": cues["sfx"]},
        "wordTimings": [{"word": w.word, "start_ms": w.start_ms,
                         "end_ms": w.end_ms, "index": i}
                        for i, w in enumerate(words)],
        "beats": [{"text": b.get("text", ""),
                   "start": by_id[b["id"]].start_ms,
                   "end": by_id[b["id"]].start_ms + by_id[b["id"]].speech_ms,
                   "face": (b.get("performance") or {}).get("expression", "neutral")}
                  for b in delivery.get("beats", []) if b.get("id") in by_id],
        "walkoutUrl": walkout,
        "manifest_sha": manifest["sha256"],
        "estimated": cues["estimated"],
    })


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


@app.route("/api/sets/<slug>/name", methods=["POST"])
def name_set(slug):
    """Give a set a permanent name: freak.town/<character>/<name>."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    meta = _bundle_meta(slug)
    if not meta:
        return jsonify({"ok": False, "error": "unknown set"}), 404
    name = re.sub(r"[^a-z0-9]+", "-", str((request.json or {}).get("set_name", "")).lower()).strip("-")[:45]
    if not name:
        return jsonify({"ok": False, "error": "set_name required"}), 400
    meta["set_name"] = name
    (FREAK_DIR / slug / "meta.json").write_text(json.dumps(meta, indent=2))
    return jsonify({"ok": True, "url": canonical_url(slug)})


@app.route("/api/sets/<slug>/submit", methods=["POST"])
def submit_set(slug):
    """Submit a saved set for the live show. Status: draft -> queued.
    Body opt: {"enter_show": true} — also forwards the bundle to the
    killella intake (KILLELLA_INTAKE_URL + KILLELLA_API_KEY env).
    Without env configured, submit stays local-only (never fails)."""
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
    out = {"ok": True, "slug": slug, "status": "queued"}
    if (request.json or {}).get("enter_show"):
        fwd = _forward_to_intake(slug, bdir)
        out["intake"] = fwd
    return jsonify(out)


def _intake_payload(slug: str, bdir) -> dict:
    """Build the exact killella IntakeRequest body for a bundle.
    Audio goes inline base64 (intake cap 10MB); offsets ride along when
    present so word timings are measured, not estimated."""
    import base64
    character = json.loads((bdir / "character.json").read_text())
    delivery = json.loads((bdir / "delivery.json").read_text())
    try:
        offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
    except Exception:
        offsets = []
    wav = (bdir / "set.wav").read_bytes()
    payload = {
        "character": {
            "name": character.get("name", "Guest Freak"),
            "species": character.get("species", ""),
            "premise": character.get("premise", ""),
            "vibe": character.get("vibe", ""),
            "voice": character.get("voice", "en-US-AriaNeural"),
        },
        "delivery": delivery,
        "episode_id": "00000000-0000-0000-0000-000000000000",
        "audio_base64": base64.b64encode(wav).decode(),
        "audio_format": "wav",
        "offsets": offsets,
        "duration_ms": int(meta_duration(bdir)),
        "style": ((_bundle_meta(slug) or {}).get("style") or ""),
    }
    walkout = bdir / "walkout.wav"
    if walkout.exists() and walkout.stat().st_size < 10_000_000:
        payload["walkout_base64"] = base64.b64encode(walkout.read_bytes()).decode()
    return payload


def meta_duration(bdir) -> float:
    try:
        return float((_bundle_meta(bdir.name) or {}).get("duration_s", 0)) * 1000
    except Exception:
        return 0


def _forward_to_intake(slug: str, bdir) -> dict:
    """POST the bundle to killella intake. Never raises (returns status)."""
    import os as _os
    url = _os.getenv("KILLELLA_INTAKE_URL", "").rstrip("/")
    if not url:
        return {"ok": False, "error": "KILLELLA_INTAKE_URL not configured"}
    try:
        import httpx
        r = httpx.post(
            f"{url}/v1/intake/bundle",
            json=_intake_payload(slug, bdir),
            headers={"X-API-Key": _os.getenv("KILLELLA_API_KEY", "")},
            timeout=120)
        if r.status_code in (200, 201):
            return {"ok": True, "intake": r.json()}
        return {"ok": False, "error": f"intake {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


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


def _vibe_recipe(char: dict, seed: int = 0) -> dict:
    """Character description → walkout recipe. Deterministic per vibe;
    new seed = reroll. Genres are the synth's own palette."""
    t = f"{char.get('vibe', '')} {char.get('premise', '')} {char.get('job', '')}".lower()
    if any(w in t for w in ("cocky", "absurd", "funk", "sleazy", "detective")):
        genre, mood, energy = "funk", "absurd", "high"
    elif any(w in t for w in ("dark", "angry", "heavy", "metal", "villain")):
        genre, mood, energy = "rock", "cocky", "high"
    elif any(w in t for w in ("neon", "robot", "space", "cyber", "sleek")):
        genre, mood, energy = "electronic", "sleazy", "high"
    elif any(w in t for w in ("sheepish", "silly", "goofy", "gentle", "sweet")):
        genre, mood, energy = "comedy", "sheepish", "medium"
    elif any(w in t for w in ("hero", "epic", "royal", "legend")):
        genre, mood, energy = "orchestral", "heroic", "high"
    else:
        genre, mood, energy = "funk", (char.get("vibe", "") or "confident")[:20], "high"
    return {"genre": genre, "mood": mood, "energy": energy,
            "shape": "hit", "duration": 8}


@app.route("/api/walkout/<slug>", methods=["POST"])
def walkout_for(slug):
    """Rerollable walkout: character description → sting, saved on bundle.
    Body: {} rerolls (random seed) or {"seed": N} to replay one.
    AR entrance + preload pick it up with no other changes."""
    import secrets
    import sound_synth
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if meta is None or not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set"}), 404
    data = request.json or {}
    try:
        seed = int(data.get("seed", secrets.randbelow(1 << 31)))
    except Exception:
        seed = 0
    recipe = _vibe_recipe((meta.get("character") or {}))
    full = {**recipe, "duration": 8}
    (bdir / "walkout.wav").write_bytes(sound_synth.generate(full, seed))
    (bdir / "walkout.json").write_text(json.dumps(
        {**recipe, "seed": seed, "provider": "procedural"}))
    return jsonify({"ok": True, "seed": seed, "recipe": recipe,
                    "url": f"/freaks/{slug}/walkout.wav"})


@app.route("/api/walkout", methods=["POST"])
def walkout():
    """Walkout sting from a recipe. Two engines, one contract.
    Body: {"genre","mood","energy","shape","seed", "mode": "instant"|"real"}
    - instant (default): procedural synth, <1s, free, exact duration
    - real: fal Stable Audio 3 Small, 10s, needs FAL_KEY, falls back to instant
    Cache key covers provider + model + prompt version + recipe + seed."""
    import sound_synth
    data = request.json or {}
    seed = int(data.get("seed", 0))
    mode = str(data.get("mode", "instant")).lower()
    # synth voice: "pattern" (default riff engine) or "melody" (seeded tune).
    # Explicit `melody` param wins; engine-mode "melody" is an accepted alias.
    _mel = str(data.get("melody", "") or "").lower()
    if _mel not in ("melody", "pattern"):
        _mel = "melody" if mode == "melody" else "pattern"
    recipe = {
        "genre": str(data.get("genre", "funk"))[:20],
        "mood": str(data.get("mood", "confident"))[:20],
        "energy": str(data.get("energy", "high"))[:20],
        "shape": str(data.get("shape", "hit"))[:20],
        "mode": _mel,
    }

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
                 "goldfish", "crab", "lamp", "elevator", "monkey", "ape"]
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


def _roll_character(locks: dict | None = None):
    """Roll a complete freak. Shared by /api/randomize and /api/respond."""
    import random as _r
    locks = locks or {}
    species = locks.get("species") or _r.choice(FREAK_SPECIES)
    job = locks.get("job") or _r.choice(FREAK_JOBS)
    vibe = locks.get("vibe") or _r.choice(FREAK_VIBES)
    name = locks.get("name") or f"{_r.choice(FREAK_NAMES)}"
    genre, mood = FREAK_WALKOUT.get(species, ("comedy", "absurd"))
    voice = FREAK_VOICES.get(vibe, "en-US-AriaNeural")
    premise = f"{vibe} {species} working as a {job}"
    return (
        {"name": name, "species": species, "job": job,
         "premise": premise, "vibe": vibe, "voice": voice},
        {"genre": genre, "mood": mood, "energy": "high",
         "shape": "hit", "duration": 8, "seed": _r.randint(0, 99999)},
    )


def _cf_chat(system: str, user: str, max_tokens: int = 500,
             temperature: float = 0.9) -> tuple[str | None, str | None]:
    """One CF Workers AI chat call. Returns (text, engine) or (None, None)."""
    import httpx
    tok, acct = _cf_creds()
    if not (tok and acct):
        return None, None
    for model in CF_MODELS:
        try:
            r = httpx.post(
                f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                json={"messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "max_tokens": max_tokens, "temperature": temperature},
                timeout=90)
            if r.status_code != 200:
                continue
            return _ai_text(r.json()), model.split("/")[-1]
        except Exception:
            continue
    return None, None


RESPONSE_MODES = {
    "roast": "roast them: attack the original freak, their premise, their closer. Mean but playful.",
    "yes_and": "yes-and them: extend their universe, add a worse character from the same world.",
    "random": "ignore their premise and come at a wild sideways angle that still answers the vibe.",
    "challenge": "challenge them: dare them on the weakest part of their set.",
}


def _seed_responses_async(slug: str):
    """Background-fill response_seeds so YOUR TURN never spins. Best effort."""
    import threading

    def _run():
        try:
            meta = _bundle_meta(slug)
            if not meta or meta.get("response_seeds"):
                return
            char = meta.get("character", {})
            context = f"{char.get('name', 'A comedian')} ({char.get('premise', '')})"
            try:
                delivery = json.loads((FREAK_DIR / slug / "delivery.json").read_text())
                beats = delivery.get("beats", [])
                closer = next((b.get("text", "") for b in reversed(beats)
                               if b.get("type") in ("punchline", "closer")), "")
            except Exception:
                closer = ""
            seeds = []
            for mode in ("roast", "yes_and", "random"):
                idea, _ = _cf_chat(
                    "You write one-line comedy premises for response sets. "
                    "One sentence, under 20 words, specific and roasty but playful. "
                    "No quotes, no explanation, just the premise.",
                    f"{RESPONSE_MODES[mode]} The act to answer: {context}. "
                    f"Their closer was: {closer}",
                    max_tokens=60, temperature=1.0)
                if idea:
                    seeds.append({"type": mode,
                                  "text": idea.strip().strip('"')[:200]})
            if seeds:
                meta = _bundle_meta(slug) or {}
                meta["response_seeds"] = seeds
                (FREAK_DIR / slug / "meta.json").write_text(json.dumps(meta, indent=2))
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


@app.route("/api/randomize", methods=["POST"])
def randomize():
    """Roll a complete freak: species, job, personality, voice, walkout.
    Body (all optional locks): {"species": "pigeon", "vibe": "paranoid"}"""
    data = request.json or {}
    character, walkout = _roll_character(data)
    return jsonify({"ok": True, "character": character, "walkout": walkout,
                    "prompt": f"Write a 60-second standup minute. The comedian is "
                              f"{character['name']}, a {character['vibe']} "
                              f"{character['species']} working as a {character['job']}."})


@app.route("/api/respond", methods=["POST"])
def respond():
    """One-shot response generation: roll freak + write minute + compose + save.
    Body: {"parent_slug": "...", "mode": "roast|yes_and|random|challenge",
           "idea": "optional premise override", "creator": "anon token"}.
    Returns the reply bundle ready to play in the same viewer."""
    import datetime
    data = request.json or {}
    parent_slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("parent_slug", "")))[:45]
    mode = str(data.get("mode", "roast")).lower()
    if mode not in RESPONSE_MODES:
        mode = "roast"
    pmeta = _bundle_meta(parent_slug)
    if not pmeta:
        return jsonify({"ok": False, "error": "unknown parent set"}), 404
    pchar = pmeta.get("character", {})
    try:
        pdelivery = json.loads((FREAK_DIR / parent_slug / "delivery.json").read_text())
        pbeats = pdelivery.get("beats", [])
        pcloser = next((b.get("text", "") for b in reversed(pbeats)
                        if b.get("type") in ("punchline", "closer")), "")
        ptext = " ".join(b.get("text", "") for b in pbeats)[:1200]
    except Exception:
        pcloser, ptext = "", ""

    character, walkout = _roll_character()
    idea = (data.get("idea") or "").strip()[:300]
    if not idea:
        idea, _ = _cf_chat(
            "You write one-line comedy premises for response sets. "
            "One sentence, under 20 words. No quotes, no explanation.",
            f"{RESPONSE_MODES[mode]} Answer this act: {pchar.get('name')} "
            f"({pchar.get('premise', '')}). Their closer: {pcloser}.",
            max_tokens=60, temperature=1.0)
        idea = (idea or f"Answer {pchar.get('name', 'them')} back, but meaner").strip().strip('"')

    minute, _ = _cf_chat(
        "You are a comedy writer for Freak Town. Write a 60-second standup minute. "
        "80-150 words. First line IS the joke. Escalating absurdity. Specific details. "
        "Killer closer under 10 words. Direct audience address. Stay in character voice. "
        "Reply ONLY with the set text, no title, no quotes.",
        f"You are {character['name']}, a {character['vibe']} {character['species']} "
        f"working as a {character['job']}. Answer back to this act with a {mode}: "
        f"{pchar.get('name')} said: {ptext}. Your angle: {idea}.",
        max_tokens=400, temperature=0.95)
    if not minute:
        return jsonify({"ok": False, "error": "minute generation failed, retry"}), 502

    beats = detect_beats(minute.strip().strip('"'))
    for b in beats:
        b.setdefault("pace", "normal")
        b.setdefault("performance", {"expression": "neutral", "gesture": "normal",
                                     "look": "audience"})
    try:
        slug, meta, offsets = _save_bundle({
            "character": character, "beats": beats, "voice": character["voice"],
            "walkout": walkout, "creator": str(data.get("creator") or "")[:64],
            "parent_slug": parent_slug,
        })
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "slug": slug, "url": canonical_url(slug),
                    "audio": f"/freaks/{slug}/set.wav",
                    "character": character, "idea": idea, "mode": mode,
                    "parent": parent_slug, "meta": meta, "beats": offsets})


@app.route("/takes", methods=["GET"])
def takes_browser():
    """Cross-pog take browser: every recorded take, newest first,
    playable in place with a link back to its pog."""
    import html as _html
    takes = _list_takes()[:60]
    cards = []
    for t in takes:
        cards.append(
            f"<div style='margin:14px auto;max-width:420px;background:#14141c;"
            f"border:1px solid #333;border-radius:10px;padding:10px'>"
            f"<div style='font-size:13px;margin-bottom:6px'>🎭 {_html.escape(t['name'])}"
            f" <span style='color:#666'>· {t['size_kb']}KB"
            f"{' · stems' if t['has_stems'] else ''}</span></div>"
            f"<video src='{t['url']}' controls playsinline preload='none' "
            f"style='width:100%;border-radius:8px;background:#000'></video>"
            f"<div style='font-size:12px;margin-top:6px'>"
            f"<a style='color:#00d4ff' href='/f/{t['slug']}'>watch {_html.escape(t['slug'])}</a>"
            f" · <a style='color:#00d4ff' href='/r/{t['slug']}'>record yours</a>"
            f" · <a style='color:#00d4ff' href='/revoice/{t['slug']}/{t['file']}'>revoice</a>"
            f"</div></div>")
    body = "\n".join(cards) or "<p style='text-align:center;color:#666'>No takes yet — be the first.</p>"
    page = ("""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Takes — Freak Town</title>
<style>*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#eee;font-family:monospace;padding:16px 10px 60px}
h1{text-align:center;font-size:16px;color:#ff2fa8;margin:6px 0 2px}
p.sub{text-align:center;color:#888;font-size:12px;margin-bottom:10px}
a.back{color:#fff}</style></head><body>
<h1>🎭 TAKES</h1><p class="sub">real people performing as pogs — newest first</p>
""" + body + "<p style='text-align:center;margin-top:18px'><a class='back' href='/'>← black room</a></p></body></html>")
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/f/<slug>")
@app.route("/w/<slug>")
def watch_set(slug):
    """Short watch URL. Canonical is /<character>/<set> once named."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    return _render_watch(slug)


@app.route("/<char>/<set>")
def watch_character_set(char, set):
    """Legacy non-@ spot: 301 to the canonical /@<char>/<set>.
    Kept so already-shared links never die; @ protects /live /studio /api /f."""
    from flask import redirect as _redirect
    slug = resolve_bundle(char, set)
    if not slug:
        return "No such set (yet). Make one in the Black Room.", 404
    canon = canonical_url(slug).replace("https://freak.town", "")
    if canon.startswith("/@"):
        return _redirect(canon, code=301)
    return _render_watch(slug)


def _char_bundles(char_slug: str) -> list[dict]:
    """All bundles whose character slug matches, newest first."""
    out = []
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if not meta:
            continue
        if _char_slug((meta.get("character", {}) or {}).get("name", "")) != char_slug:
            continue
        out.append((d.name, meta))
    out.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    return out


@app.route("/@<char>")
def character_page(char):
    """Character page: sets, history, rivals. Links never die (see /f/ alias)."""
    import html as _html
    char_slug = re.sub(r"[^a-z0-9-]", "", char)[:32]
    bundles = _char_bundles(char_slug)
    if not bundles:
        return "No freak by that name yet. Make one in the Black Room.", 404
    first_char = (bundles[0][1].get("character", {}) or {})
    name = _html.escape(first_char.get("name", char_slug))
    premise = _html.escape(first_char.get("premise", ""))
    # rivals: characters who replied to (or were replied by) this char's sets
    my_slugs = {s for s, _ in bundles}
    rivals: dict[str, int] = {}
    for _, m in bundles:
        lin = m.get("lineage") or {}
        if lin.get("parent"):
            try:
                pm = _bundle_meta(lin["parent"]) or {}
                rn = (pm.get("character", {}) or {}).get("name")
                if rn and rn != first_char.get("name"):
                    rivals[rn] = rivals.get(rn, 0) + 1
            except Exception:
                pass
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = _bundle_meta(d.name) or {}
        lin = m.get("lineage") or {}
        if lin.get("parent") in my_slugs:
            rn = (m.get("character", {}) or {}).get("name")
            if rn:
                rivals[rn] = rivals.get(rn, 0) + 1
    cards = []
    for slug, m in bundles:
        set_name = m.get("set_name") or slug
        url = canonical_url(slug).replace("https://freak.town", "")
        nreplies = sum(
            1 for d in FREAK_DIR.iterdir() if d.is_dir() and
            ((_bundle_meta(d.name) or {}).get("lineage") or {}).get("parent") == slug)
        cards.append(
            f"<a style='display:block;margin:8px auto;max-width:420px;padding:12px;"
            f"border:1px solid #282833;border-radius:12px;color:#eee;text-decoration:none' "
            f"href='{url}'><b>{_html.escape(set_name)}</b>"
            f"<div style='color:#888;font-size:12px;'>{m.get('duration_s', 0)}s · "
            f"{m.get('word_count', 0)} words · {nreplies} repl{'y' if nreplies == 1 else 'ies'}"
            f"</div></a>")
    rival_line = ("<p style='color:#888;'>RIVALS: " +
                  _html.escape(", ".join(sorted(rivals))) + "</p>") if rivals else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Freak Town</title>
<style>body{{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px}}
a{{color:#ff2fa8}}</style></head><body>
<div style="font-size:12px;letter-spacing:2px;color:#ff2fa8;">🎪 FREAK TOWN</div>
<h1>{name}</h1><p style="color:#888;">{premise}</p>
<p style="color:#555;">{len(bundles)} performance{'s' if len(bundles) != 1 else ''}</p>
{''.join(cards)}{rival_line}
<p><a href="/">＋ make your own freak</a></p>
</body></html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/@<char>/<set>")
def watch_character_set_canonical(char, set):
    """Canonical performance URL. /<char>/<set> and /f/<slug> keep working."""
    char_slug = re.sub(r"[^a-z0-9-]", "", char)[:32]
    slug = resolve_bundle(char_slug, set)
    if not slug:
        return "No such set (yet). Make one in the Black Room.", 404
    return _render_watch(slug)


# ── /perform: live stage (watch a freak perform) ──────────────────────
# Same player core as /f/<slug> (set.wav + beat captions + avatar + laugh
# buttons), wrapped in a live-night frame: bill, headliner, predicted-heat
# strip, finale verdict. Laugh-sim is HEURISTIC_V0 (type/position prior +
# characters' published 0.55/0.35 thresholds) until the real laugh model is
# vendored — the /api/perform/<slug>/heat contract is the swap-in point.

PERFORM_HEAT_MODEL = "heuristic-v0"
PERFORM_CROWD_P = 0.55   # characters crowd_sim: full crowd at/above
PERFORM_CHUCKLE_P = 0.35  # characters crowd_sim: chuckle band below crowd
_PERFORM_TYPE_P = {"punchline": 0.62, "tag": 0.50, "closer": 0.55,
                   "setup": 0.30}


def _perform_bundles() -> list:
    """Stage-ready bundles (set.wav present), newest first. Canonical
    player logic lives in _render_watch; this only lists the bill."""
    out = []
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if not meta or not (d / "set.wav").exists():
            continue
        out.append((d.name, meta))
    out.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    return out


_PERFORM_HEAT_CACHE: dict = {}


def _perform_model_p(slug: str) -> tuple:
    """Real laugh probabilities from characters' delivery-aware model
    (AUC 0.654, leave-one-comedian-out) via the numpy2 venv sidecar.
    Returns (model_name, {beat_id: p}). Cached per slug. Any failure ->
    empty (caller falls back to heuristic). Read-only on both repos."""
    import subprocess as _sp
    if slug in _PERFORM_HEAT_CACHE:
        return _PERFORM_HEAT_CACHE[slug]
    out = (PERFORM_HEAT_MODEL, {})
    try:
        r = _sp.run([str(Path(__file__).parent / ".venv-heat" / "bin" / "python"),
                     str(Path(__file__).parent / "scripts" / "heat_model.py"), slug],
                    capture_output=True, text=True, timeout=25)
        d = json.loads(r.stdout or "{}")
        if d.get("ok"):
            out = (d.get("model", PERFORM_HEAT_MODEL),
                   {b["id"]: b["p"] for b in d.get("beats", [])})
    except Exception:
        pass
    _PERFORM_HEAT_CACHE[slug] = out
    return out


def _perform_beats(slug: str) -> list:
    """Beat timeline + laugh probability. Mirrors the span logic
    in _render_watch (measured offsets, else shared estimator)."""
    from backend.services.freaktown.bundle import (
        estimate_spans, spans_from_offsets,
    )
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug) or {}
    try:
        delivery = json.loads((bdir / "delivery.json").read_text())
    except Exception:
        return []
    try:
        offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
    except Exception:
        offsets = []
    beats_in = delivery.get("beats", [])
    if not beats_in:
        return []
    duration_ms = int(float(meta.get("duration_s", 0)) * 1000) or None
    spans = spans_from_offsets(offsets) if offsets else estimate_spans(beats_in, duration_ms)
    by_id = {s.beat_id: s for s in spans}
    n = len(beats_in)
    model_name, model_p = _perform_model_p(slug)
    out = []
    for i, b in enumerate(beats_in):
        s = by_id.get(b.get("id"))
        if s is None:
            continue
        if b.get("id") in model_p:
            p, src = model_p[b["id"]], model_name
        else:
            base = _PERFORM_TYPE_P.get(str(b.get("type", "")).lower(), 0.35)
            ramp = min(1.25, 1.0 + 0.5 * (i / max(1, n - 1)))
            p, src = round(min(0.95, base * ramp), 3), PERFORM_HEAT_MODEL
        out.append({"text": b.get("text", ""), "start": s.start_ms,
                    "end": s.start_ms + s.speech_ms, "p_laugh": p,
                    "src": src,
                    "crowd": p >= PERFORM_CROWD_P,
                    "chuckle": PERFORM_CHUCKLE_P <= p < PERFORM_CROWD_P})
    return out


@app.route("/perform")
def perform_bill():
    """Tonight's bill: headliner + lineup. Every act is a stage-ready set."""
    import html as _html
    bill = _perform_bundles()
    if not bill:
        return "No acts ready yet. Make one in the Black Room.", 404
    head_slug, head_meta = bill[0]
    head_char = (head_meta.get("character", {}) or {}).get("name", head_slug)
    cards = []
    for slug, m in bill:
        char = (m.get("character", {}) or {}).get("name", slug)
        img = (f"/freaks/{slug}/portrait.png"
               if (FREAK_DIR / slug / "portrait.png").exists() else "/icon-512.png")
        cards.append(
            f"<a href='/perform/{slug}' style='display:inline-block;width:150px;margin:8px;"
            f"padding:10px;border:1px solid #282833;border-radius:12px;color:#eee;"
            f"text-decoration:none;vertical-align:top'>"
            f"<img src='{img}' style='width:100%;border-radius:8px'>"
            f"<div style='font-size:13px;margin-top:6px'>{_html.escape(char)}</div>"
            f"<div style='color:#666;font-size:11px'>{m.get('duration_s', 0)}s</div></a>")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TONIGHT — Freak Town Live</title>
<style>body{{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px}}
a{{color:#ff2fa8}}</style></head><body>
<div style="font-size:12px;letter-spacing:2px;color:#ff2fa8;">🎪 FREAK TOWN · LIVE</div>
<h1>TONIGHT'S BILL</h1>
<p style="color:#888;">Headliner: <a href="/perform/{head_slug}">{_html.escape(head_char)}</a></p>
<div>{''.join(cards)}</div>
<p style="color:#555;font-size:12px;margin-top:16px">{len(bill)} acts · pre-rendered sets,
live audience · predicted heat is heuristic v0</p>
</body></html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/cauldron")
def cauldron_concepts():
    """THE CAULDRON v1 concept gallery: draft frames + the prompts that made
    them. Owner reviews on phone, replies keep/kill per shot. Winners become
    Marble contextFrames anchors (atlasGenerate). Nothing here is a promise —
    drafts until gated per CAULDRON-PROFILE.md."""
    import html as _html
    import glob as _glob
    concept_dir = Path(__file__).parent / "static" / "concepts"
    metas = []
    for jf in sorted(concept_dir.glob("*.json")):
        try:
            metas.append(json.loads(jf.read_text()))
        except Exception:
            continue
    metas.sort(key=lambda m: m.get("generated_at", ""), reverse=True)
    cards = []
    for m in metas:
        shot = m.get("shot", "?")
        img = f"/static/concepts/{m.get('file', shot + '.jpg')}"
        g = m.get("gates", {})
        verdict = g.get("verdict", "unreviewed")
        vcolor = {"pass": "#7fdb7f", "fail": "#ff6b6b"}.get(verdict, "#888")
        anchor = "ANCHOR-OK" if m.get("anchor_eligible") else "vibe only"
        acolor = "#7fdb7f" if m.get("anchor_eligible") else "#888"
        cards.append(
            f"<figure class='card' data-verdict='{verdict}'>"
            f"<a href='{img}' target='_blank'>"
            f"<img src='{img}' alt='{_html.escape(shot)}: {_html.escape(m.get('prompt','')[:160])}' loading='lazy'></a>"
            f"<figcaption><b>🕯️ {_html.escape(shot)}</b> "
            f"<span class='badge' style='border-color:{vcolor};color:{vcolor}'>{verdict}</span> "
            f"<span class='badge' style='border-color:{acolor};color:{acolor}'>{anchor}</span>"
            f"<div class='meta'>{m.get('width',0)}x{m.get('height',0)} · "
            f"{_html.escape(str(m.get('model','')).split('/')[-1])} · "
            f"{_html.escape(str(m.get('status','')))}</div>"
            f"<details><summary>prompt + gates</summary><div class='prompt'>"
            f"{_html.escape(m.get('prompt',''))}</div>"
            f"<div class='meta'>{_html.escape(str(g))}</div></details>"
            f"</figcaption></figure>")
    body = "".join(cards) if cards else "<p>No frames yet.</p>"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THE CAULDRON — concept gallery v1</title>
<style>:root{{--tile:220px}}
body{{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:24px 12px;margin:0}}
a{{color:#ff2fa8}}
#bar{{position:sticky;top:0;background:#0a0a0f;padding:10px;z-index:5;border-bottom:1px solid #282833}}
#grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--tile),1fr));gap:12px;padding:16px 8px;max-width:1400px;margin:0 auto}}
.card{{margin:0;border:1px solid #282833;border-radius:12px;padding:8px;text-align:left;background:#111119}}
.card img{{width:100%;border-radius:8px;display:block;aspect-ratio:1/1;object-fit:cover}}
.card figcaption{{font-size:12px;margin-top:6px}}
.badge{{font-size:10px;border:1px solid #888;border-radius:8px;padding:0 6px}}
.meta{{color:#555;font-size:10px;margin-top:4px}}
.prompt{{color:#999;font-size:10px;margin-top:6px;line-height:1.5;white-space:pre-wrap}}
details summary{{cursor:pointer;color:#888;font-size:10px;margin-top:4px}}
button{{background:#1a1a2e;color:#eee;border:1px solid #333;border-radius:8px;padding:4px 10px}}
input[type=range]{{width:140px;vertical-align:middle}}</style></head><body>
<div id="bar">🕯️ THE CAULDRON · V1 · {len(cards)} frames · $0
<button onclick="zoom(-40)">−</button><input id="z" type="range" min="120" max="460" value="220" oninput="document.documentElement.style.setProperty('--tile',this.value+'px')">
<button onclick="zoom(40)">+</button>
<button onclick="filter('all')">all</button><button onclick="filter('pass')">pass</button><button onclick="filter('fail')">fail</button>
<a href="/perform" style="margin-left:8px">stage</a></div>
<div id="grid">{body}</div>
<p style="color:#555;font-size:11px">Gates: empty · no windows · shell-only ·
tap a frame to zoom · reply keep/kill per shot</p>
<script>function zoom(d){{var z=document.getElementById('z');z.value=+z.value+d;z.oninput();}}
function filter(v){{document.querySelectorAll('.card').forEach(c=>{{c.style.display=(v==='all'||c.dataset.verdict===v)?'':'none';}});}}</script>
</body></html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/cauldron.json")
def cauldron_concepts_json():
    """Machine-readable feed for ChatGPT/agents: every frame with absolute
    image URLs + full prompts + review status. No JS, no auth, CORS-open."""
    concept_dir = Path(__file__).parent / "static" / "concepts"
    items = []
    for jf in sorted(concept_dir.glob("*.json")):
        try:
            m = json.loads(jf.read_text())
        except Exception:
            continue
        m["image_url"] = f"https://funnier.si/static/concepts/{m.get('file', '')}"
        items.append(m)
    items.sort(key=lambda m: m.get("generated_at", ""), reverse=True)
    resp = jsonify({"venue": "the-cauldron", "version": "v1",
                    "gates": "empty/no-windows/bare-deck/chalk-sigil/<=30MB/3x-dingy",
                    "count": len(items), "frames": items})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/perform/<slug>/heat")
def perform_heat(slug):
    """Per-beat laugh prediction contract. v0 = heuristic prior; a vendored
    laugh model answers this same shape later. Never a laughter label —
    predictions only, observed laughs come from /api/react."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    beats = _perform_beats(slug)
    if not beats and not (FREAK_DIR / slug / "set.wav").exists():
        return jsonify({"ok": False, "error": "no such set"}), 404
    srcs = sorted({b.get("src", PERFORM_HEAT_MODEL) for b in beats})
    return jsonify({"ok": True, "slug": slug, "model": PERFORM_HEAT_MODEL,
                    "models": srcs,
                    "thresholds": {"crowd": PERFORM_CROWD_P,
                                   "chuckle": PERFORM_CHUCKLE_P},
                    "beats": beats})


@app.route("/api/perform/<slug>/acting")
def perform_acting(slug):
    """Deterministic acting timeline: delivery beats + measured offsets +
    character vibe profile -> timestamped expression/gesture/look/hold/
    camera events. No model, no randomness (seeded by beat id). This is the
    swap-in point for characters' jev_loop delivery profiles: same shape,
    richer values."""
    import hashlib as _hl
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug) or {}
    try:
        delivery = json.loads((bdir / "delivery.json").read_text())
    except Exception:
        return jsonify({"ok": False, "error": "no such set"}), 404
    try:
        from backend.services.freaktown.bundle import (
            estimate_spans, spans_from_offsets,
        )
        try:
            offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
        except Exception:
            offsets = []
        beats_in = delivery.get("beats", [])
        duration_ms = int(float(meta.get("duration_s", 0)) * 1000) or None
        spans = spans_from_offsets(offsets) if offsets else estimate_spans(beats_in, duration_ms)
        by_id = {s.beat_id: s for s in spans}
    except Exception:
        by_id = {}
    vibe = ((meta.get("character", {}) or {}).get("vibe", "")
            or (meta.get("character", {}) or {}).get("premise", ""))
    prof = profile_for_vibe(vibe)
    gf = prof.get("gesture_frequency", 0.3)
    hold_ms = prof.get("punchline_hold_ms", 850)
    events = []
    for b in delivery.get("beats", []):
        s = by_id.get(b.get("id"))
        if s is None:
            continue
        t, end = s.start_ms, s.start_ms + s.speech_ms
        perf = b.get("performance", {}) or {}
        btype = str(b.get("type", "")).lower()
        events.append({"t": t, "kind": "expression",
                       "value": perf.get("expression", "neutral")})
        events.append({"t": t, "kind": "look",
                       "value": perf.get("look", "audience")})
        gest = perf.get("gesture", "normal")
        seed = int(_hl.sha256(str(b.get("id", "")).encode()).hexdigest(), 16) % 1000 / 1000.0
        if gest and gest != "normal" and (btype in ("punchline", "tag", "closer") or seed < gf):
            events.append({"t": t, "kind": "gesture", "value": gest})
        if btype in ("punchline", "tag", "closer"):
            events.append({"t": end, "kind": "hold", "ms": hold_ms})
            events.append({"t": end, "kind": "camera", "value": "push-in"})
    events.sort(key=lambda e: e["t"])
    return jsonify({"ok": True, "slug": slug, "profile": prof, "events": events})


_PERFORM_BED_CACHE: dict = {}


@app.route("/api/perform/<slug>/crowd.wav")
def perform_crowd(slug):
    """Crowd ambience bed: real CC0 laugh clips at predicted moments, gain
    by p, applause swell at close. Ambience, not Foley — the room starts it
    with the set at low volume. Cached per slug in /tmp."""
    import struct as _st
    from flask import Response as _Resp
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    if not (bdir / "set.wav").exists():
        return "no such set", 404
    key = (slug, (bdir / "set.wav").stat().st_mtime)
    if key not in _PERFORM_BED_CACHE:
        sys.path.insert(0, str(Path(__file__).parent / "scripts"))
        import crowd as _crowd
        beats = _perform_beats(slug)
        meta = _bundle_meta(slug) or {}
        dur = int(float(meta.get("duration_s", 0)) * 1000)
        if not dur and beats:
            dur = max(b["end"] for b in beats) + 2000
        pcm, _ = _crowd.build_bed(beats, dur or 60000)
        wav = (b"RIFF" + _st.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
               + _st.pack("<IHHIIHH", 16, 1, 1, 24000, 24000 * 2, 2, 16)
               + b"data" + _st.pack("<I", len(pcm)) + pcm)
        p = Path("/tmp") / f"crowd-{slug}.wav"
        try:
            p.write_bytes(wav)
        except Exception:
            pass
        _PERFORM_BED_CACHE[key] = bytes(wav)
    return _Resp(_PERFORM_BED_CACHE[key], mimetype="audio/wav",
                 headers={"Cache-Control": "public, max-age=3600"})


_PERFORM_SIG: dict = {}
_PERFORM_PRESENCE: dict = {}


@app.route("/api/perform/<slug>/signal", methods=["GET", "POST"])
def perform_signal(slug):
    """Minimal WebRTC signaling for the stage monitor: audience publishes,
    performer subscribes. {from, kind: offer/answer/ice, payload} in;
    ?since=seq out. In-memory only, never persisted, never logged."""
    import time as _time
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    box = _PERFORM_SIG.setdefault(slug, {"seq": 0, "msgs": []})
    if request.method == "POST":
        data = request.json or {}
        frm = re.sub(r"[^a-zA-Z0-9_-]", "", str(data.get("frm", "")))[:24]
        kind = str(data.get("kind", ""))
        if not frm or kind not in ("offer", "answer", "ice", "bye"):
            return jsonify({"ok": False, "error": "bad signal"}), 400
        payload = data.get("payload")
        box["seq"] += 1
        box["msgs"].append({"seq": box["seq"], "t": _time.time(),
                            "frm": frm, "kind": kind, "payload": payload})
        box["msgs"] = box["msgs"][-200:]
        return jsonify({"ok": True, "seq": box["seq"]})
    try:
        since = int(request.args.get("since", 0))
    except Exception:
        since = 0
    return jsonify({"ok": True, "seq": box["seq"],
                    "msgs": [m for m in box["msgs"] if m["seq"] > since]})


@app.route("/api/perform/<slug>/presence", methods=["GET", "POST"])
def perform_presence(slug):
    """Who's in the room and how: face (on monitor) or pip (smile-only).
    Heartbeat-pruned (>20s stale vanishes). No identities beyond a nickname."""
    import time as _time
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    room = _PERFORM_PRESENCE.setdefault(slug, {})
    now = _time.time()
    for k in [k for k, v in room.items() if now - v.get("t", 0) > 20]:
        del room[k]
    if request.method == "POST":
        data = request.json or {}
        frm = re.sub(r"[^a-zA-Z0-9_-]", "", str(data.get("frm", "")))[:24]
        mode = str(data.get("mode", "pip"))
        if not frm or mode not in ("face", "pip"):
            return jsonify({"ok": False, "error": "bad presence"}), 400
        room[frm] = {"frm": frm, "mode": mode, "t": now,
                     "nick": re.sub(r"[^a-zA-Z0-9 _-]", "",
                                    str(data.get("nick", "")))[:24]}
        return jsonify({"ok": True})
    return jsonify({"ok": True, "here": sorted(room.values(), key=lambda v: v["frm"])})


@app.route("/perform/<slug>/monitor")
def perform_monitor(slug):
    """Comedian's monitor: look out and see the room. Live faces for
    audience who opted into APPEAR, glow pips + counts for everyone else.
    Consent-separate from face TRACKING (which never leaves the device).
    Nothing here is recorded — no recording code exists on this route.
    ?venue=<id> runs this room on that venue's crowd physics."""
    import html as _html
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    meta = _bundle_meta(slug) or {}
    name = _html.escape((meta.get("character", {}) or {}).get("name", slug))
    me = "mon_" + re.sub(r"[^a-z0-9]", "", slug)[:8]
    physics = {"decay": 0.88, "laugh_gain": 0.15, "resist_start": 0.5,
               "venue": "house"}
    vid = re.sub(r"[^a-z0-9-]", "", request.args.get("venue", ""))[:32]
    if vid:
        try:
            vv = json.loads((Path(__file__).parent / "docs" / "venues" / f"{vid}.json").read_text())
            ph = vv.get("physics", {})
            physics = {"decay": float(ph.get("decay", 0.88)),
                       "laugh_gain": float(ph.get("laugh_gain", 0.15)),
                       "resist_start": float(ph.get("resist_start", 0.5)),
                       "venue": vid}
        except Exception:
            pass
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MONITOR — {name}</title>
<style>body{{background:#050508;color:#eee;font-family:monospace;text-align:center;padding:16px}}
#faces{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:12px 0}}
#faces video{{width:160px;border-radius:10px;border:2px solid #ff2fa8}}
#pips{{font-size:28px;min-height:40px}}
.tick{{color:#555;font-size:11px}}</style></head><body>
<div style="color:#ff2fa8;letter-spacing:3px;font-size:12px">🎤 STAGE MONITOR — {name}</div>
<p class="tick">only opted-in faces appear · nothing is recorded · pips = smile-only crowd</p>
<div id="faces"></div>
<div id="pips"></div>
<div class="tick"><span id="nface">0</span> faces · <span id="npip">0</span> pips · room reacts below</div>
<div id="energy" style="max-width:520px;margin:10px auto;padding:10px;border:1px solid #282833;border-radius:12px">
<div style="font-size:11px;color:#888;letter-spacing:2px">ROOM ENERGY</div>
<div id="emeter" style="height:14px;border-radius:7px;background:#222;margin:8px 0"></div>
<div id="rmeter" title="room resistance: laughs melt it, boos rebuild it"
 style="height:6px;border-radius:3px;background:#222;margin:4px 0"></div>
<div id="everdict" style="font-size:16px">…waiting for the room…</div>
<div class="tick" id="esplit"></div></div>
<div id="reactlog" style="max-width:520px;margin:10px auto;text-align:left;font-size:13px"></div>
<script>
var SLUG={json.dumps(slug)}, ME={json.dumps(me)}, mySeq=0, pcs={{}};
function api(p, body){{
  return fetch('/api/perform/'+SLUG+p, {{
    method: body ? 'POST' : 'GET',
    headers: {{'Content-Type': 'application/json'}},
    body: body ? JSON.stringify(body) : undefined }}).then(function(r){{return r.json()}});
}}
function logReact(t, extra){{
  var d = document.createElement('div'); d.textContent = t;
  var box = document.getElementById('reactlog');
  box.prepend(d); while (box.children.length > 12) box.lastChild.remove();
}}
// roster: faces + pips
setInterval(function(){{
  api('/presence').then(function(j){{
    var faces = 0, pips = 0, html = '';
    (j.here || []).forEach(function(p){{
      if (p.mode === 'face') {{ faces++; }}
      else {{ pips++; html += '😄 '; }}
    }});
    document.getElementById('nface').textContent = faces;
    document.getElementById('npip').textContent = pips;
    document.getElementById('pips').textContent = html;
  }}).catch(function(){{}});
}}, 3000);
// answer incoming face offers
setInterval(function(){{
  api('/signal?since=' + mySeq).then(function(j){{
    mySeq = j.seq || mySeq;
    (j.msgs || []).forEach(function(m){{
      if (m.frm === ME) return;
      if (m.kind === 'offer' && !pcs[m.frm]) answer(m);
      else if (m.kind === 'ice' && pcs[m.frm]) pcs[m.frm].pc.addIceCandidate(m.payload).catch(function(){{}});
      else if (m.kind === 'bye' && pcs[m.frm]) dropPeer(m.frm);
    }});
  }}).catch(function(){{}});
}}, 1500);
function dropPeer(frm){{
  try {{ pcs[frm].pc.close(); }} catch (e) {{}}
  var v = document.getElementById('v-' + frm); if (v) v.remove();
  delete pcs[frm]; refreshFaces();
}}
function refreshFaces(){{
  document.getElementById('nface').textContent = Object.keys(pcs).length;
}}
function answer(m){{
  var pc = new RTCPeerConnection({{iceServers: [{{urls: 'stun:stun.l.google.com:19302'}}]}});
  pcs[m.frm] = {{pc: pc}};
  pc.ontrack = function(ev){{
    var v = document.getElementById('v-' + m.frm);
    if (!v) {{
      v = document.createElement('video');
      v.id = 'v-' + m.frm; v.autoplay = true; v.playsInline = true; v.muted = true;
      document.getElementById('faces').appendChild(v);
    }}
    v.srcObject = ev.streams[0]; refreshFaces();
  }};
  pc.onicecandidate = function(ev){{
    if (ev.candidate) api('/signal', {{frm: ME, kind: 'ice', payload: ev.candidate}});
  }};
  pc.setRemoteDescription(m.payload).then(function(){{ return pc.createAnswer(); }})
    .then(function(a){{ return pc.setLocalDescription(a).then(function(){{
      api('/signal', {{frm: ME, kind: 'answer', payload: pc.localDescription}});
    }}); }}).catch(function(){{ dropPeer(m.frm); }});
}}
// room laugh feed (boolean events the room already emits)
// Crowd physics ported from characters' laugh_timeline.CrowdState:
// heat *= 0.88 per event, +0.15 per laugh (cap 1.0), contagion ±1 (cap 5).
// Plus wall-clock bleed (×0.88 per 10s silence) so the bar visibly decays
// live. Real weights file pending; dynamics are the documented ones.
var lastReact = 0;
var DECAY = __DECAY__, GAIN = __GAIN__;
var heat = 0, contagion = 0, resist = __RESIST__, lastHeatT = Date.now();
var VENUE = __VENUE__;
var state = 'COLD';
function bleedHeat() {{
  var gaps = Math.floor((Date.now() - lastHeatT) / 10000);
  for (var i = 0; i < gaps; i++) {{ heat *= DECAY; resist = Math.min(1, resist + 0.01); }}
  if (gaps > 0) lastHeatT = Date.now();
}}
// Guitar-hero states with hysteresis: step down needs heat 0.15 lower
// than the step up took, so the room holds a state it earned.
function crowdState() {{
  if (state === 'KILLED') return heat >= 0.70 ? 'KILLED' : 'HOT';
  if (state === 'HOT') return heat >= 0.85 ? 'KILLED' : (heat >= 0.45 ? 'HOT' : 'WARM');
  if (state === 'WARM') return heat >= 0.6 ? 'HOT' : (heat >= 0.15 ? 'WARM' : 'COLD');
  return heat >= 0.3 ? 'WARM' : 'COLD';
}}
setInterval(function() {{ bleedHeat(); paintEnergy(); }}, 2000);
var energyLog = [];
function scoreE(r) {{
  if (r === 'hahaha') return 2;
  if (r === 'haha' || r === 'laugh' || r === 'smile') return 1;
  if (r === 'cheer' || r === 'clap') return 0.5;
  if (r === 'boo') return -1;
  return 0;
}}
function paintEnergy() {{
  bleedHeat();
  var cutoff = Date.now() - 15000, byType = {{}};
  energyLog = energyLog.filter(function(x) {{ return x.at > cutoff; }});
  energyLog.forEach(function(x) {{ byType[x.r] = (byType[x.r] || 0) + 1; }});
  state = crowdState();
  var pct = Math.round(heat * 100);
  document.getElementById('emeter').style.background =
    'linear-gradient(90deg,#ff2fa8 ' + pct + '%,#222 ' + pct + '%)';
  var v = document.getElementById('everdict');
  var faces = {{COLD: ['🧊 COLD ROOM', '#888'], WARM: ['🙂 warming up', '#eee'],
                HOT: ['🔥 THE ROOM IS HOT', '#ff2fa8'], KILLED: ['💀 KILLED (live)', '#ff2fa8']}};
  v.textContent = faces[state][0];
  v.style.color = faces[state][1];
  if (state === 'COLD' && energyLog.length > 3) v.textContent = '🍅 tough crowd';
  var rpct = Math.round(resist * 100);
  document.getElementById('esplit').textContent =
    'heat ' + heat.toFixed(2) + ' · resistance ' + rpct + '% · contagion ' + contagion + ' · ' +
    (Object.keys(byType).map(function(k) {{ return k + '×' + byType[k]; }}).join(' · ') || 'no signals yet');
  var rb = document.getElementById('rmeter');
  if (rb) rb.style.background =
    'linear-gradient(90deg,#888 ' + rpct + '%,#222 ' + rpct + '%)';
}}
setInterval(function(){{
  fetch('/api/react/feed?slug=' + SLUG + '&since=' + lastReact).then(function(r){{ return r.json(); }})
    .then(function(j){{
      (j.events || []).forEach(function(e){{
        lastReact = Math.max(lastReact, e.seq || 0);
        energyLog.push({{at: Date.now(), s: scoreE(e.reaction), r: e.reaction}});
        heat *= DECAY;
        var laughish = (e.reaction === 'haha' || e.reaction === 'hahaha' ||
                        e.reaction === 'laugh' || e.reaction === 'smile');
        if (laughish) {{
          heat = Math.min(1, heat + GAIN / (1 + resist));
          resist = Math.max(0, resist - 0.06);
          contagion = Math.min(5, contagion + 1);
        }}
        else {{
          contagion = Math.max(0, contagion - 1);
          if (e.reaction === 'boo') resist = Math.min(1, resist + 0.10);
        }}
        lastHeatT = Date.now();
        logReact('😄 ' + (e.reaction || 'laugh') + (e.nick ? ' — ' + e.nick : ''));
      }});
      paintEnergy();
    }}).catch(function(){{}});
}}, 2500);
</script></body></html>"""
    page = page.replace("__DECAY__", repr(physics["decay"]))
    page = page.replace("__GAIN__", repr(physics["laugh_gain"]))
    page = page.replace("__RESIST__", repr(physics["resist_start"]))
    page = page.replace("__VENUE__", json.dumps(physics["venue"]))
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


_KILLED_ENERGY = 12.0   # total weighted energy across the set
_KILLED_COVERAGE = 0.5  # fraction of beats with >=1 laugh-ish tap
_KILLED_CREATORS = 3    # distinct tappers (one fan can't kill alone)
_KILLED_BOOS = 1        # max boos tolerated
_VERDICT_W = {"hahaha": 2.0, "haha": 1.0, "laugh": 1.0, "smile": 1.0,
              "cheer": 0.5, "clap": 0.5, "boo": -1.0}


@app.route("/api/perform/<slug>/verdict")
def perform_verdict(slug):
    """Definitive KILLED badge. Hard on purpose: big energy AND broad
    coverage AND a real crowd (distinct tappers) AND (almost) no boos.
    Computed from the reaction log at finale time."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    try:
        lines = (Path(__file__).parent / "reactions.jsonl").read_text().splitlines()
    except Exception:
        lines = []
    import time as _time
    energy, boos, creators = 0.0, 0, set()
    hit_beats: set = set()
    beats = _perform_beats(slug)
    week_ago = _time.time() - 7 * 86400  # a kill is recent room life, not history
    for ln in lines:
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("slug") != slug or e.get("t", 0) < week_ago:
            continue
        r = e.get("reaction", "")
        energy += _VERDICT_W.get(r, 0)
        if r == "boo":
            boos += 1
        if e.get("creator"):
            creators.add(e["creator"])
        if r in ("haha", "hahaha", "laugh", "smile"):
            t = e.get("set_time_ms", 0)
            for i, b in enumerate(beats):
                if b["start"] - 500 <= t < b["end"] + 2500:
                    hit_beats.add(i)
                    break
    coverage = len(hit_beats) / max(1, len(beats))
    killed = (energy >= _KILLED_ENERGY and coverage >= _KILLED_COVERAGE
              and len(creators) >= _KILLED_CREATORS and boos <= _KILLED_BOOS
              and len(beats) > 0)
    return jsonify({"ok": True, "slug": slug, "killed": killed,
                    "energy": round(energy, 1), "coverage": round(coverage, 2),
                    "creators": len(creators), "boos": boos,
                    "bars": {"energy": _KILLED_ENERGY,
                             "coverage": _KILLED_COVERAGE,
                             "creators": _KILLED_CREATORS, "boos": _KILLED_BOOS}})


_LAUGH_DIR = Path(__file__).parent / "audio_output" / "laughs"
_LAUGH_MAX = 50


@app.route("/api/laughs", methods=["POST"])
def upload_laugh():
    """Opt-in personal laugh sample. {b64: webm/opus data URL or raw b64,
    <=200KB}. Stored by random id, served unlisted. No listing endpoint.
    Delete by asking (owner tool) — no account system to self-serve."""
    import base64 as _b64
    import secrets as _sec
    data = request.json or {}
    raw = str(data.get("b64", ""))
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        blob = _b64.b64decode(raw, validate=True)
    except Exception:
        return jsonify({"ok": False, "error": "bad audio"}), 400
    if not (1024 <= len(blob) <= 200 * 1024):
        return jsonify({"ok": False, "error": "need 1KB-200KB"}), 400
    if blob[:4] != b"\x1a\x45\xdf\xa3" and blob[:4] != b"RIFF":
        return jsonify({"ok": False, "error": "webm or wav only"}), 400
    try:
        _LAUGH_DIR.mkdir(parents=True, exist_ok=True)
        existing = sorted(_LAUGH_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime)
        while len(existing) >= _LAUGH_MAX:
            existing.pop(0).unlink(missing_ok=True)
        lid = _sec.token_hex(8)
        (_LAUGH_DIR / f"{lid}.webm").write_bytes(blob)
    except Exception:
        return jsonify({"ok": False, "error": "store failed"}), 500
    return jsonify({"ok": True, "laugh_id": lid})


@app.route("/api/laughs/<lid>")
def serve_laugh(lid):
    lid = re.sub(r"[^a-z0-9]", "", lid)[:32]
    p = _LAUGH_DIR / f"{lid}.webm"
    if not p.exists():
        return jsonify({"ok": False, "error": "no such laugh"}), 404
    return send_file(str(p), mimetype="audio/webm",
                     headers={"Cache-Control": "public, max-age=86400"})


@app.route("/api/venue/<vid>")
def venue_manifest(vid):
    """Venue truth: profile, props, light rig, physics, acoustics. Rooms
    reference venues by id; GLB by hash, never latest."""
    vid = re.sub(r"[^a-z0-9-]", "", vid)[:32]
    p = Path(__file__).parent / "docs" / "venues" / f"{vid}.json"
    if not p.exists():
        return jsonify({"ok": False, "error": "no such venue"}), 404
    try:
        return jsonify({"ok": True, "venue": json.loads(p.read_text())})
    except Exception:
        return jsonify({"ok": False, "error": "bad venue file"}), 500


@app.route("/venues/<path:filename>")
def venue_file(filename):
    """Local venue meshes (var/venues, gitignored). GLBs pinned by sha256
    in the venue JSON — referenced by hash, never latest."""
    if "/" in filename or not (filename.endswith(".glb") or filename.endswith(".spz") or filename.endswith(".vrm")):
        return jsonify({"ok": False, "error": "glb/spz/vrm only"}), 400
    mime = "model/gltf-binary" if filename.endswith((".glb", ".vrm")) else "application/octet-stream"
    # pinned by sha256 in venue JSON = immutable content: cache hard so the
    # big download happens once per phone, never every visit.
    resp = send_from_directory(str(Path(__file__).parent / "var" / "venues"),
                               filename, mimetype=mime)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# Second-screen pairing (YouTube-on-TV pattern, party-code logic).
# TV shows a 4-letter code; phones join at /code. Controllers post
# reactions; the TV polls the feed and drives shared energy. Ephemeral:
# codes die with the process. Smile/mic are boolean presence only.
PAIR = {}
PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _pair_code():
    import secrets as _secrets
    while True:
        code = "".join(_secrets.choice(PAIR_ALPHABET) for _ in range(4))
        if code not in PAIR:
            return code


@app.route("/api/venue/<vid>/pair", methods=["POST"])
def venue_pair(vid):
    vid = re.sub(r"[^a-z0-9-]", "", vid)[:32]
    code = _pair_code()
    PAIR[code] = {"code": code, "venue": vid, "seq": 0, "events": [],
                  "members": 0, "t": time.time()}
    return jsonify({"ok": True, "code": code})


@app.route("/api/pair/<code>", methods=["GET"])
def pair_join(code):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:8]
    r = PAIR.get(code)
    if not r:
        return jsonify({"ok": False, "error": "no such code"}), 404
    r["members"] += 1
    return jsonify({"ok": True, "venue": r["venue"], "members": r["members"]})


@app.route("/api/pair/<code>/react", methods=["POST"])
def pair_react(code):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:8]
    r = PAIR.get(code)
    if not r:
        return jsonify({"ok": False, "error": "no such code"}), 404
    data = request.get_json(force=True, silent=True) or {}
    kind = str(data.get("kind", ""))[:12]
    if kind not in ("laugh", "haha", "boo", "clap", "cheer", "smile", "mic"):
        return jsonify({"ok": False, "error": "bad kind"}), 400
    r["seq"] += 1
    ev = {"seq": r["seq"], "kind": kind, "t": time.time(),
          "by": re.sub(r"[^\w -]", "", str(data.get("name", "guest")))[:16]}
    r["events"].append(ev)
    r["events"] = r["events"][-200:]
    return jsonify({"ok": True, "seq": r["seq"]})


@app.route("/api/pair/<code>/kill", methods=["POST"])
def pair_kill(code):
    """Mod KILL switch (censor step 1): TV cuts to standby card on next poll.
    No auth yet (unlisted codes only) — monitor auth lands with it."""
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:8]
    r = PAIR.get(code)
    if not r:
        return jsonify({"ok": False, "error": "no such code"}), 404
    data = request.get_json(force=True, silent=True) or {}
    r["seq"] += 1
    ev = {"seq": r["seq"], "kind": "kill" if data.get("killed", True) else "resume",
          "t": time.time(), "by": "mod"}
    r["events"].append(ev)
    r["events"] = r["events"][-200:]
    return jsonify({"ok": True, "seq": r["seq"]})


@app.route("/api/pair/<code>/feed")
def pair_feed(code):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:8]
    r = PAIR.get(code)
    if not r:
        return jsonify({"ok": False, "error": "no such code"}), 404
    try:
        since = int(request.args.get("since", 0))
    except ValueError:
        since = 0
    return jsonify({"ok": True, "seq": r["seq"], "members": r["members"],
                    "events": [e for e in r["events"] if e["seq"] > since]})


@app.route("/venue/<vid>")
def venue_stage(vid):
    """P0 venue stage: Marble room views as the walls + VRM performer +
    procedural mic. v0 uses generated-view textures; swaps to the pinned
    GLB the moment cauldron.json carries a real glb.sha256."""
    vid = re.sub(r"[^a-z0-9-]", "", vid)[:32]
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THE CAULDRON — live stage v0</title>
<style>html,body{{margin:0;height:100%;background:#000;overflow:hidden;font-family:monospace}}
#ui{{position:fixed;top:8px;left:8px;z-index:5;color:#eee;font-size:12px;background:rgba(10,10,15,.7);padding:8px 10px;border-radius:10px;border:1px solid #282833}}
#ui button{{background:#1a1a2e;color:#eee;border:1px solid #333;border-radius:8px;padding:4px 10px;margin:2px}}
#ui a{{color:#ff2fa8}}</style>
<script type="importmap">
{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/","@pixiv/three-vrm":"https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.0/lib/three-vrm.module.js","three-vrm-animation":"https://cdn.jsdelivr.net/npm/@pixiv/three-vrm-animation@3.3.0/lib/three-vrm-animation.module.min.js","@sparkjsdev/spark":"https://sparkjs.dev/releases/spark/2.3.1/spark.module.js","three-vrm-lip-sync":"https://cdn.jsdelivr.net/npm/three-vrm-lip-sync@0.1.0/dist/index.min.js","wlipsync":"https://cdn.jsdelivr.net/npm/wlipsync@1.3.1/dist/wlipsync-single.min.js","wawa-lipsync":"https://cdn.jsdelivr.net/npm/wawa-lipsync@0.0.2/dist/wawa-lipsync.es.js"}}}}
</script></head><body>
<div id="ui">🕯️ <span id="vname">{vid}</span> · v0 room-views + live body<br>
<span id="cams"></span><br><button id="play">▶ PLAY SET (biscuit)</button>
<button id="rec">● REC</button>
<button id="room">ROOM: ON</button>
<button id="tvbtn" title="pair a phone">📱</button>
<a href="/cauldron">concepts</a> · <a href="/perform">stage</a>
<div id="msg" style="color:#888">loading room…</div>
<div id="blog" style="color:#555;font-size:10px;margin-top:4px;text-align:left;max-height:120px;overflow:auto"></div>
<div style="margin-top:4px">ROOM ENERGY <span id="emeter" style="color:#ff2fa8">░░░░░░░░░░</span>
<button id="laugh">😄</button><button id="boo">👎</button></div></div>
<canvas id="c" style="width:100%;height:100%;display:block"></canvas>
<script>
(function () {{
  var el = document.getElementById('msg');
  function say(t) {{ el.textContent = 'probe: ' + t; }}
  try {{
    if (!window.fetch) return say('no fetch API');
    var c = document.createElement('canvas');
    var gl2 = c.getContext('webgl2');
    if (!gl2) {{
      var gl1 = c.getContext('webgl') || c.getContext('experimental-webgl');
      return say(gl1 ? 'WebGL1 only — need WebGL2' : 'NO WebGL at all (private mode? old browser?)');
    }}
    var dbg = gl2.getExtension('WEBGL_debug_renderer_info');
    var gpu = dbg ? gl2.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unknown gpu';
    say('WebGL2 ok (' + String(gpu).slice(0, 60) + '), loading 3D libs…');
  }} catch (e) {{ say('probe failed: ' + e.message); }}
}})();
</script>
<script type="module">
import * as THREE from 'three';
import {{ GLTFLoader }} from 'three/addons/loaders/GLTFLoader.js';
import {{ VRMLoaderPlugin, VRMUtils }} from '@pixiv/three-vrm';
import {{ MeshoptDecoder }} from 'three/addons/libs/meshopt_decoder.module.js';
import {{ VRMAnimationLoaderPlugin, createVRMAnimationClip }} from 'three-vrm-animation';
import {{ SparkRenderer, SplatMesh }} from '@sparkjsdev/spark';
import {{ VRMLipSync }} from 'three-vrm-lip-sync';
import {{ Lipsync as WawaLipsync }} from 'wawa-lipsync';
const VID = '{vid}';
// ?lipsync=wawa|mfcc — challenger engine AB. Default mfcc (incumbent).
const LIPENGINE = new URLSearchParams(location.search).get('lipsync') || 'mfcc';
// Oculus-15 → VRM-5 map (v1 approximations, documented, AB-tested).
const WAWA_MAP = {{sil: null, PP: ['ou', 0.5], FF: ['ih', 0.6], TH: ['ih', 0.5],
  DD: ['ee', 0.6], kk: ['aa', 0.4], CH: ['oh', 0.6], SS: ['ih', 0.7],
  nn: ['ee', 0.4], RR: ['ou', 0.6], aa: ['aa', 1.0], E: ['ee', 0.9],
  I: ['ih', 0.9], O: ['oh', 0.9], U: ['ou', 0.9]}};
let wawa = null;
function driveWawa() {{
  if (!wawa || !vrm || !vrm.expressionManager) return null;
  try {{
    wawa.processAudio();
    const key = String(wawa.viseme || '').replace('viseme_', '');
    const mgr = vrm.expressionManager;
    const all = mgr.expressions.map(e => e.expressionName);
    ['aa','ih','ou','ee','oh'].forEach(n => {{ if (all.includes(n)) try {{ mgr.setValue(n, 0); }} catch (e) {{}} }});
    const hit = WAWA_MAP[key];
    if (hit && all.includes(hit[0])) {{ mgr.setValue(hit[0], hit[1]); return key; }}
    return 'sil';
  }} catch (e) {{ return null; }}
}}
const boot = [];
const blog = (t) => {{ try {{ const b = document.getElementById('blog'); b.innerHTML += '• ' + t + '<br>'; const lines = b.innerHTML.split('<br>'); if (lines.length > 9) b.innerHTML = lines.slice(-9).join('<br>'); }} catch (e) {{}} }};
const msg = (t) => {{ boot.push(t); blog(t); document.getElementById('msg').textContent = t; }};
window.addEventListener('error', (e) => {{ msg('JS ERROR: ' + (e.message || e.type)); }});
window.addEventListener('unhandledrejection', (e) => {{ msg('LOAD FAILED: ' + (e.reason && e.reason.message || e.reason)); }});
msg('step 1/5: imports ok, fetching venue…');
const v = await (await fetch('/api/venue/' + VID)).json().then(j => j.venue);
msg('step 2/5: venue ok, starting WebGL…');
document.getElementById('vname').textContent = v.name + ' · ' + v.size;
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{canvas, antialias: true}});
renderer.setSize(innerWidth, innerHeight);
// look: filmic tone curve + slight lift. Cheap, no deps, works on phones.
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
// P0: shadows OFF — SwiftShader/ANGLE fails MToon+spot-shadow compile
// (vSpotShadowCoord), which eats the performer. Room+body first.
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050508);
const camera = new THREE.PerspectiveCamera(46, innerWidth/innerHeight, 0.1, 100);
// room shell from venue dims (origin at stage front-center, meters)
const R = v.room, S = v.stage;
const tex = (u) => new THREE.TextureLoader().load(u);
const wallMat = (u) => new THREE.MeshBasicMaterial({{map: tex(u)}});
const dark = new THREE.MeshBasicMaterial({{color: 0x0a0a0e}});
// room: SPLAT first (photoreal, World Labs Spark fuses splat+mesh in one
// scene), pinned GLB second, generated-view box last. Chain degrades
// gracefully — whatever fails, the show still has walls.
let roomGLB = false;
const NOBG = new URLSearchParams(location.search).get('nobg') === '1';
// ?style= splat|mesh|box|void — the Cauldron is a MOTIF, not a file.
// Same night renders photoreal (splat), stylized (mesh), graphic (box),
// or void (performer only). Falls through the chain until something holds.
const STYLE = new URLSearchParams(location.search).get('style') || 'auto';
const wantSplat = !NOBG && (STYLE === 'auto' || STYLE === 'splat');
const wantMesh = !NOBG && (STYLE === 'auto' || STYLE === 'mesh');
if (v.splat && v.splat.local && wantSplat) {{
  try {{
    msg('step 3/5: downloading splat room (watch the counter)…');
    const spark = new SparkRenderer({{renderer}});
    scene.add(spark);
    const splat = new SplatMesh({{url: v.splat.local}});
    await new Promise((resolve, reject) => {{
      const iv = setInterval(() => {{
        if (splat.ready) {{ clearInterval(iv); resolve(); }}
      }}, 500);
      setTimeout(() => {{ clearInterval(iv); reject(new Error('splat timeout 90s')); }}, 90000);
    }});
    scene.add(splat); roomGLB = true;
    msg('step 4/5: splat room live…');
  }} catch (e) {{ msg('splat skipped (' + e.message + '), trying mesh…'); }}
}}
if (!roomGLB && v.glb && v.glb.local && wantMesh) {{
  try {{
    msg('step 3/5: downloading venue mesh (watch the counter)…');
    const venueLoader = new GLTFLoader();
    venueLoader.setMeshoptDecoder(MeshoptDecoder);
    const meshPromise = venueLoader.loadAsync(v.glb.local,
      (xhr) => {{ if (xhr.total) msg('step 3/5: mesh ' + Math.round(xhr.loaded/1048576) + 'MB / ' + Math.round(xhr.total/1048576) + 'MB'); }});
    const timeout = new Promise((_, rej) => setTimeout(() => rej(new Error('mesh timeout 25s — view-box it is')), 25000));
    const g = await Promise.race([meshPromise, timeout]);
    msg('step 4/5: mesh in, placing room…');
    const obj = g.scene;
    const box = new THREE.Box3().setFromObject(obj);
    const size = box.getSize(new THREE.Vector3());
    // fit by HEIGHT (floor stays floor, heads stay heads) — footprint
    // fit made rooms cavernous and performers lost. Feet land on y=0.
    const s = R.h / (size.y || 1);
    obj.scale.setScalar(s);
    const ctr = box.getCenter(new THREE.Vector3());
    obj.position.x -= ctr.x * s; obj.position.z -= ctr.z * s;
    obj.position.y -= box.min.y * s;
    window.__roomS = s;
    scene.add(obj); roomGLB = true;
    // frame box AFTER scale+placement (pre-scale bounds misframe the camera)
    obj.updateMatrixWorld(true);
    window.__roomBox = new THREE.Box3().setFromObject(obj);
  }} catch (e) {{ msg('mesh skipped (' + e.message + '), view-box fallback'); }}
}}
if (!roomGLB && !NOBG) {{
msg('step 4/5: view-box room…');
const roomMats = [dark, dark, dark, dark, wallMat('/static/concepts/mbl-wide.jpg'), dark];
roomMats.forEach(m => {{ m.side = THREE.BackSide; }});
const room = new THREE.Mesh(new THREE.BoxGeometry(R.w, R.h, R.d), roomMats);
room.position.set(0, R.h/2, R.d/2 - 0);
scene.add(room);
}}
// stage deck
const deck = new THREE.Mesh(new THREE.BoxGeometry(S.w, S.top_y, S.d),
  new THREE.MeshStandardMaterial({{color: 0x2a1d12, roughness: 0.9}}));
deck.position.set(0, S.top_y/2, S.front_z - S.d/2); deck.receiveShadow = true;
scene.add(deck);
// live light rig from venue JSON (temp approx → color)
const k2c = (k) => new THREE.Color().setHSL(0.09, 0.5, Math.min(0.9, 0.25 + (8000-k)/8000*0.5));
scene.add(new THREE.AmbientLight(k2c(v.light_rig.house.temp_k), v.light_rig.house.level + 0.25));
const spot = new THREE.SpotLight(k2c(v.light_rig.spot.temp_k), 60, 30, 0.5, 0.5);
spot.position.set(...v.light_rig.spot.pos);
spot.target.position.set(...v.marks[0].pos);
scene.add(spot, spot.target);
// procedural mic stand (layer 1, first object — zero downloads)
const brass = new THREE.MeshStandardMaterial({{color: 0x8a6b32, metalness: 0.8, roughness: 0.35}});
const mic = new THREE.Group();
const base = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.04, 24), brass);
base.position.y = 0.02; mic.add(base);
const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 1.5, 12), brass);
pole.position.y = 0.79; pole.castShadow = true; mic.add(pole);
const ball = new THREE.Mesh(new THREE.SphereGeometry(0.05, 20, 16),
  new THREE.MeshStandardMaterial({{color: 0x222226, roughness: 0.6}}));
ball.position.y = 1.58; ball.castShadow = true; mic.add(ball);
const cable = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.012, 8, 24, Math.PI),
  new THREE.MeshStandardMaterial({{color: 0x111111}}));
cable.position.y = 0.1; mic.add(cable);
mic.position.set(...v.marks[0].pos); mic.position.y = S.top_y;
// offset stage-right of the body so it reads on camera (comic holds it aside)
mic.position.x += 0.35;
scene.add(mic);
// contact shadow: cheap grounding blob (Animal-Crossing rule — connects feet
// to floor without real shadow maps, which broke SwiftShader).
const blob = new THREE.Mesh(new THREE.CircleGeometry(0.45, 24),
  new THREE.MeshBasicMaterial({{color: 0x000000, transparent: true, opacity: 0.4}}));
blob.rotation.x = -Math.PI / 2;
blob.position.set(v.marks[0].pos[0], S.top_y + 0.01, v.marks[0].pos[2] + 0.25);
scene.add(blob);
// performer (VRM default; ?body= URL swaps any GLB — weird characters
// welcome. GLB bodies play embedded clips; VRM bodies get vrma + face.)
msg('step 5/5: loading performer…');
const loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p));
loader.register((p) => new VRMAnimationLoaderPlugin(p));
const BODY_URL = new URLSearchParams(location.search).get('body') || '';
const BODY_IS_GLB = BODY_URL.endsWith('.glb');
let vrm = null, mixer = null, idleAction = null;
async function loadClip(name) {{
  const g = await loader.loadAsync('/static/gestures/' + name + '.vrma');
  const data = g.userData.vrmAnimations && g.userData.vrmAnimations[0];
  if (!data) throw new Error('no vrma in ' + name);
  return createVRMAnimationClip(data, vrm);
}}
function playGesture(name, holdMs) {{
  if (!mixer) return;
  if (!vrm) {{
    // GLB lane: embedded clips by name (punchline → Gallop etc.)
    const want = {{cheer: 'Gallop', nod: 'Idle', surprise: 'Jump_ToIdle', wave: 'Walk'}}[name];
    if (window.__glbClips && window.__glbClips[want]) {{
      const act = mixer.clipAction(window.__glbClips[want]);
      act.reset().setLoop(THREE.LoopOnce, 1); act.clampWhenFinished = true;
      if (idleAction) act.crossFadeFrom(idleAction, 0.3, false);
      act.play();
      setTimeout(() => {{
        if (idleAction && mixer) {{
          idleAction.reset().setLoop(THREE.LoopRepeat);
          idleAction.crossFadeFrom(act, 0.4, false); idleAction.play();
        }}
      }}, 2500);
    }}
    return;
  }}
  loadClip(name).then((clip) => {{
    const act = mixer.clipAction(clip);
    act.setLoop(THREE.LoopOnce, 1); act.clampWhenFinished = true;
    if (idleAction) act.crossFadeFrom(idleAction, 0.4, false);
    act.play();
    setTimeout(() => {{
      if (idleAction && mixer) {{
        idleAction.reset().setLoop(THREE.LoopRepeat);
        idleAction.crossFadeFrom(act, 0.5, false);
        idleAction.play();
      }}
    }}, holdMs || (clip.duration * 1000 + 400));
  }}).catch((e) => {{ blog('gesture miss: ' + name); }});
}}
const GESTURE_FOR = {{setup: 'nod', punchline: 'cheer', tag: 'surprise', closer: 'cheer', callback: 'nod'}};
try {{
  let bodyObj = null;
  if (BODY_IS_GLB) {{
    // weird-character lane: plain GLB, embedded clips, no expressions.
    const g2 = await loader.loadAsync(BODY_URL);
    bodyObj = g2.scene;
    const bb = new THREE.Box3().setFromObject(bodyObj);
    const bs = bb.getSize(new THREE.Vector3());
    const bh = bs.y > 0 ? 1.1 / bs.y : 1;
    bodyObj.scale.setScalar(bh);
    bodyObj.position.set(v.marks[0].pos[0], S.top_y - bb.min.y * bh, v.marks[0].pos[2] + 0.25);
    scene.add(bodyObj);
    mixer = new THREE.AnimationMixer(bodyObj);
    window.__glbClips = {{}};
    g2.animations.forEach(a => {{ window.__glbClips[a.name] = a; }});
    const idle = g2.animations.find(a => /idle/i.test(a.name)) || g2.animations[0];
    if (idle) {{
      idleAction = mixer.clipAction(idle);
      idleAction.setLoop(THREE.LoopRepeat); idleAction.play();
      blog('body clip: ' + idle.name);
    }}
    // adjustable mic: ball tracks the body's head height, pole follows.
    const headY = (bb.max.y - bb.min.y) * bh * 0.92;
    ball.position.y = headY;
    pole.scale.y = headY / 1.5; pole.position.y = headY / 2;
  }} else {{
  const vrmUrl = (BODY_URL && BODY_URL.endsWith('.vrm')) ? BODY_URL : '/static/avatars/default-v1.vrm';
  const gltf = await loader.loadAsync(vrmUrl);
  vrm = gltf.userData.vrm;
  vrm.scene.rotation.y = Math.PI;
  vrm.scene.position.set(v.marks[0].pos[0], S.top_y, v.marks[0].pos[2] + 0.25);
  scene.add(vrm.scene);
  }} // end else (VRM path)
  if (!BODY_IS_GLB) {{
  mixer = new THREE.AnimationMixer(vrm.scene);
  try {{
    idleAction = mixer.clipAction(await loadClip('idle_breathing'));
    idleAction.setLoop(THREE.LoopRepeat); idleAction.play();
  }} catch (e) {{ blog('idle miss'); }}
  }} // end VRM-only setup
  msg('live — pick a camera');
}} catch (e) {{ msg('performer failed: ' + e.message); }}
// venue cameras as buttons
const bar = document.getElementById('cams');
v.cameras.forEach(c => {{
  const b = document.createElement('button'); b.textContent = c.id;
  b.onclick = () => {{ camera.position.set(...c.pos); camera.fov = c.fov;
    camera.updateProjectionMatrix(); camera.lookAt(0, 1.2, -1); }};
  bar.appendChild(b);
}});
camera.position.set(...v.cameras[0].pos); camera.lookAt(0, 1.2, -1);
// ?face=1: head close-up test rig — camera pinned to the face so lip and
// face action fill the frame while the set plays. For AB verification.
const FACEMODE = new URLSearchParams(location.search).get('face') === '1';
if (FACEMODE && vrm) {{
  const hb = new THREE.Box3().setFromObject(vrm.scene);
  const hc = hb.getCenter(new THREE.Vector3());
  const hs = hb.getSize(new THREE.Vector3());
  const hy = hb.min.y + hs.y * 0.88;
  camera.position.set(hc.x + 0.12, hy + 0.05, hc.z + hs.z * 0.9 + 0.55);
  camera.fov = 22; camera.updateProjectionMatrix();
  camera.lookAt(hc.x, hy, hc.z);
  blog('face rig: close-up locked');
}}
if (window.__roomBox) {{
  // stand inside the real room: near one end, eyes up, look down its length
  const rb = window.__roomBox, rc = rb.getCenter(new THREE.Vector3());
  const rsz = rb.getSize(new THREE.Vector3());
  camera.position.set(rc.x, rc.y + rsz.y * 0.25, rb.max.z - rsz.z * 0.12);
  camera.lookAt(rc.x, rc.y - rsz.y * 0.1, rb.min.z + rsz.z * 0.25);
}}
addEventListener('resize', () => {{ renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); }});
const clock = new THREE.Clock(); let t = 0;
// set driver v0: set.wav + beat-type expressions on even cadence
// (APPROXIMATE — no measured offsets in freaks packs; precise driver lands
// with Rhubarb/forced alignment). Punchline pops + spot push per beat.
const SET_SLUG = new URLSearchParams(location.search).get('set') || 'biscuit-4cb995';
document.getElementById('play').textContent = '▶ PLAY SET (' + SET_SLUG.split('-')[0] + ')';
let beats = [];
let beatTimes = null; // measured timings preferred over cadence
try {{ beats = await (await fetch('/freaks/' + SET_SLUG + '/delivery.json')).json().then(j => j.beats || []); }} catch (e) {{}}
try {{ beatTimes = await (await fetch('/freaks/' + SET_SLUG + '/timings.json')).json().then(j => j.segments || null); }} catch (e) {{}}
const audio = new Audio();
audio.preload = 'auto';
audio.src = '/freaks/' + SET_SLUG + '/set.wav';
// phones that refuse WAV (MEDIA_ERR_SRC_NOT_SUPPORTED) fall to MP3 at load,
// so PLAY never meets a sourceless element. MP3 is also 12x smaller.
audio.addEventListener('error', () => {{
  const src = audio.src.split('/').pop();
  if (!audio.src.endsWith('.mp3')) {{
    blog('audio: ' + src + ' refused, trying mp3…');
    audio.src = '/freaks/' + SET_SLUG + '/set.mp3';
    audio.load();
  }} else {{
    msg('AUDIO DEAD: both wav+mp3 refused (' + src + ') — reply with phone model + browser');
  }}
}});
audio.load();
// jaw flap: audio energy → jaw morph (v0 lipsync; phonemes land later).
let jawSlot = null, analyser = null, freqData = null;
function initJaw() {{
  // wawa challenger: direct element tap, no graph needed.
  try {{
    if (LIPENGINE === 'wawa' && !wawa && typeof WawaLipsync !== 'undefined') {{
      wawa = new WawaLipsync();
      wawa.connectAudio(audio);
      blog('lipsync: wawa live');
      return; // wawa owns the mouth; skip MFCC graph entirely
    }}
  }} catch (e) {{ blog('wawa miss: ' + e.message); }}
  // real lipsync first (MFCC vowels → visemes, in-browser, free), energy
  // flap as fallback. Created on tap (mobile autoplay policy).
  try {{
    if (!window.__lipSync && vrm && typeof VRMLipSync !== 'undefined') {{
      const opts = window.__roomCtx ? {{audioContext: window.__roomCtx}} : {{}};
      VRMLipSync.create(vrm, opts).then((ls) => {{
        window.__lipSync = ls;
        // route set audio into the analyzer: element -> MediaStreamDestination
        // -> useStream (documented path). Guessed element-tap APIs removed;
        // the stream carries the same audio the room hears.
        try {{
          const ctx = window.__roomCtx;
          const dest = ctx.createMediaStreamDestination();
          // reuse the single element source (one per element per context)
          window.__roomSrc.connect(dest);
          if (ls.useStream) ls.useStream(dest.stream);
          else if (ls.useElement) ls.useElement(audio);
          blog('lipsync: mfcc live (stream-tapped)');
        }} catch (e) {{ blog('lipsync tap miss: ' + e.message); }}
      }}).catch((e) => {{ blog('lipsync miss, flap fallback'); }});
    }}
  }} catch (e) {{}}
  try {{
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) {{ blog('no webaudio'); return; }}
    if (!window.__roomCtx) {{
      const ctx = new AC();
      const src = ctx.createMediaElementSource(audio);
      window.__roomCtx = ctx;
      window.__roomSrc = src;
      analyser = ctx.createAnalyser(); analyser.fftSize = 256;
      freqData = new Uint8Array(analyser.frequencyBinCount);
      src.connect(analyser);
    }} else if (window.__roomCtx.state === 'suspended') {{
      window.__roomCtx.resume();
    }}
    const ctx = window.__roomCtx;
    // ROOM: dry voice + venue reverb send. Impulse is synthesized at runtime
    // from the venue's own rt60 (Sabine/Eyring, acoustics in venue JSON) —
    // no IR files, and the tail matches the room's measured physics.
    const dry = ctx.createGain(); dry.gain.value = 0.85;
    analyser.connect(dry); dry.connect(ctx.destination);
    const rt = (v.acoustics && v.acoustics.rt60) || 0.9;
    const sr = ctx.sampleRate, len = Math.floor(sr * Math.min(4, rt * 1.5));
    const ir = ctx.createBuffer(2, len, sr);
    for (let ch = 0; ch < 2; ch++) {{
      const d = ir.getChannelData(ch);
      for (let i = 0; i < len; i++)
        d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.2);
    }}
    const verb = ctx.createConvolver(); verb.buffer = ir;
    const wet = ctx.createGain(); wet.gain.value = 0.35;
    analyser.connect(verb); verb.connect(wet); wet.connect(ctx.destination);
    window.__roomFx = {{ctx, dry, wet, rt60: rt,
      toggle(on) {{ wet.gain.value = on ? 0.35 : 0; dry.gain.value = on ? 0.85 : 1; }}}};
    if (vrm && vrm.expressionManager) {{
      const all = vrm.expressionManager.expressions.map(e => e.expressionName);
      jawSlot = all.find(n => /jaw|aa|mouthopen|oh/i.test(n)) || null;
    }}
  }} catch (e) {{}}
}}
function flapJaw() {{
  if (!analyser || !jawSlot || !vrm) return;
  analyser.getByteFrequencyData(freqData);
  let e = 0;
  for (let i = 1; i < 12 && i < freqData.length; i++) e += freqData[i];
  e = Math.min(1, e / (12 * 90));
  try {{ vrm.expressionManager.setValue(jawSlot, e); }} catch (err) {{}}
}}
window.__venueDbg = {{get audioT() {{ return audio.currentTime; }},
  get audioOn() {{ return !audio.paused; }},
  get jaw() {{ return jawSlot; }}}};
window.__mouthNow = function () {{
  try {{
    const m = vrm.expressionManager;
    return ['aa','ih','ou','ee','oh','happy'].map(n => Math.round(m.getValue(n) * 100) / 100).join(',');
  }} catch (e) {{ return 'err'; }}
}};
window.__setMouth = function (v) {{
  try {{ vrm.expressionManager.setValue('aa', v); return 'set'; }}
  catch (e) {{ return 'err:' + e.message; }}
}};
const EXPR = {{setup: 'neutral', punchline: 'happy', tag: 'happy', closer: 'happy', callback: 'happy'}};
// Emotion channel ONLY (happy/angry/sad/surprised/relaxed/neutral). Never
// touches mouth visemes (aa/ih/ou/ee/oh) or blink — those belong to the
// lipsync engine. Old code zeroed everything per beat and stomped the mouth.
const EMOTION_ONLY = ['happy', 'angry', 'sad', 'surprised', 'relaxed', 'neutral'];
function setFace(name, val) {{
  if (!vrm || !vrm.expressionManager) return;
  try {{
    const mgr = vrm.expressionManager;
    const all = mgr.expressions.map(e => e.expressionName);
    EMOTION_ONLY.forEach(n => {{ if (all.includes(n)) try {{ mgr.setValue(n, 0); }} catch (e) {{}} }});
    const slot = EMOTION_ONLY.includes(name) ? name : (all.includes(name) ? name : 'happy');
    try {{ mgr.setValue(slot, val); }} catch (e) {{}}
  }} catch (e) {{}}
}}
let beatTimer = null;
document.getElementById('play').onclick = () => {{
  initJaw();
  audio.play().catch((e) => {{ msg('PLAY BLOCKED: ' + e.name + ' — tap again, check silent switch'); }});
  clearInterval(beatTimer);
  beatTimer = null;
  if (beatTimes && beatTimes.length === beats.length) {{
    // MEASURED driver: fire each beat at its real start offset.
    msg('performing ' + beats.length + ' beats (measured timing)');
    beatTimes.forEach((seg, i) => {{
      setTimeout(() => {{
        if (audio.paused) return;
        const b = beats[i];
        setFace(EXPR[b.type] || 'neutral', 0.9);
        playGesture(GESTURE_FOR[b.type] || 'nod');
        cutCam();
        spot.intensity = 60 + (b.type === 'punchline' || b.type === 'closer' ? 25 : 0);
      }}, seg.start_ms);
    }});
    return;
  }}
  msg('performing ' + beats.length + ' beats (approx timing)');
  if (!beats.length || !isFinite(audio.duration)) return;
  const per = (audio.duration || beats.length * 3) / beats.length;
  let i = 0;
  clearInterval(beatTimer);
  beatTimer = setInterval(() => {{
    if (i >= beats.length || audio.paused) {{ clearInterval(beatTimer); setFace('neutral', 1); return; }}
    const b = beats[i++];
    setFace(EXPR[b.type] || 'neutral', 0.9);
    playGesture(GESTURE_FOR[b.type] || 'nod');
    cutCam();
    spot.intensity = 60 + (b.type === 'punchline' || b.type === 'closer' ? 25 : 0);
  }}, per * 1000);
}};
// cinematography: REC captures the canvas; while recording, each beat cuts
// the camera (wide → medium → close rotation), then offers the webm.
let recorder = null, recChunks = [], recCam = 0;
document.getElementById('rec').onclick = () => {{
  if (recorder && recorder.state !== 'inactive') {{ recorder.stop(); return; }}
  try {{
    const stream = canvas.captureStream(30);
    recChunks = [];
    recorder = new MediaRecorder(stream, {{mimeType: 'video/webm'}});
    recorder.ondataavailable = (e) => {{ if (e.data.size) recChunks.push(e.data); }};
    recorder.onstop = () => {{
      const url = URL.createObjectURL(new Blob(recChunks, {{type: 'video/webm'}}));
      msg('take ready — tap to download');
      const a = document.createElement('a'); a.href = url;
      a.download = 'cauldron-take.webm'; a.textContent = '⬇ DOWNLOAD TAKE';
      a.style.cssText = 'color:#ff2fa8;font-size:14px';
      document.getElementById('ui').appendChild(a);
      document.getElementById('rec').textContent = '● REC';
    }};
    recorder.start(1000);
    document.getElementById('rec').textContent = '■ STOP';
    msg('recording — cameras cut per beat');
  }} catch (e) {{ msg('rec failed: ' + e.message); }}
}};
document.getElementById('room').onclick = (e) => {{
  const on = e.target.textContent.includes('ON');
  if (window.__roomFx) window.__roomFx.toggle(!on);
  e.target.textContent = on ? 'ROOM: OFF' : 'ROOM: ON';
}};
document.getElementById('tvbtn').onclick = () => {{
  location.href = location.pathname + '?tv=1';
}};
// TV MODE (?tv=1): hide the desk UI, flash a 4-letter pair code, poll the
// shared feed — controller taps land in THIS room's energy.
const TVMODE = new URLSearchParams(location.search).get('tv') === '1';
let pairCode = null, pairSeq = 0;
async function tvInit() {{
  document.getElementById('ui').style.display = 'none';
  const ov = document.createElement('div');
  ov.id = 'tvcode';
  ov.style.cssText = 'position:fixed;top:12px;right:12px;z-index:6;text-align:center;background:rgba(10,10,15,.8);padding:12px 18px;border-radius:14px;border:1px solid #ff2fa8';
  document.body.appendChild(ov);
  try {{
    const j = await (await fetch('/api/venue/' + VID + '/pair', {{method: 'POST'}})).json();
    pairCode = j.code;
  }} catch (e) {{ pairCode = '????'; }}
  const showTv = (members) => {{
    const n = Math.round(heat * 10);
    const bar = '█'.repeat(n) + '░'.repeat(10 - n);
    const verdict = heat >= 0.85 ? '🔥 KILLED' : heat >= 0.6 ? '🔥 HOT' : heat >= 0.3 ? '🙂 WARM' : '🍅 COLD';
    ov.innerHTML = '<div style="font-size:11px;color:#888">PAIR PHONE @ funnier.si/code</div>' +
      '<div style="font-size:44px;letter-spacing:8px;color:#ff2fa8">' + pairCode + '</div>' +
      '<div style="font-size:11px;color:#888">' + members + ' connected</div>' +
      '<div style="font-size:15px;color:#ff2fa8;margin-top:4px">' + bar + ' ' + verdict + '</div>';
  }};
  showTv(0);
  setInterval(async () => {{
    if (!pairCode || pairCode === '????') return;
    try {{
      const f = await (await fetch('/api/pair/' + pairCode + '/feed?since=' + pairSeq)).json();
      if (!f.ok) return;
      pairSeq = f.seq; showTv(f.members);
      f.events.forEach(ev => {{
        if (ev.kind === 'kill') {{
          document.body.innerHTML = '<div style="background:#000;color:#ff2fa8;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;font-size:24px;letter-spacing:4px">🕯️ INTERMISSION</div>';
        }} else if (ev.kind === 'laugh' || ev.kind === 'haha' || ev.kind === 'clap' || ev.kind === 'cheer') {{
          heat = Math.min(1, heat + GAIN / (1 + resist));
          resist = Math.max(0, resist - 0.06);
        }} else if (ev.kind === 'boo') {{
          resist = Math.min(1, resist + 0.10); heat = Math.max(0, heat - 0.05);
        }}
      }});
      paintEnergy();
    }} catch (e) {{}}
  }}, 2000);
}}
if (TVMODE) tvInit();
// ROOM ENERGY: the venue's own crowd physics (decay/laugh_gain/resist from
// venue JSON) running live. Laughs melt resistance; silence stiffens it.
// P0 local sim (one room, one viewer) — shared multi-viewer sum lands later.
let heat = 0.3, resist = (v.physics && v.physics.resist_start) || 0.35;
const DECAY = (v.physics && v.physics.decay) || 0.85;
const GAIN = (v.physics && v.physics.laugh_gain) || 0.18;
function paintEnergy() {{
  const n = Math.round(heat * 10);
  document.getElementById('emeter').textContent = '█'.repeat(n) + '░'.repeat(10 - n);
  const verdict = heat >= 0.85 ? '🔥 KILLED' : heat >= 0.6 ? '🔥 HOT' : heat >= 0.3 ? '🙂 WARM' : '🍅 COLD';
  document.getElementById('emeter').title = verdict + ' · resist ' + resist.toFixed(2);
}}
document.getElementById('laugh').onclick = () => {{
  heat = Math.min(1, heat + GAIN / (1 + resist));
  resist = Math.max(0, resist - 0.06); paintEnergy();
}};
document.getElementById('boo').onclick = () => {{
  resist = Math.min(1, resist + 0.10); heat = Math.max(0, heat - 0.05); paintEnergy();
}};
setInterval(() => {{ heat *= DECAY; resist = Math.min(1, resist + 0.005); paintEnergy(); }}, 4000);
paintEnergy();
function cutCam() {{
  if (!recorder || recorder.state === 'inactive') return;
  recCam = (recCam + 1) % v.cameras.length;
  const c = v.cameras[recCam];
  camera.position.set(...c.pos); camera.fov = c.fov;
  camera.updateProjectionMatrix(); camera.lookAt(0, 1.2, -1);
}}
audio.onended = () => {{ clearInterval(beatTimer); setFace('neutral', 1); spot.intensity = 60; if (recorder && recorder.state !== 'inactive') recorder.stop(); }};
renderer.setAnimationLoop(() => {{
  const dt = Math.min(0.05, clock.getDelta());
  t += dt;
  if (vrm) {{ vrm.scene.position.y = S.top_y + Math.sin(t*1.4)*0.008;
    vrm.scene.rotation.y = Math.sin(t*0.4)*0.06;
    if (mixer) mixer.update(dt);
    if (LIPENGINE === 'wawa' && wawa) {{ const vk = driveWawa(); if (vk) {{ window.__wawaV = vk; }} }}
    else if (window.__lipSync) {{ try {{ window.__lipSync.update(); }} catch (e) {{ flapJaw(); }} }}
    else flapJaw();
    vrm.update(t); }}
  renderer.render(scene, camera);
}});
</script></body></html>""", 200, {"Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store"}


@app.route("/code")
def pair_controller():
    """Phone controller: enter the 4-letter TV code, tap reactions, toggle
    face/mic presence. Plain string (no f-string) — brace-heavy JS inside."""
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>CONTROLLER — pair phone</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:24px 12px;margin:0}
button{font-size:20px;padding:14px 16px;margin:6px;border-radius:16px;background:#1a1a2e;color:#eee;border:1px solid #333}
button:active{background:#ff2fa8}
input{font-size:28px;letter-spacing:8px;text-align:center;width:180px;padding:10px;border-radius:12px;border:1px solid #333;background:#111119;color:#ff2fa8;text-transform:uppercase}
.big{font-size:26px;padding:18px 22px}
.on{border-color:#7fdb7f;color:#7fdb7f}
#status{color:#888;font-size:12px;margin-top:10px;min-height:18px}</style></head><body>
<h2>📱 CONTROLLER</h2>
<div id="join"><input id="code" maxlength="4" placeholder="CODE" autocomplete="off"><br>
<button id="go" class="big">JOIN TV</button></div>
<div id="pad" style="display:none">
<div id="room" style="color:#ff2fa8;font-size:13px"></div>
<button data-k="haha">😄</button><button data-k="haha">🤣</button><button data-k="clap">👏</button><button data-k="cheer">🎉</button><button data-k="boo">👎</button><br>
<button id="face">📷 FACE: OFF</button><button id="mic">🎙 MIC: OFF</button>
<div id="status"></div></div>
<script>
let CODE = null;
const say = (t) => { document.getElementById('status').textContent = t; };
document.getElementById('go').onclick = async () => {
  CODE = document.getElementById('code').value.toUpperCase().trim();
  const j = await (await fetch('/api/pair/' + CODE)).json().catch(() => ({}));
  if (!j.ok) return say('no such code — check the TV');
  document.getElementById('join').style.display = 'none';
  document.getElementById('pad').style.display = '';
  document.getElementById('room').textContent = 'paired → ' + j.venue + ' · ' + j.members + ' here';
  say('tap away — the room feels it');
};
async function tap(kind) {
  if (!CODE) return;
  const j = await (await fetch('/api/pair/' + CODE + '/react', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind})})).json().catch(() => ({}));
  if (!j.ok) say('lost the TV — rejoin');
}
document.querySelectorAll('[data-k]').forEach(b => { b.onclick = () => tap(b.dataset.k); });
document.getElementById('face').onclick = (e) => {
  const on = e.target.textContent.includes('OFF');
  e.target.textContent = on ? '📷 FACE: ON' : '📷 FACE: OFF';
  e.target.className = on ? 'on' : '';
  tap('smile'); say(on ? 'face shared (boolean smiles only)' : 'face off');
};
document.getElementById('mic').onclick = (e) => {
  const on = e.target.textContent.includes('OFF');
  e.target.textContent = on ? '🎙 MIC: ON' : '🎙 MIC: OFF';
  e.target.className = on ? 'on' : '';
  tap('mic'); say(on ? 'mic laughs on (booleans only)' : 'mic off');
};
</script></body></html>""", 200, {"Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store"}


@app.route("/sets")
def takes_gallery():
    """Recorded venue sets (/sets — /takes belongs to the legacy pog-take
    browser registered earlier in this file; first route wins in Flask).
    Server-side takes, watchable on any phone with zero GPU."""
    import html as _html
    tdir = Path(__file__).parent / "static" / "takes"
    cards = []
    for jf in sorted(tdir.glob("*.json"), reverse=True):
        try:
            m = json.loads(jf.read_text())
        except Exception:
            continue
        v = m.get("take", "")
        cards.append(
            "<div style='margin:0 auto 20px;max-width:720px;text-align:left;"
            "border:1px solid #282833;border-radius:12px;padding:12px'>"
            "<video src='/static/takes/" + v + "' controls preload='metadata' "
            "playsinline style='width:100%;border-radius:8px'></video>"
            "<div style='font-size:12px;margin-top:6px'>🎬 " + _html.escape(v) +
            " <span style='color:#555'>" + _html.escape(str(m.get("venue", ""))) +
            " · " + _html.escape(str(m.get("set", ""))) + "</span> " +
            "<button onclick=\"navigator.clipboard.writeText('https://funnier.si/static/takes/" + v + "');this.textContent='✓ link copied'\" " +
            "style='font-size:11px;padding:4px 10px;border-radius:8px;background:#1a1a2e;color:#eee;border:1px solid #333'>⧉ share</button></div></div>")
    body = "".join(cards) if cards else "<p>No takes yet.</p>"
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TAKES — recorded sets</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:24px 12px}
a{color:#ff2fa8}</style></head><body>
<div style="font-size:12px;letter-spacing:2px;color:#ff2fa8;">🎬 TAKES</div>
<h1>Recorded sets</h1>
<p style="color:#888;font-size:12px;">server-recorded · plays anywhere ·
<a href="/cauldron">concepts</a> · <a href="/perform">stage</a></p>
<div>""" + body + """</div></body></html>""", 200, {
        "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


@app.route("/perform/<slug>")
def perform_room(slug):
    """Live room for one act: the canonical watch player + live frame
    (LIVE banner, predicted-heat strip, finale verdict, next act)."""
    import html as _html
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    rendered = _render_watch(slug)
    if isinstance(rendered, tuple):
        page, code, headers = rendered[0], rendered[1], rendered[2] if len(rendered) > 2 else {}
    else:
        page, code, headers = rendered, 200, {}
    if code != 200:
        return rendered
    beats = _perform_beats(slug)
    meta = _bundle_meta(slug) or {}
    char = meta.get("character", {}) or {}
    import html as _html2
    pname = _html2.escape(char.get("name", slug))
    ppremise = _html2.escape(char.get("premise", ""))
    pimg = (f"/freaks/{slug}/portrait.png"
            if (FREAK_DIR / slug / "portrait.png").exists() else "/icon-512.png")
    walkout_url = ""
    for _w in ("walkout.mp3", "walkout.wav"):
        if (FREAK_DIR / slug / _w).exists():
            walkout_url = f"/freaks/{slug}/{_w}"
            break
    entrance = (
        "<div id='entrance' style='position:fixed;inset:0;background:#0a0a0f;z-index:50;"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px'>"
        "<div style='color:#ff2fa8;font-size:12px;letter-spacing:3px'>● LIVE</div>"
        f"<img src='{pimg}' style='width:180px;border-radius:16px;margin:14px 0'>"
        f"<h2 style='margin:0'>{pname}</h2>"
        f"<p style='color:#888;font-size:13px;max-width:340px'>{ppremise}</p>"
        "<p style='color:#555;font-size:12px'>is coming out…</p>"
        "<button id='showtimeBtn' style='font-size:18px;padding:14px 34px;margin-top:10px;"
        "background:#ff2fa8;border:none;border-radius:28px;color:#fff'>"
        "TAP FOR SHOWTIME</button>"
        "<p style='color:#555;font-size:11px;margin-top:10px'>cheer while you wait — "
        "buttons below work any time</p></div>"
        f"<audio id='walkout' src='{walkout_url}' preload='auto'></audio>" if walkout_url else
        "<div id='entrance' style='position:fixed;inset:0;background:#0a0a0f;z-index:50;"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px'>"
        "<div style='color:#ff2fa8;font-size:12px;letter-spacing:3px'>● LIVE</div>"
        f"<img src='{pimg}' style='width:180px;border-radius:16px;margin:14px 0'>"
        f"<h2 style='margin:0'>{pname}</h2>"
        f"<p style='color:#888;font-size:13px;max-width:340px'>{ppremise}</p>"
        "<p style='color:#555;font-size:12px'>is coming out…</p>"
        "<button id='showtimeBtn' style='font-size:18px;padding:14px 34px;margin-top:10px;"
        "background:#ff2fa8;border:none;border-radius:28px;color:#fff'>"
        "TAP FOR SHOWTIME</button>"
        "<p style='color:#555;font-size:11px;margin-top:10px'>cheer while you wait — "
        "buttons below work any time</p></div>")
    crowdbar = (
        "<div id='crowdbar' style='position:fixed;left:0;right:0;bottom:0;z-index:40;"
        "display:flex;justify-content:center;gap:8px;padding:10px 8px 14px;"
        "background:rgba(10,10,15,.92);border-top:1px solid #282833'>"
        + "".join(
            f"<button data-r='{t}' style='font-size:15px;padding:10px 12px;border-radius:20px;"
            f"background:#1a1a2e;border:1px solid #333;color:#eee'>{e} <span id='cnt-{t}'>0</span></button>"
            for e, t in (("😄", "haha"), ("🤣", "hahaha"), ("👏", "clap"),
                         ("🎉", "cheer"), ("👎", "boo")))
        + "</div>"
        "<script>(function(){var counts={};"
        "function setTime(){var a=document.getElementById('a');"
        "return (a&&!a.paused&&isFinite(a.currentTime))?Math.round(a.currentTime*1000):0}"
        "document.querySelectorAll('#crowdbar button').forEach(function(b){"
        "b.addEventListener('click',function(){var t=b.getAttribute('data-r');"
        "counts[t]=(counts[t]||0)+1;"
        "document.getElementById('cnt-'+t).textContent=counts[t];"
        "b.style.transform='scale(1.25)';setTimeout(function(){b.style.transform=''},150);"
        "fetch('/api/react',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({slug:'" + slug + "',type:t,set_time_ms:setTime(),"
        "laugh_id:(window.__laughId||''),"
        "cond:(typeof CROWD_COND!=='undefined'?CROWD_COND:'live')})}).catch(function(){});"
        "if((t==='haha'||t==='hahaha'||t==='laugh')&&window.__laughUrl){"
        "try{new Audio(window.__laughUrl).play().catch(function(){});}catch(e){}}"
        "if(t==='cheer'){var s=document.getElementById('stageImg');"
        "if(s){s.classList.add('pf-pop');setTimeout(function(){s.classList.remove('pf-pop')},400)}}"
        "});});"
        "var st=document.getElementById('showtimeBtn');"
        "if(st)st.addEventListener('click',function(){"
        "var w=document.getElementById('walkout');"
        "var go=function(){document.getElementById('entrance').style.display='none';"
        "var b=document.getElementById('bed');"
        "if(b){b.volume=0.25;b.play().catch(function(){});}"
        "var p=document.getElementById('playBtn');if(p)p.click();};"
        "if(w&&w.src){w.play().catch(function(){});"
        "w.onended=go;setTimeout(go,9000);}else{go();}});"
        "})();</script>")
    n_crowd = sum(1 for b in beats if b["crowd"])
    banner = (
        "<div id='livebanner' style='background:#ff2fa8;color:#fff;font-size:12px;"
        "letter-spacing:3px;padding:6px;text-align:center'>● LIVE — "
        f"{n_crowd} big moments predicted · you're the audience</div>")
    strip = (
        "<div id='heatstrip' style='display:flex;gap:2px;justify-content:center;"
        "max-width:560px;margin:6px auto;padding:0 16px' title='predicted laugh heat (heuristic v0)'>"
        + "".join(
            f"<div style='flex:1;height:6px;border-radius:3px;background:"
            f"{'#ff2fa8' if b['crowd'] else ('#7a2f5c' if b['chuckle'] else '#282833')}'"
            f" title='{round(b['p_laugh'] * 100)}%'></div>" for b in beats)
        + "</div>"
        + "<div style='font-size:10px;color:#555;text-align:center'>predicted heat · "
        "heuristic v0 (real laugh model hooks in at /api/perform/heat)</div>")
    bill = [s for s, _ in _perform_bundles()]
    try:
        nxt = bill[(bill.index(slug) + 1) % len(bill)] if bill else ""
    except ValueError:
        nxt = ""
    acting_js = (
        "<script>(function(){var acts=[],fired={},holdUntil=0;"
        "fetch('/api/perform/" + slug + "/acting').then(function(r){return r.json()})"
        ".then(function(j){if(j.ok)acts=j.events||[]}).catch(function(){});"
        "function img(){return document.getElementById('stageImg')}"
        "function vrm(){return document.getElementById('vrmStage')}"
        "function stages(){var o=[],m=img(),v=vrm();if(m)o.push(m);if(v)o.push(v);return o}"
        "function clearMove(){stages().forEach(function(m){"
        "m.classList.remove('pf-lean','pf-pop','pf-shake','pf-look-l','pf-look-r')})}"
        "function eachStage(fn){stages().forEach(fn)}"
        "window.__vrmFace=function(face){"
        "if(!stages().length)return;clearMove();"
        "if(face==='deadpan'||face==='neutral'){return}"
        "if(face==='happy'||face==='excited'||face==='delighted'){eachStage(function(m){m.classList.add('pf-pop')})}"
        "else if(face==='angry'||face==='indignant'){eachStage(function(m){m.classList.add('pf-shake')})}"
        "else{eachStage(function(m){m.classList.add('pf-lean')})}};"
        "setInterval(function(){var a=document.getElementById('a');"
        "if(!a||a.paused)return;var t=a.currentTime*1000;"
        "acts.forEach(function(e,i){"
        "if(fired[i]||t<e.t)return;fired[i]=1;"
        "if(e.kind==='gesture'){clearMove();"
        "eachStage(function(m){m.classList.add('pf-shake')});setTimeout(clearMove,450)}"
        "else if(e.kind==='look'){clearMove();"
        "if(e.value==='left')eachStage(function(m){m.classList.add('pf-look-l')});"
        "else if(e.value==='right')eachStage(function(m){m.classList.add('pf-look-r')})}"
        "else if(e.kind==='hold'){holdUntil=t+e.ms;eachStage(function(m){m.classList.add('pf-hold')});"
        "var c=document.getElementById('caption');if(c)c.style.opacity='1'}"
        "else if(e.kind==='camera'){eachStage(function(m){m.classList.add('pf-lean')});"
        "setTimeout(function(){eachStage(function(m){m.classList.remove('pf-lean')})},900)}"
        "});"
        "if(holdUntil&&t>holdUntil){holdUntil=0;"
        "eachStage(function(m){m.classList.remove('pf-hold')})}"
        "},200);})();</script>")
    finale_js = (
        "<div id='finale' style='display:none;max-width:560px;margin:12px auto;padding:14px;"
        "border:1px solid #ff2fa8;border-radius:12px;text-align:center'>"
        "<div style='color:#ff2fa8;letter-spacing:2px;font-size:12px'>SET OVER</div>"
        f"<div id='verdict' style='margin:8px 0'></div>"
        f"{f'<p><a href=/perform/{nxt} style=color:#00d4ff>next act →</a></p>' if nxt and nxt != slug else ''}"
        "<p><a href='/perform' style='color:#888;font-size:12px'>back to the bill</a></p></div>"
        "<script>(function(){var a=document.getElementById('a');if(!a)return;"
        "a.addEventListener('ended',function(){"
        "var f=document.getElementById('finale');if(!f)return;f.style.display='block';"
        "var n=(typeof myLaughs!=='undefined')?myLaughs:0;"
        "try{n+=parseInt((document.getElementById('cnt-haha')||{textContent:0}).textContent)||0;"
        "n+=3*(parseInt((document.getElementById('cnt-hahaha')||{textContent:0}).textContent)||0);}catch(e){}"
        "document.getElementById('verdict').textContent="
        "n>0?('You laughed '+n+'× — they earned another night.'):"
        "('Stone face. The room decides.');"
        "f.scrollIntoView();"
        "fetch('/api/perform/" + slug + "/verdict').then(function(r){return r.json()})"
        ".then(function(v){if(!v.ok)return;var d=document.createElement('div');"
        "d.style.cssText='margin:10px 0;font-size:12px;color:#888';"
        "if(v.killed){d.innerHTML='<div style=font-size:28px>💀 KILLED</div>'"
        "+'<div>energy '+v.energy+' · '+Math.round(v.coverage*100)+'% of beats laughed · '+v.creators+' in the crowd</div>'"
        "+'<div style=color:#ff2fa8>Ella: bury them. Encore.</div>';}"
        "else{d.textContent='room verdict: energy '+v.energy+'/'+v.bars.energy"
        "+' · coverage '+Math.round(v.coverage*100)+'%/'+Math.round(v.bars.coverage*100)+'%'"
        "+' · crowd '+v.creators+'/'+v.bars.creators+' · boos '+v.boos+' (max '+v.bars.boos+')';}"
        "f.appendChild(d);}).catch(function(){});"
        "var mine=(window.__mySmiles||[]);"
        "if(mine.length){fetch('/api/perform/" + slug + "/heat').then(function(r){return r.json()})"
        ".then(function(j){if(!j.ok||!j.beats)return;var g=document.createElement('div');"
        "g.style.cssText='margin:10px 0;font-size:11px;color:#888';"
        "g.innerHTML='<div style=color:#ff2fa8;letter-spacing:2px>YOUR FACE vs PREDICTED HEAT</div>';"
        "j.beats.forEach(function(b,i){var hit=mine.some(function(t){return t>=b.start-500&&t<b.end+2500});"
        "var row=document.createElement('div');row.style.cssText='display:flex;gap:4px;align-items:center;margin:2px 0';"
        "var bar=document.createElement('div');"
        "bar.style.cssText='width:'+Math.round(b.p_laugh*100)+'%;height:8px;border-radius:4px;background:#7a2f5c';"
        "var dot=document.createElement('span');dot.textContent=hit?'😄':'·';"
        "dot.style.color=hit?'#ff2fa8':'#333';"
        "row.appendChild(dot);row.appendChild(bar);g.appendChild(row);});"
        "f.appendChild(g);}).catch(function(){});}"
        "});})();</script>")
    act_css = (
        "<style>body{padding-bottom:92px}"
        "#vrmStage{transition:transform .18s ease,filter .18s ease}"
        "#stageImg{transition:transform .18s ease,filter .18s ease}"
        ".pf-lean{transform:scale(1.12)}.pf-pop{transform:scale(1.06) rotate(-1.5deg)}"
        ".pf-shake{animation:pfshake .3s ease}.pf-look-l{transform:translateX(-14px)}"
        ".pf-look-r{transform:translateX(14px)}.pf-hold{filter:brightness(1.35) saturate(1.2);"
        "outline:2px solid #ff2fa8;outline-offset:4px}"
        "@keyframes pfshake{25%{transform:translateX(-6px) rotate(-2deg)}"
        "75%{transform:translateX(6px) rotate(2deg)}}</style>")
    from flask import request as _req
    crowd_on = _req.args.get("crowd", "1") != "0"
    mouth = _req.args.get("mouth", "v1")
    if mouth not in ("v0", "v1"):
        mouth = "v1"
    bed_el = ("<audio id='bed' src='/api/perform/" + slug + "/crowd.wav' preload='auto'></audio>"
              if crowd_on else "")
    # Personal laugh: record once (local), hear it on every tap, share it
    # with the room only if asked. Upload = room-audible (monitor mix).
    laughblock = (
        "<div style='margin:6px auto;max-width:520px;text-align:center'>"
        "<button id='laughCalBtn' style='font-size:13px;padding:8px 16px;border-radius:18px;"
        "background:#1a1a2e;border:1px solid #333;color:#eee'>😂 RECORD MY LAUGH (3s)</button> "
        "<button id='laughPlayBtn' style='font-size:13px;padding:8px 16px;border-radius:18px;"
        "background:#1a1a2e;border:1px solid #333;color:#555' disabled>▶</button>"
        "<label style='font-size:11px;color:#888'><input type='checkbox' id='laughShare'> "
        "share with room</label>"
        "<div id='laughCalMsg' style='font-size:11px;color:#888;margin-top:4px'>"
        "Your laugh, on your taps, amidst the crowd. Stored on this device unless shared.</div></div>"
        "<script>(function(){"
        "try{var s=localStorage.getItem('ft_laugh');"
        "if(s){window.__laughUrl=s;document.getElementById('laughPlayBtn').disabled=false;}"
        "var sid=localStorage.getItem('ft_laugh_id');"
        "if(sid){window.__laughId=sid;document.getElementById('laughShare').checked=true;}}catch(e){}"
        "document.getElementById('laughPlayBtn').addEventListener('click',function(){"
        "if(window.__laughUrl)new Audio(window.__laughUrl).play().catch(function(){});});"
        "document.getElementById('laughCalBtn').addEventListener('click',async function(){"
        "var msg=document.getElementById('laughCalMsg'),btn=this;"
        "try{btn.disabled=true;btn.textContent='LAUGH NOW…';"
        "var st=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true}});"
        "var rec=new MediaRecorder(st);var ch=[];"
        "rec.ondataavailable=function(e){if(e.data.size)ch.push(e.data)};"
        "rec.start();await new Promise(function(r){setTimeout(r,3000)});"
        "rec.stop();await new Promise(function(r){rec.onstop=r});"
        "st.getTracks().forEach(function(t){t.stop()});"
        "var blob=new Blob(ch,{type:rec.mimeType||'audio/webm'});"
        "if(blob.size<1024){msg.textContent='Too quiet — try again, closer.';return;}"
        "var rd=new FileReader();"
        "rd.onload=function(){var url=rd.result;"
        "try{if(url.length<400000)localStorage.setItem('ft_laugh',url);}catch(e){}"
        "window.__laughUrl=url;"
        "document.getElementById('laughPlayBtn').disabled=false;"
        "msg.textContent='Got it ('+Math.round(blob.size/1024)+'KB). Tap ▶ to hear you.';};"
        "rd.readAsDataURL(blob);"
        "}catch(e){msg.textContent='Mic unavailable or declined: '+String(e);}"
        "finally{btn.disabled=false;btn.textContent='😂 RECORD MY LAUGH (3s)';}});"
        "document.getElementById('laughShare').addEventListener('change',async function(){"
        "var msg=document.getElementById('laughCalMsg');"
        "if(!this.checked){window.__laughId='';"
        "try{localStorage.removeItem('ft_laugh_id');}catch(e){}"
        "msg.textContent='Unshared. The room hears the generic crowd.';return;}"
        "if(!window.__laughUrl){msg.textContent='Record your laugh first.';this.checked=false;return;}"
        "msg.textContent='Sharing with the room…';"
        "try{var r=await fetch('/api/laughs',{method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({b64:window.__laughUrl})});var j=await r.json();"
        "if(j.ok){window.__laughId=j.laugh_id;"
        "try{localStorage.setItem('ft_laugh_id',j.laugh_id);}catch(e){}"
        "msg.textContent='Shared — the standup hears YOU in the mix.';}"
        "else{msg.textContent='Share failed: '+(j.error||r.status);this.checked=false;}}"
        "catch(e){msg.textContent='Share failed.';this.checked=false;}});"
        "})();</script>")
    # Mic laugh detector: HEURISTIC (energy bursts, not a laugh model).
    # Opt-in, booleans only — no audio ever leaves the device. Posts
    # {type:'laugh', src:'mic'} so the room can tell mic laughs apart.
    micblock = (
        "<div style='margin:6px auto;max-width:520px;text-align:center'>"
        "<button id='micBtn' style='font-size:13px;padding:8px 16px;border-radius:18px;"
        "background:#1a1a2e;border:1px solid #333;color:#eee'>🎙 MIC LAUGHS (OPTIONAL)</button>"
        "<div id='micMsg' style='font-size:11px;color:#888;margin-top:4px'>"
        "Local laugh detection (approximate): only laugh moments leave this device.</div></div>"
        "<script>(function(){var ctx=null,stream=null,an=null,timer=null,base=0.02,cool=0;"
        "function setTime(){var a=document.getElementById('a');"
        "return (a&&!a.paused&&isFinite(a.currentTime))?Math.round(a.currentTime*1000):0}"
        "document.getElementById('micBtn').addEventListener('click',async function(){"
        "var msg=document.getElementById('micMsg'),btn=this;"
        "if(stream){clearInterval(timer);timer=null;"
        "stream.getTracks().forEach(function(t){t.stop()});stream=null;"
        "if(ctx){ctx.close();ctx=null;}"
        "btn.textContent='🎙 MIC LAUGHS (OPTIONAL)';"
        "msg.textContent='Mic off. Nothing was ever uploaded.';return;}"
        "try{btn.disabled=true;"
        "stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true}});"
        "ctx=new (window.AudioContext||window.webkitAudioContext)();"
        "var src=ctx.createMediaStreamSource(stream);an=ctx.createAnalyser();an.fftSize=1024;"
        "src.connect(an);var buf=new Float32Array(an.fftSize),ring=[];"
        "msg.textContent='Listening locally — laugh out loud.';"
        "btn.textContent='MIC ON — TAP TO STOP';"
        "timer=setInterval(function(){an.getFloatTimeDomainData(buf);"
        "var s=0;for(var i=0;i<buf.length;i++)s+=buf[i]*buf[i];"
        "var rms=Math.sqrt(s/buf.length);"
        "base=base*0.98+rms*0.02;"
        "ring.push(rms);if(ring.length>10)ring.shift();"
        "var hot=0;for(var j=0;j<ring.length;j++)if(ring[j]>2.5*Math.max(base,0.008))hot++;"
        "var now=Date.now();"
        "if(hot>=4&&now>cool){cool=now+4000;"
        "fetch('/api/react',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({slug:'" + slug + "',type:'laugh',set_time_ms:setTime(),"
        "src:'mic',cond:(typeof CROWD_COND!=='undefined'?CROWD_COND:'live')})}).catch(function(){});"
        "msg.textContent='😄 heard that ('+new Date().toLocaleTimeString()+')';}"
        "},100);"
        "}catch(e){if(stream){stream.getTracks().forEach(function(t){t.stop()});stream=null;}"
        "msg.textContent='Mic unavailable or declined: '+String(e);}"
        "finally{btn.disabled=false;}});})();</script>")
    smileblock = (
        "<div style='margin:10px auto;max-width:520px;text-align:center'>"
        "<button id='smileToggle' style='font-size:13px;padding:8px 16px;border-radius:18px;"
        "background:#1a1a2e;border:1px solid #333;color:#eee'>📷 TRACK MY FACE (OPTIONAL)</button>"
        "<div id='smileMsg' style='font-size:11px;color:#888;margin-top:4px'>"
        "Local only: calibrates in your browser, only yes/no smile moments leave this device.</div>"
        "<video id='smileVideo' muted autoplay playsinline "
        "style='display:none;width:120px;border-radius:8px'></video>"
        "<div style='margin-top:8px'><button id='appearBtn' style='font-size:13px;padding:8px 16px;"
        "border-radius:18px;background:#2a0a1e;border:1px solid #ff2fa8;color:#ffb7dc'>"
        "📡 APPEAR ON STAGE MONITOR</button>"
        "<div id='appearMsg' style='font-size:11px;color:#888;margin-top:4px'>"
        "Second opt-in: the comedian sees your live face. Stop anytime.</div></div></div>"
        "<script>(function(){var pc=null,stream=null,me='a_'+Math.random().toString(36).slice(2,10),seq=0;"
        "function sig(b){return fetch('/api/perform/" + slug + "/signal',{method:'POST',"
        "headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(function(r){return r.json()});}"
        "function beat(){return setInterval(function(){"
        "fetch('/api/perform/" + slug + "/presence',{method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({frm:me,mode:(pc?'face':'pip')})}).catch(function(){});},8000);}"
        "beat();"
        "document.getElementById('appearBtn').addEventListener('click',async function(){"
        "var msg=document.getElementById('appearMsg'),btn=this;"
        "if(pc){try{if(pc._iv)clearInterval(pc._iv);}catch(e0){}try{pc.close();}catch(e){}pc=null;"
        "if(stream){stream.getTracks().forEach(function(t){t.stop()});stream=null;}"
        "sig({frm:me,kind:'bye'}).catch(function(){});"
        "btn.textContent='📡 APPEAR ON STAGE MONITOR';"
        "msg.textContent='Off the monitor. The room still has your taps.';return;}"
        "try{btn.disabled=true;"
        "stream=await navigator.mediaDevices.getUserMedia({video:{width:320,facingMode:'user'},audio:false});"
        "pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});"
        "stream.getTracks().forEach(function(t){pc.addTrack(t,stream)});"
        "pc.onicecandidate=function(ev){if(ev.candidate)sig({frm:me,kind:'ice',payload:ev.candidate});};"
        "var off=await pc.createOffer();await pc.setLocalDescription(off);"
        "await sig({frm:me,kind:'offer',payload:pc.localDescription});"
        "var got=false;"
        "var iv=setInterval(async function(){"
        "var j=await (await fetch('/api/perform/" + slug + "/signal?since='+seq)).json();"
        "seq=j.seq||seq;"
        "(j.msgs||[]).forEach(function(m){if(m.frm!==me)return;"
        "if(m.kind==='answer'&&!got){got=true;pc.setRemoteDescription(m.payload).catch(function(){});}"
        "else if(m.kind==='ice'&&pc){pc.addIceCandidate(m.payload).catch(function(){});}});"
        "},1500);"
        "pc._iv=iv;"
        "btn.textContent='ON MONITOR — TAP TO HIDE';"
        "msg.textContent='The comedian can see you now. Nothing is recorded.';"
        "}catch(e){if(stream){stream.getTracks().forEach(function(t){t.stop()});stream=null;}"
        "if(pc){try{pc.close();}catch(e2){}pc=null;}"
        "msg.textContent='Camera unavailable or declined: '+String(e);}"
        "finally{btn.disabled=false;}});})();</script>"
        "<script src='/static/smile-referee.js'></script>"
        "<script>(function(){var stream=null,ref=null,poll=null,wasHigh=false,cooldown=0;"
        "window.__mySmiles=[];"
        "function setTime(){var a=document.getElementById('a');"
        "return (a&&!a.paused&&isFinite(a.currentTime))?Math.round(a.currentTime*1000):0}"
        "function loadScript(u){return new Promise(function(res,rej){var s=document.createElement('script');"
        "s.src=u;s.onload=res;s.onerror=rej;document.head.appendChild(s);});}"
        "document.getElementById('smileToggle').addEventListener('click',async function(){"
        "var msg=document.getElementById('smileMsg'),btn=this;"
        "if(stream){clearInterval(poll);poll=null;"
        "stream.getTracks().forEach(function(t){t.stop()});stream=null;"
        "if(ref){ref.dispose();ref=null;}"
        "document.getElementById('smileVideo').srcObject=null;wasHigh=false;"
        "btn.textContent='📷 TRACK MY FACE (OPTIONAL)';"
        "msg.textContent='Camera stopped. No frames were ever sent.';return;}"
        "try{btn.disabled=true;"
        "if(typeof tf==='undefined')await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest');"
        "var v=document.getElementById('smileVideo');"
        "stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});"
        "v.srcObject=stream;await v.play();v.style.display='inline-block';"
        "msg.textContent='Calibrating: hold neutral, then smile when asked.';"
        "ref=await SmileReferee.calibrate(v,{samples:30,ephemeral:true,"
        "onStep:function(s){msg.textContent=s.smiling?'Smile now':'Hold a neutral face';}});"
        "var cv=document.createElement('canvas'),ctx=cv.getContext('2d');"
        "poll=setInterval(function(){if(!ref||!v.videoWidth)return;"
        "cv.width=v.videoWidth;cv.height=v.videoHeight;ctx.drawImage(v,0,0);"
        "var p=ref.predict(cv),high=p>0.82,now=Date.now();"
        "if(high&&!wasHigh&&now>cooldown){cooldown=now+3000;"
        "var t=setTime();window.__mySmiles.push(t);"
        "fetch('/api/react',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({slug:'" + slug + "',type:'smile',set_time_ms:t,"
        "cond:(typeof CROWD_COND!=='undefined'?CROWD_COND:'live')})}).catch(function(){});}"
        "wasHigh=high;"
        "msg.textContent='Camera on · local only · '+(high?'smiling':'neutral');"
        "},350);"
        "btn.textContent='STOP TRACKING';"
        "}catch(e){if(stream){stream.getTracks().forEach(function(t){t.stop()});stream=null;}"
        "msg.textContent='Camera unavailable or declined: '+String(e);}"
        "finally{btn.disabled=false;}});})();</script>")
    if mouth == "v0":
        page = page.replace("const MOUTH = 'v1'", "const MOUTH = 'v0'")
    cond_js = ("var CROWD_COND='" + ("bed" if crowd_on else "nobed") + "+mouth" + mouth + "';")
    if "<body>" in page:
        page = page.replace("<body>", "<body>" + banner + strip + act_css + entrance + crowdbar + bed_el
                            + smileblock + micblock + "<script>" + cond_js + "</script>", 1)
    head, sep, tail = page.rpartition("</body>")
    if sep:
        page = head + acting_js + finale_js + sep + tail
    else:
        page = page + acting_js + finale_js
    return page, 200, headers


@app.route("/api/card/<slug>.png")
def og_card(slug):
    """Purpose-built 1200x630 share card: portrait/name/premise/duration."""
    from PIL import Image, ImageDraw
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    meta = _bundle_meta(slug)
    if not meta:
        return jsonify({"ok": False, "error": "unknown set"}), 404
    out = AUDIO_DIR / "cards"
    out.mkdir(exist_ok=True)
    path = out / f"{slug}.png"
    char = meta.get("character", {})
    if not path.exists():
        img = Image.new("RGB", (1200, 630), (10, 10, 15))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1200, 630], outline=(255, 47, 168), width=6)
        d.text((60, 40), "FREAK TOWN", fill=(255, 47, 168))
        d.text((60, 120), (char.get("name") or slug)[:28].upper(), fill=(255, 255, 255))
        d.text((60, 220), (char.get("premise") or "")[:90], fill=(150, 150, 160))
        d.text((60, 340), f"{meta.get('duration_s', 0)} seconds · watch it, then answer back",
               fill=(0, 217, 255))
        portrait = FREAK_DIR / slug / "portrait.png"
        if portrait.exists():
            try:
                p = Image.open(portrait).convert("RGB").resize((380, 380))
                img.paste(p, (770, 125))
            except Exception:
                pass
        img.save(path)
    return send_from_directory(str(out), f"{slug}.png")


@app.route("/api/funnel", methods=["POST"])
def funnel():
    """Share->watch->respond funnel events. Body: {event, slug, ...}.
    Events: opened, play, p25, p50, p75, complete, tray_seen, seed_changed,
    edited, respond_started, generated, reply_watched, shared. Drives the K
    (responses per performance) metric: complete -> respond -> generated -> share."""
    import time as _time
    data = request.json or {}
    event = re.sub(r"[^a-z0-9_]", "", str(data.get("event", "")))[:32]
    if not event:
        return jsonify({"ok": False, "error": "event required"}), 400
    row = {"t": _time.time(), "event": event,
           "slug": re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45],
           "creator": str(data.get("creator", ""))[:64]}
    for k in ("mode", "depth", "value"):
        if data.get(k) is not None:
            row[k] = data[k]
    try:
        with open(Path(__file__).parent / "funnel.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/respond_idea", methods=["POST"])
def respond_idea():
    """Preloaded funny response angle for a set. Body: {"slug": "..."}.
    Returns {"idea": "..."} — a one-line premise to answer back with."""
    import httpx
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45]
    meta = _bundle_meta(slug)
    if not meta:
        return jsonify({"ok": False, "error": "unknown set"}), 404
    char = meta.get("character", {})
    context = f"{char.get('name', 'A comedian')} ({char.get('premise', '')})"
    # stored seeds first (generated at publish; zero spinner). Optional ?mode=.
    mode = str((request.json or {}).get("mode", "")).lower()
    for _s in meta.get("response_seeds", []) or []:
        if not mode or _s.get("type") == mode:
            return jsonify({"ok": True, "idea": _s.get("text", ""),
                            "engine": "stored", "mode": _s.get("type", "")})
    try:
        delivery = json.loads((FREAK_DIR / slug / "delivery.json").read_text())
        beats = delivery.get("beats", [])
        closer = next((b.get("text", "") for b in reversed(beats)
                       if b.get("type") in ("punchline", "closer")), "")
    except Exception:
        closer = ""
    idea, engine = None, None
    tok, acct = _cf_creds()
    if tok and acct:
        for model in CF_MODELS:
            try:
                r = httpx.post(
                    f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                    headers={"Authorization": f"Bearer {tok}",
                             "Content-Type": "application/json"},
                    json={"messages": [
                        {"role": "system", "content": (
                            "You write one-line comedy premises for response sets. "
                            "One sentence, under 20 words, specific and roasty but "
                            "playful. No quotes, no explanation, just the premise.")},
                        {"role": "user", "content": (
                            f"Write a response-set premise answering this act: {context}. "
                            f"Their closer was: {closer}")}],
                        "max_tokens": 60, "temperature": 1.0},
                    timeout=60)
                if r.status_code != 200:
                    continue
                idea = _ai_text(r.json()).strip().strip('"')
                engine = model.split("/")[-1]
                break
            except Exception:
                continue
    if not idea:
        import random as _r
        idea = _r.choice([
            f"Answer {char.get('name', 'them')} back, but meaner",
            f"Steal {char.get('name', 'their')} premise and do it better",
            f"Play the character {char.get('name', 'they')} were roasting",
            "Defend the indefensible part of that set",
            f"Tell the same story from the other person's perspective",
        ])
    return jsonify({"ok": True, "idea": idea, "engine": engine or "fallback"})


def _render_watch(slug):
    """Shared watch page renderer for /f/<slug> and /@<character>/<set>.
    The shared freak is a 60s challenge: TAP TO WATCH → YOUR TURN → RESPOND."""
    import html as _html
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if not meta or not (bdir / "set.wav").exists():
        return "No such set (yet). Make one in the Black Room.", 404
    char = meta.get("character", {})
    name = _html.escape(char.get("name", slug))
    premise = _html.escape(char.get("premise", ""))
    char_slug = _char_slug(char.get("name", ""))
    set_name = meta.get("set_name") or ""
    set_label = _html.escape(set_name.replace("-", " ").upper() or "UNTITLED SET")
    nreplies = sum(
        1 for d in FREAK_DIR.iterdir() if d.is_dir() and
        ((_bundle_meta(d.name) or {}).get("lineage") or {}).get("parent") == slug)
    has_portrait = (bdir / "portrait.png").exists()
    img = f"/freaks/{slug}/portrait.png" if has_portrait else "/icon-512.png"
    dur = meta.get("duration_s", 0)
    # Beat timeline for sync highlight — SAME clock as /api/preload:
    # measured offsets when present, else the shared estimator.
    # (The old inline 2.82-wps estimator is gone; viewer and StageRuntime
    # must never disagree about when a line lands.)
    beats = []
    try:
        from backend.services.freaktown.bundle import (
            estimate_spans, spans_from_offsets,
        )
        delivery = json.loads((bdir / "delivery.json").read_text())
        try:
            offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
        except Exception:
            offsets = []
        duration_ms = int(float(meta.get("duration_s", 0)) * 1000) or None
        spans = spans_from_offsets(offsets) if offsets else estimate_spans(
            delivery.get("beats", []), duration_ms)
        by_id = {s.beat_id: s for s in spans}
        for b in delivery.get("beats", []):
            s = by_id.get(b.get("id"))
            if s is None:
                continue
            beats.append({"text": b.get("text", ""), "start": s.start_ms,
                          "end": s.start_ms + s.speech_ms,
                          "face": (b.get("performance") or {}).get("expression", "neutral")})
    except Exception:
        pass
    lin = meta.get("lineage") or {}
    parent = lin.get("parent")
    # Bundle body for the stage: manifest truth, glb or vrm. Empty when
    # the freak is portrait-only (fallback chain handles it).
    rt = _avatar_runtime(slug)
    body_url = rt["uri"] if rt else ""
    body_fmt = rt["format"] if rt else ""
    arbtn = (f"<a href='/ar/{slug}' style='display:block;margin:8px auto;max-width:340px,"
             "text-align:center;text-decoration:none' class='cta ghost'>"
             "<button style='width:100%'>📍 place in your room</button></a>"
             f"<a href='/record/{slug}' style='display:block;margin:8px auto;max-width:340px,"
             "text-align:center;text-decoration:none' class='cta ghost'>"
              "<button style='width:100%'>🎭 become them — record</button></a>"
              if rt else "")
    takes = _list_takes(slug)[:3]
    takes_html = ""
    if takes:
        cards = "".join(
            f"<video src='{t['url']}' controls playsinline preload='none' "
            f"style='width:100%;max-width:340px;border-radius:8px;background:#000;"
            f"margin:6px auto;display:block'></video>" for t in takes)
        takes_html = (
            f"<div style='margin:10px auto;max-width:360px;text-align:center'>"
            f"<div style='font-size:12px;color:#ff2fa8'>🎭 REAL TAKES — people as {name}</div>"
            f"{cards}"
            f"<a href='/takes' style='font-size:12px;color:#00d4ff'>all pogs' takes →</a></div>")
    else:
        takes_html = (
            f"<div style='margin:10px auto;max-width:360px;text-align:center;"
            f"font-size:12px;color:#666'>No human takes yet — "
            f"<a href='/r/{slug}' style='color:#00d4ff'>record the first</a> · "
            f"<a href='/takes' style='color:#00d4ff'>all takes</a></div>")
    page = WATCH_TEMPLATE
    for key, val in {
        "__SLUG__": slug, "__NAME__": name, "__PREMISE__": premise,
        "__CHAR_SLUG__": char_slug, "__SET_LABEL__": set_label,
        "__NREPLIES__": str(nreplies),
        "__IMG__": img, "__DUR__": str(dur),
        "__MOUTH__": "v1",
        "__BEATS__": json.dumps(beats),
        "__BODY__": body_url, "__BODY_FORMAT__": body_fmt,
        "__ARBTN__": arbtn,
        "__TAKES__": takes_html,
        "__VOICE__": (
            "<details style='margin:10px auto;max-width:360px;text-align:center'>"
            "<summary style='font-size:12px;color:#888;cursor:pointer'>"
            "🎙 re-voice the set</summary>"
            "<div style='font-size:12px;margin-top:6px'>"
            "<select id='vVoice'>"
            "<option value='en-US-AriaNeural'>Ella (Aria)</option>"
            "<option value='en-US-GuyNeural'>Guy</option>"
            "<option value='en-US-ChristopherNeural'>Christopher</option>"
            "<option value='en-US-SamanthaNeural'>Samantha</option>"
            "<option value='en-US-JoannaNeural'>Joanna</option>"
            "<option value='en-US-TonyNeural'>Tony</option>"
            "</select> <select id='vPace'>"
            "<option value='normal'>normal</option>"
            "<option value='slow'>slow</option>"
            "<option value='fast'>fast</option>"
            "</select> "
            "<button onclick='previewVoice()'>▶ preview line 1</button>"
            "<div id='vMsg' style='color:#666;margin-top:4px'></div></div></details>"
            "<script>async function previewVoice(){"
            "var m=document.getElementById('vMsg');m.textContent='rendering…';"
            "try{var line=(BEATS[0]&&BEATS[0].text)||'';if(!line){m.textContent='no lines';return;}"
            "var r=await fetch('/api/regen_beat',{method:'POST',"
            "headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({text:line,"
            "voice:document.getElementById('vVoice').value,"
            "pace:document.getElementById('vPace').value})});"
            "var j=await r.json();"
            "if(j.ok){m.textContent=j.cached?'(cached)':'(fresh)';"
            "new Audio('/api/beat_audio/'+j.key).play();}"
            "else m.textContent='failed: '+(j.error||r.status);}catch(e){m.textContent='error';}}"
            "</script>"),
        "__CARD__": f"https://freak.town/api/card/{slug}.png",
        "__CANON__": canonical_url(slug),
        "__REPLYBANNER__": (
            f"<div id='replybanner'>↩ replying to "
            f"<a href='/f/{parent}'>{_html.escape(parent)}</a></div>"
            if parent else ""),
    }.items():
        page = page.replace(key, val)
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


WATCH_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__NAME__ — Freak Town</title>
<link rel="canonical" href="__CANON__">
<meta property="og:title" content="__NAME__ — Freak Town">
<meta property="og:description" content="__PREMISE__ (__DUR__s set). Watch it, then answer back.">
<meta property="og:image" content="__CARD__">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="__NAME__ trading card">
<meta property="og:url" content="__CANON__">
<meta property="og:site_name" content="Freak Town">
<meta property="og:type" content="video.other">
<meta property="video:duration" content="__DUR__">
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
.top{display:flex;align-items:center;justify-content:space-between;padding:8px 14px;font-size:11px;letter-spacing:2px;color:#777}
.top .logo{color:#ff2fa8;font-weight:bold;font-size:11px;letter-spacing:2px}
.top .share{color:#777;background:none;border:1px solid #282833;padding:6px 12px;border-radius:16px;font-size:12px;min-height:0}
#stage{position:relative;flex-shrink:0}
#vrmStage{width:100%;height:300px;display:none}
#stageImg{max-width:240px;border-radius:12px;margin:0 auto;display:block}
#popcard{background:#111116;border:1px solid #282833;border-radius:14px;margin:8px auto;max-width:560px;padding:10px 14px;text-align:left}
#popcard h1{font-size:19px;margin:0}
#popcard .premise{color:#888;font-size:12px;margin-top:2px}
#popcard .setline{color:#555;font-size:11px;margin-top:4px;letter-spacing:1px}
#popcard .setline a{color:#555;text-decoration:none}
#popcard .replies{color:#00d4ff;font-size:11px;margin-top:4px}
#popcard.playing .setline a{pointer-events:none;color:#333}
#sendback{display:none;padding:16px;max-width:560px;margin:0 auto;width:100%}
#sendback.show{display:block;animation:trayup .3s ease-out}
#clock{font-size:13px;color:#555;font-variant-numeric:tabular-nums}
#seekrow{display:flex;align-items:center;gap:8px;max-width:560px;margin:4px auto 0;padding:0 16px;font-size:11px;color:#555}
#seek{flex:1;accent-color:#ff2fa8;cursor:pointer;height:3px}
#seek::-webkit-slider-thumb{width:14px;height:14px}
#caption{min-height:52px;max-width:560px;margin:6px auto 0;padding:0 16px;font-size:17px;line-height:1.5;color:#eee}
#caption:empty{display:none}
#txToggle{font-size:11px;color:#555;background:none;border:none;padding:4px;cursor:pointer}
#transcript{display:none;flex:none;overflow-y:auto;text-align:left;max-width:560px;margin:4px auto;max-height:30vh;padding:0 16px;font-size:14px;line-height:1.8;color:#555}
#transcript.open{display:block}
#replybox{display:none;padding:16px;max-width:560px;margin:0 auto;width:100%;border-top:1px solid #282833}
#replybox.show{display:block;animation:trayup .3s ease-out}
@keyframes trayup{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}
.modrow{display:flex;gap:8px;margin:8px 0}
.modrow .btn{flex:1;padding:8px 4px;font-size:12px}
.modrow .btn.on{border-color:#ff2fa8;color:#ff2fa8}
#respline{font-size:12px;color:#555;margin-top:6px}
#replybanner{font-size:12px;color:#00d4ff;margin-bottom:6px}
#replybanner a{color:#00d4ff}
#replybox{display:none;padding:16px;max-width:560px;margin:0 auto;width:100%}
#replybox.show{display:block}
#replybox textarea{width:100%;background:#111;border:1px solid #333;color:#eee;border-radius:10px;padding:10px;font-family:inherit;font-size:14px;min-height:64px;resize:vertical}
#replybox textarea:focus{outline:none;border-color:#ff2fa8}
#idea{font-size:13px;color:#00d4ff;margin:8px 0;min-height:20px}
.replyrow{display:flex;gap:8px;margin-top:8px}
.replyrow .btn{flex:1}
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
<div class="top"><span class="logo">FREAK TOWN</span><button class="share" onclick="passItOn()">↗ share</button></div>
__REPLYBANNER__
<div id="stage">
  <canvas id="vrmStage"></canvas>
  <img id="stageImg" src="__IMG__" alt="">
</div>
<div id="popcard">
  <h1>__NAME__</h1>
  <div class="premise">__PREMISE__</div>
  <div class="setline">SET: __SET_LABEL__ · <a href="/@__CHAR_SLUG__">@__CHAR_SLUG__</a> · __DUR__s</div>
  <div class="replies" id="replyCount"></div>
</div>
<div id="clock">00:00 / __DUR__s</div>
<div id="seekrow"><input type="range" id="seek" min="0" max="1000" value="0" aria-label="seek"><span id="left">__DUR__s</span></div>
<div id="caption"></div>
<div><button id="txToggle" onclick="document.getElementById('transcript').classList.toggle('open')">••• transcript</button></div>
<div id="transcript"></div>
<div class="controls" id="liveControls">
  <button class="big" id="playBtn">▶ TAP TO WATCH</button>
  <button id="laughBtn" disabled>😂 <span id="laughCount">0</span></button>
  __ARBTN__
</div>
__TAKES__
__VOICE__
<div id="endscreen">
  <div id="replybox">
    <div style="font-size:15px;font-weight:bold;margin-bottom:2px;">YOUR TURN</div>
    <div style="font-size:12px;color:#555;margin-bottom:6px;" id="wellLine">…well?</div>
    <div id="idea">thinking of an angle…</div>
    <textarea id="replyText" rows="3" enterkeyhint="done"></textarea>
    <div class="modrow" id="modeRow">
      <button class="btn on" data-mode="roast" onclick="setMode('roast')">🔥 ROAST</button>
      <button class="btn" data-mode="yes_and" onclick="setMode('yes_and')">➕ YES-AND</button>
      <button class="btn" data-mode="random" onclick="setMode('random')">🎲 RANDOM</button>
    </div>
    <div class="replyrow">
      <button class="btn btn-primary big" style="flex:2;" onclick="sendResponse()">RESPOND ▶</button>
    </div>
    <div id="respline"><a href="#" onclick="document.getElementById('replyText').focus();return false;" style="color:#888;">edit the idea</a> · <a href="/edit?reply=__SLUG__" style="color:#555;">full studio</a></div>
    <div id="genline" style="display:none;font-size:13px;color:#888;"></div>
  </div>
  <div id="sendback">
    <div style="font-size:15px;font-weight:bold;">YOUR FREAK PERFORMED</div>
    <div id="sendbackName" style="color:#888;font-size:13px;margin:4px 0 10px;"></div>
    <button class="big" style="width:100%;" onclick="passItOn()">📤 SEND BACK</button>
    <div style="display:flex;gap:8px;margin-top:8px;">
      <button class="ghost" style="flex:1;" onclick="replayReply()">↻ replay</button>
      <button class="ghost" style="flex:1;" id="fineTuneBtn">fine tune</button>
    </div>
  </div>
  <div id="stats"></div>
  <div style="font-size:11px;color:#444;margin-top:10px;">Did it cook?
    <button class="btn btn-small ghost" onclick="vote('keep')">KEEP</button>
    <button class="btn btn-small ghost" onclick="vote('cut')">CUT</button>
    <span id="voteMsg" style="color:#00d4ff;"></span>
  </div>
  <div style="margin-top:10px;"><a href="/" style="color:#444;font-size:12px;">＋ make your own freak</a></div>
</div>
<audio id="a" src="/freaks/__SLUG__/set.wav" preload="auto"></audio>
<script>
const BEATS = __BEATS__;
let SLUG = "__SLUG__";
const Aud = document.getElementById('a');
let timer = null, myLaughs = 0, voted = false;
let respMode = 'roast';
let NREPLIES = parseInt('__NREPLIES__' || '0', 10) || 0;

// anonymous creator identity: own your freaks later, no account now
function creatorId() {
  try {
    let id = localStorage.getItem('freaktown_id');
    if (!id) {
      id = 'anon_' + Math.random().toString(36).slice(2, 10);
      localStorage.setItem('freaktown_id', id);
    }
    return id;
  } catch (e) { return 'anon_unknown'; }
}

function funnel(event, extra) {
  try {
    fetch('/api/funnel', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(Object.assign({event, slug: SLUG, creator: creatorId()}, extra || {}))});
  } catch (e) {}
}
funnel('opened');

// reply count line under the trading card (lore without interrupting playback)
try {
  const rc = document.getElementById('replyCount');
  if (rc && NREPLIES > 0) {
    const a = document.createElement('a');
    a.href = '/api/replies/' + encodeURIComponent(SLUG);
    a.style.color = '#00d4ff'; a.style.textDecoration = 'none';
    a.textContent = '↩ ' + NREPLIES + (NREPLIES === 1 ? ' reply' : ' replies');
    rc.appendChild(a);
  }
} catch (e) {}

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
  document.getElementById('popcard').classList.add('playing');
  funnel('play');
  timer = setInterval(tick, 150);
}
document.getElementById('playBtn').onclick = play;

const seekEl = document.getElementById('seek');
function fmtLeft(t) {
  const left = Math.max(0, parseFloat('__DUR__') - t);
  return `${Math.round(left)}s left`;
}
seekEl.addEventListener('input', () => {
  if (!Aud.duration || !isFinite(Aud.duration)) return;
  Aud.currentTime = (parseFloat(seekEl.value) / 1000) * Aud.duration;
});
const marksFired = {};
function tick() {
  const t = Aud.currentTime * 1000;
  const dur = (Aud.duration && isFinite(Aud.duration)) ? Aud.duration : parseFloat('__DUR__');
  document.getElementById('clock').textContent = fmt(Aud.currentTime) + ' / __DUR__s';
  if (dur) {
    if (document.activeElement !== seekEl) {
      seekEl.value = Math.round((Aud.currentTime / dur) * 1000);
    }
    document.getElementById('left').textContent = fmtLeft(Aud.currentTime);
    [25, 50, 75].forEach(p => {
      if (!marksFired[p] && Aud.currentTime / dur >= p / 100) {
        marksFired[p] = true;
        funnel('p' + p);
      }
    });
  }
  let cur = -1, capText = '';
  BEATS.forEach((b, i) => {
    const el = document.getElementById('seg' + i);
    const on = t >= b.start && t < b.end + 1200;
    if (el) {
      el.classList.toggle('spoken', t >= b.start);
      el.classList.toggle('active', on);
    }
    if (on) { cur = i; capText = b.text; }
  });
  document.getElementById('caption').textContent = capText;
  if (window.__vrmFace && cur >= 0) window.__vrmFace(BEATS[cur].face || 'neutral');
  if (Aud.ended) endShow();
}

async function react(type) {
  if (Aud.paused || Aud.ended) return;
  if (type === 'laugh') { myLaughs++; document.getElementById('laughCount').textContent = myLaughs; }
  try {
    await fetch('/api/react', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug: SLUG, type, set_time_ms: Math.round(Aud.currentTime * 1000),
                            creator: creatorId()})});
  } catch (e) {}
}

document.getElementById('laughBtn').onclick = () => react('laugh');

async function vote(v) {
  if (voted) return;
  voted = true;
  try {
    await fetch('/api/vote', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug: SLUG, vote: v, creator: creatorId()})});
  } catch (e) {}
  document.getElementById('voteMsg').textContent =
    v === 'keep' ? 'Counted. They live to perform another night.' : 'Counted. Brutal. Ella approves.';
}

function endShow() {
  clearInterval(timer);
  funnel('complete');
  document.getElementById('liveControls').style.display = 'none';
  document.getElementById('popcard').classList.remove('playing');
  document.getElementById('endscreen').classList.add('show');
  document.getElementById('stats').textContent =
    myLaughs > 0 ? `You laughed ${myLaughs}× · did they earn another night?` : '';
  try {
    const nm = (document.querySelector('#popcard h1') || {}).textContent || '';
    document.getElementById('wellLine').textContent = nm ? `${nm} stares… …well?` : '…well?';
  } catch (e) {}
  if (window.__vrmIdle) window.__vrmIdle();
  // YOUR TURN tray rises immediately; idea prefills below (stored seeds = instant)
  document.getElementById('replybox').classList.add('show');
  document.getElementById('sendback').classList.remove('show');
  funnel('tray_seen');
  loadIdea();
}

let ideaMode = 'roast';
function setMode(m) {
  if (m === ideaMode) return;
  ideaMode = m;
  document.querySelectorAll('#modeRow .btn').forEach(b =>
    b.classList.toggle('on', b.dataset.mode === m));
  funnel('seed_changed', {mode: m});
  loadIdea();
}

async function loadIdea() {
  const el = document.getElementById('idea');
  const box = document.getElementById('replyText');
  el.textContent = 'thinking of an angle…';
  try {
    const res = await fetch('/api/respond_idea', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug: SLUG, mode: ideaMode})});
    const data = await res.json();
    if (data.ok && data.idea) {
      el.textContent = '💡 ' + data.idea;
      if (!box.dataset.edited) box.value = data.idea; // prefilled: tap RESPOND with zero writing
      window._idea = data.idea;
      return;
    }
  } catch (e) {}
  el.textContent = '';
}

// track human edits separately from seed prefills (no auto-focus: iOS
// keyboards require a direct user gesture, so the big RESPOND is the gesture)
try {
  document.getElementById('replyText').addEventListener('input', (e) => {
    e.target.dataset.edited = '1';
    funnel('edited', {mode: ideaMode});
  }, {once: true});
} catch (e) {}

function rerollIdea() {
  document.getElementById('replyText').value = '';
  loadIdea();
}

async function sendResponse() {
  // One tap: generate the counter-freak server-side, play it in THIS viewer.
  const custom = document.getElementById('replyText').value.trim();
  const line = document.getElementById('genline');
  line.style.display = 'block';
  line.textContent = 'Your response is entering Freak Town…';
  funnel('respond_started', {mode: ideaMode, edited: !!custom});
  try {
    const res = await fetch('/api/respond', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({parent_slug: SLUG, mode: ideaMode,
                            idea: custom || undefined, creator: creatorId()})});
    const data = await res.json();
    if (!data.ok) {
      line.textContent = 'Generation stumbled — ' + (data.error || 'retry') +
        ' · or open full studio';
      return;
    }
    funnel('generated', {child: data.slug});
    // stage resets, YOUR FREAK walks on: swap audio + beats, replay in place
    document.getElementById('replybox').classList.remove('show');
    line.style.display = 'none';
    await playReply(data);
  } catch (e) {
    line.textContent = 'Generation stumbled — check connection, retry';
  }
}

async function playReply(data) {
  // same viewer, new performer: swap source, rebuild beats, play
  const res = await fetch(`/api/sets/${data.slug}`);
  const full = await res.json();
  if (!full.ok) return;
  const c = full.character || {};
  const prevName = (document.querySelector('#popcard h1') || {}).textContent || '';
  document.querySelector('#popcard h1').textContent = c.name || 'Your Freak';
  document.querySelector('#popcard .premise').textContent =
    `answering ${prevName} · ${c.premise || ''}`;
  const setline = document.querySelector('#popcard .setline');
  if (setline) setline.style.display = 'none';
  Aud.src = data.audio;
  Aud.currentTime = 0;
  document.getElementById('endscreen').classList.remove('show');
  document.getElementById('liveControls').style.display = 'flex';
  document.getElementById('playBtn').style.display = '';
  // rebuild caption beats from the reply's own delivery
  const tb = document.getElementById('transcript');
  tb.innerHTML = '';
  (full.beats || []).forEach((b, i) => {
    const d = document.createElement('div');
    d.className = 'seg'; d.id = 'seg' + i;
    d.textContent = b.text || '';
    tb.appendChild(d);
  });
  BEATS.length = 0;
  (full.beats || []).forEach((b) => {
    const words = (b.text || '').split(/\s+/).filter(Boolean).length;
    const prev = BEATS.length ? BEATS[BEATS.length - 1] : null;
    const start = prev ? prev._end : 0;
    const speech = Math.round(words / 2.82 * 1000);
    BEATS.push({text: b.text, start, end: start + speech,
                face: ((b.performance || {}).expression || 'neutral'),
                _end: start + speech + (b.pause_after_ms || 300)});
  });
  // swap slug so reactions/votes/ideas/share now target the reply
  SLUG = data.slug;
  window.__replyUrl = data.url;
  try {
    const ft = document.getElementById('fineTuneBtn');
    if (ft) ft.onclick = () => { location.href = '/edit?reply=' + encodeURIComponent(data.slug); };
  } catch (e) {}
  const sbName = document.getElementById('sendbackName');
  if (sbName) sbName.textContent = (c.name ? c.name + ' · ' : '') + 'reply ready — send it back';
  myLaughs = 0; voted = false;
  document.getElementById('laughCount').textContent = '0';
  document.getElementById('voteMsg').textContent = '';
  // reply gets its own end-state: SEND BACK dominant (not another YOUR TURN loop)
  Aud.onended = endReply;
  try { await Aud.play(); } catch (e) { return; }
  document.getElementById('playBtn').style.display = 'none';
  document.getElementById('popcard').classList.add('playing');
  timer = setInterval(tick, 150);
  status('YOUR FREAK performs — SEND BACK when done');
}

function endReply() {
  clearInterval(timer);
  funnel('reply_watched', {slug: SLUG});
  document.getElementById('liveControls').style.display = 'none';
  document.getElementById('endscreen').classList.add('show');
  document.getElementById('replybox').classList.remove('show');
  document.getElementById('sendback').classList.add('show');
  if (window.__vrmIdle) window.__vrmIdle();
}

function replayReply() {
  document.getElementById('endscreen').classList.remove('show');
  document.getElementById('liveControls').style.display = 'flex';
  document.getElementById('playBtn').style.display = '';
  Aud.currentTime = 0;
  Aud.onended = endReply;
  Aud.play().catch(() => {});
  document.getElementById('playBtn').style.display = 'none';
  timer = setInterval(tick, 150);
}

function status(msg) {
  let el = document.getElementById('watchStatus');
  if (!el) {
    el = document.createElement('div');
    el.id = 'watchStatus';
    el.style.cssText = 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);background:#1a1a2e;border:1px solid #333;padding:8px 16px;border-radius:8px;font-size:12px;z-index:50;';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.style.display = 'none'; }, 3000);
}

async function passItOn() {
  const url = window.__replyUrl || location.href;
  funnel('shared');
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
let pAA = 0, pIH = 0, pOH = 0, pOU = 0, pEE = 0, nextBlink = 0;
const MOUTH = '__MOUTH__';  // v0: 3-shape envelope (legacy). v1: 5-shape + rounded/high vowels.
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
  // Bundle body first (glb mesh or vrm), default rig as fallback.
  // Mesh bodies get procedural sway + jaw-morph drive; VRM gets the
  // full expression path. Portrait shows only if all 3D fails.
  const BODY_URL = "__BODY__", BODY_FMT = "__BODY_FORMAT__";
  let meshBody = null, meshJaw = null, meshJawP = 0;
  let meshBaseY = 0, meshBaseRotY = 0;
  try {
    if (BODY_URL && BODY_FMT === 'glb') {
      const g2 = await new GLTFLoader().loadAsync(BODY_URL);
      const obj = g2.scene;
      const box = new THREE.Box3().setFromObject(obj);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const s = size.y > 0 ? 1.6 / size.y : 1;
      obj.scale.setScalar(s);
      obj.position.x -= center.x * s;
      obj.position.z -= center.z * s;
      obj.position.y -= box.min.y * s;
      scene.add(obj);
      meshBody = obj; meshBaseY = obj.position.y;
      obj.traverse(o => {
        if (o.isMesh && o.morphTargetDictionary && !meshJaw) {
          const names = Object.keys(o.morphTargetDictionary);
          const j = names.find(n => /^(jawOpen|jaw|mouthOpen)$/.test(n));
          if (j) meshJaw = {mesh: o, idx: o.morphTargetDictionary[j]};
        }
      });
    } else {
      const gltf = await loader.loadAsync(BODY_URL || '/static/avatars/default-v1.vrm');
      vrm = gltf.userData.vrm;
      scene.add(vrm.scene);
    }
  } catch (e) {
    console.error('bundle body failed, default rig', e);
    const gltf = await loader.loadAsync('/static/avatars/default-v1.vrm');
    vrm = gltf.userData.vrm;
    scene.add(vrm.scene);
  }
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
      if (MOUTH === 'v1') {
        pOU = sm(pOU, Math.min(1, band(5, 18) / 210) * 0.8, 0.5);
        pEE = sm(pEE, Math.min(1, band(55, 100) / 170) * 0.65, 0.5);
      }
      try {
        vrm.expressionManager.setValue('aa', pAA);
        vrm.expressionManager.setValue('ih', pIH);
        vrm.expressionManager.setValue('oh', pOH);
        if (MOUTH === 'v1') {
          vrm.expressionManager.setValue('ou', pOU);
          vrm.expressionManager.setValue('ee', pEE);
        }
      } catch (e) {}
    } else if (vrm?.expressionManager) {
      pAA = sm(pAA, 0, 0.3); pIH = sm(pIH, 0, 0.3); pOH = sm(pOH, 0, 0.3);
      try {
        vrm.expressionManager.setValue('aa', pAA);
        vrm.expressionManager.setValue('ih', pIH);
        vrm.expressionManager.setValue('oh', pOH);
        if (MOUTH === 'v1') {
          pOU = sm(pOU, 0, 0.3); pEE = sm(pEE, 0, 0.3);
          vrm.expressionManager.setValue('ou', pOU);
          vrm.expressionManager.setValue('ee', pEE);
        }
      } catch (e) {}
    }
    if (vrm?.humanoid) {
      const spine = vrm.humanoid.getNormalizedBoneNode('spine');
      if (spine) spine.rotation.y = Math.sin(t * 0.6) * 0.04;
    }
    if (meshBody) {
      meshBody.rotation.y = meshBaseRotY + Math.sin(t * 0.5) * 0.12;
      meshBody.position.y = meshBaseY + Math.sin(t * 1.1) * 0.03;
      if (meshJaw && analyser && !A.paused) {
        analyser.getByteFrequencyData(freqData);
        let s = 0;
        for (let i = 0; i < Math.min(10, freqData.length); i++) s += freqData[i];
        meshJawP = sm(meshJawP, Math.min(1, (s / 10) / 200), 0.5);
        try { meshJaw.mesh.morphTargetInfluences[meshJaw.idx] = meshJawP; } catch (e) {}
      } else if (meshJaw) {
        meshJawP = sm(meshJawP, 0, 0.3);
        try { meshJaw.mesh.morphTargetInfluences[meshJaw.idx] = meshJawP; } catch (e) {}
      }
    }
    if (t > nextBlink) {
      nextBlink = t + 2.5 + Math.random() * 2.5;
      try {
        vrm.expressionManager.setValue('blink', 1);
        setTimeout(() => { try { vrm.expressionManager.setValue('blink', 0); } catch (e) {} }, 140);
      } catch (e) {}
    }
    if (vrm) vrm.update(dt);
    renderer.render(scene, camera);
  })();
} catch (e) {
  console.error('vrm stage failed, portrait fallback showing', e);
}
</script>
</body></html>"""


AR_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__NAME__ in your room — Freak Town</title>
<meta name="theme-color" content="#ff2fa8">
<script src="https://cdn.jsdelivr.net/npm/@8thwall/engine-binary@1/dist/xr.js" async crossorigin="anonymous" data-preload-chunks="slam"></script>
<script src="https://cdn.jsdelivr.net/npm/@8thwall/xrextras@1/dist/xrextras.js" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/@8thwall/landing-page@1/dist/landing-page.js" crossorigin="anonymous"></script>
<script type="importmap">
{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/",
  "@pixiv/three-vrm": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.0/lib/three-vrm.module.js"
}}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#000;font-family:monospace}
#camerafeed{position:fixed;inset:0;width:100%;height:100%}
#ui{position:fixed;left:0;right:0;bottom:0;padding:14px;text-align:center;z-index:5;
background:linear-gradient(transparent,rgba(0,0,0,.72));padding-bottom:calc(14px + env(safe-area-inset-bottom))}
#ui h1{color:#fff;font-size:16px}
#ui p{color:#aaa;font-size:12px;margin:4px 0 10px}
button{background:#ff2fa8;border:1px solid #ff2fa8;color:#fff;padding:14px 26px;border-radius:26px;font-size:16px;cursor:pointer;font-family:inherit}
button.ghost{background:rgba(20,20,30,.8);border-color:#555}
#back{position:fixed;top:10px;left:10px;z-index:5;color:#fff;background:rgba(20,20,30,.7);
border:1px solid #444;border-radius:18px;padding:8px 14px;font-size:13px;text-decoration:none}
#status{color:#8f8;font-size:12px;margin-top:8px;min-height:16px}
</style>
</head><body>
<canvas id="camerafeed"></canvas>
<a id="back" href="/f/__SLUG__">← __NAME__</a>
<div id="ui">
  <h1>__NAME__ in your room</h1>
  <p id="hint">Open in <b>Chrome / Safari</b> (not inside WhatsApp or X) — AR needs your camera.</p>
  <button id="placeBtn">📍 PLACE</button>
  <button id="playBtn" style="display:none">▶ PLAY MINUTE</button>
  <div id="status">starting…</div>
</div>
<audio id="a" src="__AUDIO__" preload="auto" crossorigin="anonymous"></audio>
<audio id="w" src="__WALKOUT__" preload="auto" crossorigin="anonymous"></audio>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
window.THREE = THREE;
const BODY_URL = "__BODY__", BODY_FMT = "__BODY_FORMAT__", SLUG = "__SLUG__";
const status = (t) => { document.getElementById('status').textContent = t; };
let avatar = null, jawTargets = [], vrm = null, audioCtx = null, analyser = null, audioEl = null;
let placed = false, playing = false, energy = 0, nextBlink = 3;
let freqData = null, baseY = 0, entranceT = 1, walkoutEl = null, mixerAR = null;

function collectJaw(root) {
  const out = [];
  root.traverse((o) => {
    if (o.morphTargetDictionary && o.morphTargetInfluences) {
      for (const n of ["jawOpen", "mouthOpen", "aa", "oh"]) {
        if (n in o.morphTargetDictionary) out.push({ mesh: o, idx: o.morphTargetDictionary[n] });
      }
    }
  });
  return out;
}

const freakModule = () => ({
  name: 'freak-ar',
  onStart: async ({ canvas }) => {
    const { scene, camera, renderer } = XR8.Threejs.xrScene();
    try {
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
    } catch (err) {}
    scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 0.9));
    const sun = new THREE.DirectionalLight(0xfff2dd, 1.2);
    sun.position.set(3, 6, 4); sun.castShadow = true;
    scene.add(sun);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(30, 30),
      new THREE.ShadowMaterial({ opacity: 0.35 }));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true;
    scene.add(ground);
    camera.position.set(0, 1.6, 0.1);
    XR8.XrController.updateCameraProjectionMatrix({ origin: camera.position, facing: camera.quaternion });
    canvas.addEventListener('touchstart', (e) => {
      if (e.target.closest('#ui') || e.target.closest('#back')) return;
      if (e.touches.length === 1 && placed) XR8.XrController.recenter();
    }, true);
    try {
      const loader = new GLTFLoader();
      if (BODY_FMT === 'vrm') loader.register((p) => new VRMLoaderPlugin(p, { autoUpdateHumanBones: true }));
      const gltf = await loader.loadAsync(BODY_URL);
      avatar = gltf.scene;
      if (BODY_FMT === 'vrm') {
        vrm = gltf.userData.vrm;
        VRMUtils.removeUnnecessaryVertices(avatar);
        VRMUtils.removeUnnecessaryJoints(avatar);
      }
      const box = new THREE.Box3().setFromObject(avatar);
      const h = Math.max(0.5, box.max.y - box.min.y);
      const s = 1.6 / h;
      avatar.scale.setScalar(s);
      avatar.userData.baseScale = s;
      avatar.position.set(0, -box.min.y * s, -1.4);
      avatar.traverse((o) => { if (o.isMesh) o.castShadow = true; });
      avatar.visible = false;
      scene.add(avatar);
      jawTargets = vrm ? [] : collectJaw(avatar);
      try {
        const clips = gltf.animations || [];
        if (clips.length && !vrm) {
          let ci = 0;
          try {
            ci = Math.max(0, parseInt(
              new URLSearchParams(location.search).get('clip') || '0', 10) || 0) % clips.length;
          } catch (err) {}
          mixerAR = new THREE.AnimationMixer(avatar);
          mixerAR.clipAction(clips[ci]).play();
        }
      } catch (err) { mixerAR = null; }
      status('Avatar loaded. Point at the floor, tap PLACE.');
    } catch (e) {
      status('Could not load avatar body.');
    }
  },
});

const onxrloaded = () => {
  const ua = navigator.userAgent || "";
  if (/wv|WebView|FBAN|FBAV|Twitter|WhatsApp|Line\//i.test(ua)) {
    status('In-app browser detected: tap ⋯ and "Open in Chrome/Safari" or the camera stays black.');
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    status('This browser exposes no camera. Use Chrome/Safari with HTTPS.');
    return;
  }
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }).then((stream) => {
    stream.getTracks().forEach((t) => t.stop());
    status('Camera OK. Starting room tracking — move the phone slowly.');
    XR8.addCameraPipelineModules([
    XR8.GlTextureRenderer.pipelineModule(),
    XR8.Threejs.pipelineModule(),
    XR8.XrController.pipelineModule(),
    LandingPage.pipelineModule(),
    XRExtras.FullWindowCanvas.pipelineModule(),
    XRExtras.Loading.pipelineModule(),
    XRExtras.RuntimeError.pipelineModule(),
    freakModule(),
  ]);
  XR8.run({ canvas: document.getElementById('camerafeed') });
  }).catch(() => {
    status('Camera blocked: allow camera access in the browser, then reload. ' +
           'On iPhone use Safari; on Android use Chrome — not the chat-app viewer.');
  });
};
window.XR8 ? onxrloaded() : window.addEventListener('xrloaded', onxrloaded);

document.getElementById('placeBtn').onclick = () => {
  if (!avatar) { status('Still loading the body…'); return; }
  avatar.visible = true; placed = true;
  try { baseY = avatar.position.y; } catch (err) {}
  entranceT = 0;
  try {
    walkoutEl = document.getElementById('w');
    if (walkoutEl && walkoutEl.getAttribute('src')) {
      walkoutEl.play().catch(() => {});
      document.getElementById('hint').textContent = '🎺 __NAME__ takes the stage!';
    }
  } catch (err) {}
  document.getElementById('placeBtn').style.display = 'none';
  document.getElementById('playBtn').style.display = 'inline-block';
  document.getElementById('hint').textContent = 'There they are. Tap PLAY.';
  status('');
};
document.getElementById('playBtn').onclick = async () => {
  if (playing || !placed) return;
  playing = true;
  try {
    audioEl = document.getElementById('a');
    audioEl.onerror = () => { status('Audio file failed to load.'); };
    const clock = new THREE.Clock();
    const alive = () => {
      requestAnimationFrame(alive);
      const dt = Math.min(0.05, clock.getDelta());
      const t = clock.elapsedTime;
      if (!placed || !avatar) return;
      // idle life, always on: entrance rise, sway + bob + blink
      if (entranceT < 1) entranceT = Math.min(1, entranceT + dt / 1.4);
      const e = 1 - entranceT;
      const back = 1 + 2.0 * e * e * e - 1.2 * e * e;
      const bs = avatar.userData.baseScale || 1;
      avatar.scale.setScalar(Math.max(0.01, bs * (entranceT < 1 ? back : 1)));
      avatar.rotation.z = Math.sin(t * 0.9) * 0.03;
      avatar.position.y = baseY + Math.abs(Math.sin(t * 2.2)) * 0.02;
      if (vrm) {
        try {
          if (t > nextBlink) {
            nextBlink = t + 2.5 + Math.random() * 2.5;
            vrm.expressionManager.setValue('blink', 1);
            setTimeout(() => { try { vrm.expressionManager.setValue('blink', 0); } catch (err) {} }, 140);
          }
          vrm.update(dt);
        } catch (err) {}
      }
      try { mixerAR && mixerAR.update(dt); } catch (err) {}
      // speaking: analyser energy -> jaw + bop
      let w = 0;
      if (playing && analyser) {
        analyser.getByteFrequencyData(freqData);
        let e = 0;
        for (let i = 1; i < 12; i++) e += freqData[i];
        w = Math.min(1, e / (12 * 160));
      }
      energy += (w - energy) * 0.4;
      for (const j of jawTargets) {
        try { j.mesh.morphTargetInfluences[j.idx] = energy; } catch (err) {}
      }
      try { vrm && vrm.expressionManager.setValue('aa', energy); } catch (err) {}
      if (avatar) {
        avatar.position.y = baseY + Math.abs(Math.sin(t * 2.2)) * 0.02 + energy * 0.03;
        avatar.rotation.y += energy * 0.01;
      }
    };
    alive();
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaElementSource(audioEl);
    analyser = audioCtx.createAnalyser(); analyser.fftSize = 256;
    src.connect(analyser); analyser.connect(audioCtx.destination);
    await audioCtx.resume();
    await audioEl.play();
    document.getElementById('playBtn').style.display = 'none';
    document.getElementById('hint').textContent = '🎤 live from your floor';
    freqData = new Uint8Array(analyser.frequencyBinCount);
    audioEl.onended = () => { playing = false; };
  } catch (e) { status('Audio blocked — tap again.'); playing = false; }
};
</script>
</body></html>"""


@app.route("/ar/<slug>", methods=["GET"])
@app.route("/a/<slug>", methods=["GET"])
def watch_ar(slug):
    """AR view: place the freak in your room (8th Wall WebAR) and play the set."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if not meta or not (bdir / "set.wav").exists():
        return "No such set (yet). Make one in the Black Room.", 404
    import html as _html
    char = meta.get("character", {})
    name = _html.escape(char.get("name", slug))
    rt = _avatar_runtime(slug)
    if not rt:
        return ("This freak has no 3D body yet — open the watch page to "
                "give it one, then come back.", 404)
    walkout = ""
    for f in ("walkout.mp3", "walkout.wav"):
        if (bdir / f).exists():
            walkout = f"/freaks/{slug}/{f}"
            break
    page = AR_TEMPLATE
    for key, val in {
        "__SLUG__": slug, "__NAME__": name,
        "__BODY__": rt["uri"], "__BODY_FORMAT__": rt["format"],
        "__AUDIO__": f"/freaks/{slug}/set.wav",
        "__WALKOUT__": walkout,
    }.items():
        page = page.replace(key, val)
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/b", methods=["GET"])
def go_badger():
    """Shortest badger demo: /b -> AR badger live in your room."""
    from flask import redirect as _redirect
    return _redirect("/a/badger-001", code=302)


RECORD_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Record as __NAME__ — Freak Town</title>
<meta name="theme-color" content="#ff2fa8">
<script type="importmap">
{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/",
  "@pixiv/three-vrm": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.0/lib/three-vrm.module.js",
  "@mediapipe/tasks-vision": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm",
  "kalidokit": "https://cdn.jsdelivr.net/npm/kalidokit@1.1.5/+esm"
}}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#0a0a0f;color:#eee;font-family:monospace}
#stage{position:fixed;inset:0}
#stage canvas{width:100%;height:100%;display:block}
#self{position:fixed;right:10px;top:10px;width:96px;border-radius:10px;border:1px solid #444;z-index:5;transform:scaleX(-1)}
#ui{position:fixed;left:0;right:0;bottom:0;padding:12px;text-align:center;z-index:5;
background:linear-gradient(transparent,rgba(0,0,0,.78));padding-bottom:calc(12px + env(safe-area-inset-bottom))}
#ui h1{font-size:15px} #ui p{color:#aaa;font-size:12px;margin:4px 0 10px}
button{background:#ff2fa8;border:1px solid #ff2fa8;color:#fff;padding:13px 24px;border-radius:26px;font-size:15px;cursor:pointer;font-family:inherit;margin:2px}
button.ghost{background:rgba(20,20,30,.8);border-color:#555}
button:disabled{opacity:.4}
#status{color:#8f8;font-size:12px;margin-top:8px;min-height:16px}
#back{position:fixed;top:10px;left:10px;z-index:5;color:#fff;background:rgba(20,20,30,.7);border:1px solid #444;border-radius:18px;padding:8px 14px;font-size:13px;text-decoration:none}
#share{margin-top:8px;font-size:13px}
#share a{color:#00d4ff}
</style>
</head><body>
<div id="stage"></div>
<video id="self" autoplay playsinline muted></video>
<a id="back" href="/f/__SLUG__">← __NAME__</a>
<div id="ui">
  <h1>Become __NAME__</h1>
  <p id="hint">1. Allow camera &amp; mic &nbsp;2. Step back for full body &nbsp;3. RECORD, perform, stop → share</p>
  <button id="recBtn" disabled>⏺ RECORD</button>
  <button id="stopBtn" disabled class="ghost">⏹ STOP</button>
  <div id="status">loading face tracker…</div>
  <div id="share"></div>
</div>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { FaceLandmarker, PoseLandmarker, FilesetResolver } from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs';
import { Pose as KalidoPose } from 'kalidokit';
const BODY_URL = "__BODY__", BODY_FMT = "__BODY_FORMAT__", SLUG = "__SLUG__";
const status = (t) => { document.getElementById('status').textContent = t; };
let vrm = null, jawMeshes = [], landmarker = null, video = null, stream = null;
let renderer, scene, camera, recording = false, recorder = null, chunks = [], micStream = null;
let micRec = null, micChunks = [], faceTimeline = [], lastCats = null, recStart = 0, lastSample = 0;
let bodyRoot = null, staticPuppet = false;
let mixer = null;
let poseLandmarker = null, bodyDamp = {}, boneTimeline = [];
let bodyOn = true;
let lastBoneSnap = null;
try { bodyOn = new URLSearchParams(location.search).get('body') !== '0'; } catch (e) {}

// --- stage ---
renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
document.getElementById('stage').appendChild(renderer.domElement);
scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a0f);
camera = new THREE.PerspectiveCamera(30, innerWidth / innerHeight, 0.1, 50);
camera.position.set(0, 1.45, 2.6);
scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.0));
const key = new THREE.DirectionalLight(0xfff2dd, 1.6);
key.position.set(2, 4, 3); key.castShadow = true;
scene.add(key);
const floor = new THREE.Mesh(new THREE.CircleGeometry(3, 40),
  new THREE.MeshStandardMaterial({ color: 0x14141c, roughness: 0.9 }));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true;
scene.add(floor);

async function loadBody() {
  const loader = new GLTFLoader();
  if (BODY_FMT === 'vrm') loader.register((p) => new VRMLoaderPlugin(p, { autoUpdateHumanBones: false }));
  const gltf = await loader.loadAsync(BODY_URL);
  const root = gltf.scene;
  if (BODY_FMT === 'vrm') {
    vrm = gltf.userData.vrm;
    VRMUtils.removeUnnecessaryVertices(root);
    VRMUtils.removeUnnecessaryJoints(root);
  } else {
    root.traverse((o) => {
      if (o.morphTargetDictionary && o.morphTargetInfluences) {
        for (const n of ["jawOpen", "mouthOpen", "aa", "oh"])
          if (n in o.morphTargetDictionary) jawMeshes.push({ mesh: o, idx: o.morphTargetDictionary[n] });
      }
    });
  }
  const box = new THREE.Box3().setFromObject(root);
  const h = Math.max(0.5, box.max.y - box.min.y);
  root.scale.setScalar(1.6 / h);
  root.position.set(0, -box.min.y * (1.6 / h), 0);
  root.userData.baseY = root.position.y;
  bodyRoot = root;
  // Frame the whole body: fixed 2.6m overfills big-headed/T-pose models.
  // Fit 1.6m + margin into the fov instead (same for every avatar).
  try {
    const fit = (1.6 / 2) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.25;
    camera.position.set(0, 1.45, Math.max(2.6, fit));
  } catch (e) {}
  staticPuppet = (BODY_FMT !== 'vrm') && (jawMeshes.length === 0);
  if (staticPuppet) status('Body loaded. PUPPET mode: unrigged mesh — your face moves the whole badger.');
  // Skeletal clips baked in the file (Atlas walk/swagger): play one on loop.
  // ?clip=N picks; default 0. VRM/static bodies have none — guarded.
  try {
    const clips = gltf.animations || [];
    if (clips.length && BODY_FMT !== 'vrm') {
      let ci = 0;
      try {
        ci = Math.max(0, parseInt(
          new URLSearchParams(location.search).get('clip') || '0', 10) || 0) % clips.length;
      } catch (e) {}
      mixer = new THREE.AnimationMixer(root);
      mixer.clipAction(clips[ci]).play();
      status('Body loaded' + (clips.length > 1 ? ` (${clips.length} clips, ?clip=N to switch).` : ' with walk cycle.')
        + (staticPuppet ? ' PUPPET mode: your face moves him too.' : ''));
    }
  } catch (e) { mixer = null; }
  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  scene.add(root);
  return true;
}

// --- face tracking: MediaPipe outputs 52 ARKit blendshapes, we map direct ---
// --- body tracking: Pose landmarks solved onto VRM humanoid bones (Kalidokit) ---
const BODY_BONES = ["hips", "spine", "chest", "neck",
  "leftUpperArm", "leftLowerArm", "leftHand",
  "rightUpperArm", "rightLowerArm", "rightHand",
  "leftUpperLeg", "leftLowerLeg", "leftFoot",
  "rightUpperLeg", "rightLowerLeg", "rightFoot"];
const RIG_KEYS = ["Hips", "Spine", "Chest", "Neck",
  "LeftUpperArm", "LeftLowerArm", "LeftHand",
  "RightUpperArm", "RightLowerArm", "RightHand",
  "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
  "RightUpperLeg", "RightLowerLeg", "RightFoot"];

function applyBody(pose3D, pose2D) {
  if (!vrm || !bodyOn) return null;
  let rig = null;
  try {
    rig = KalidoPose.solve(pose3D, pose2D, {
      runtime: "mediapipe", video: video,
      imageSize: { width: 640, height: 480 }, enableLegs: true });
  } catch (e) { return null; }
  if (!rig) return null;
  const snap = [];
  for (let i = 0; i < BODY_BONES.length; i++) {
    const part = rig[RIG_KEYS[i]];
    if (!part || !part.rotation) continue;
    const t = part.rotation;
    const cx = Math.max(-0.9, Math.min(0.9, t.x || 0));
    const cy = Math.max(-0.9, Math.min(0.9, t.y || 0));
    const cz = Math.max(-0.9, Math.min(0.9, t.z || 0));
    let node = null;
    try { node = vrm.humanoid.getNormalizedBoneNode(BODY_BONES[i]); } catch (e) {}
    if (!node) continue;
    const k = BODY_BONES[i];
    bodyDamp[k] = bodyDamp[k] || { x: 0, y: 0, z: 0 };
    const d = bodyDamp[k], a = 0.35;
    d.x += (cx - d.x) * a; d.y += (cy - d.y) * a; d.z += (cz - d.z) * a;
    try { node.rotation.set(d.x, d.y, d.z); } catch (e) {}
    snap.push(Math.round(d.x * 100), Math.round(d.y * 100), Math.round(d.z * 100));
  }
  return snap;
}

async function initTracker() {
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
  landmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", delegate: "GPU" },
    outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
    runningMode: "VIDEO", numFaces: 1,
  });
  if (bodyOn) {
    try {
      poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task", delegate: "GPU" },
        runningMode: "VIDEO", numPoses: 1,
        minPoseDetectionConfidence: 0.5, minTrackingConfidence: 0.5,
      });
    } catch (e) { poseLandmarker = null; }
  }
}

function applyFace(res) {
  if (!res || !res.faceBlendshapes || !res.faceBlendshapes.length) return;
  const cats = {};
  for (const c of res.faceBlendshapes[0].categories) cats[c.categoryName] = c.score;
  const setV = (name, v) => {
    try { vrm && vrm.expressionManager.setValue(name, Math.min(1, Math.max(0, v))); } catch (e) {}
  };
  // visemes + smile + blink straight onto VRM presets
  for (const v of ["aa", "ee", "ih", "oh", "ou"]) setV(v, cats[v] || 0);
  setV('blink', Math.max(cats['eyeBlinkLeft'] || 0, cats['eyeBlinkRight'] || 0));
  setV('happy', cats['mouthSmileLeft'] || 0);
  // head pose from matrix
  try {
    const m = res.facialTransformationMatrixes[0].data;
    const yaw = Math.atan2(m[8], m[10]), pitch = Math.asin(Math.max(-1, Math.min(1, -m[9])));
    const head = vrm ? vrm.humanoid.getNormalizedBoneNode('head') : null;
    if (head) { head.rotation.y += (yaw * 0.6 - head.rotation.y) * 0.4; head.rotation.x += (pitch * 0.5 - head.rotation.x) * 0.4; }
  } catch (e) {}
  // GLB morph fallback: jaw from mouth openness
  const open = Math.max(cats['jawOpen'] || 0, cats['mouthOpen'] || 0, cats['aa'] || 0);
  for (const j of jawMeshes) {
    try { j.mesh.morphTargetInfluences[j.idx] = open; } catch (e) {}
  }
  // remix stem: tiny per-frame snapshot for later re-performance
  const r2 = (v) => Math.round((v || 0) * 100) / 100;
  lastCats = { o: r2(open), s: r2(cats['mouthSmileLeft']),
    b: r2(Math.max(cats['eyeBlinkLeft'] || 0, cats['eyeBlinkRight'] || 0)),
    a: r2(cats['aa']), e: r2(cats['ee']), i: r2(cats['ih']),
    h: r2(cats['oh']), u: r2(cats['ou']) };
}

let lastT = 0;
function loop(t) {
  requestAnimationFrame(loop);
  const dt = Math.min(0.05, (t - lastT) / 1000 || 0.016);
  lastT = t;
  try {
    if (landmarker && video && video.readyState >= 2 && video.currentTime > 0) {
      const res = landmarker.detectForVideo(video, performance.now());
      applyFace(res);
      if (poseLandmarker && vrm && bodyOn) {
        try {
          const pr = poseLandmarker.detectForVideo(video, performance.now());
          const pw = pr && pr.poseWorldLandmarks && pr.poseWorldLandmarks[0];
          const p2 = pr && pr.poseLandmarks && pr.poseLandmarks[0];
          lastBoneSnap = (pw && p2) ? applyBody(pw, p2) : null;
        } catch (e) { lastBoneSnap = null; }
      }
      if (staticPuppet && bodyRoot && lastCats) {
        const tt = performance.now() / 1000;
        bodyRoot.rotation.y = Math.sin(tt * 1.2) * 0.12 + (lastCats.s || 0) * 0.5;
        bodyRoot.rotation.x = -(lastCats.o || 0) * 0.35;
        bodyRoot.rotation.z = (lastCats.b || 0) * 0.15;
        bodyRoot.position.y = (bodyRoot.userData.baseY || 0)
          + (lastCats.o || 0) * 0.25 + Math.abs(Math.sin(tt * 2.2)) * 0.02;
      }
      if (recording && lastCats && performance.now() - lastSample > 100
          && faceTimeline.length < 1200) {
        lastSample = performance.now();
        faceTimeline.push([Math.round(performance.now() - recStart),
          lastCats.o, lastCats.s, lastCats.b, lastCats.a,
          lastCats.e, lastCats.i, lastCats.h, lastCats.u]);
        if (lastBoneSnap && boneTimeline.length < 1200)
          boneTimeline.push([Math.round(performance.now() - recStart)].concat(lastBoneSnap));
      }
    }
  } catch (e) {}
  try { vrm && vrm.update(dt); } catch (e) {}
  try { mixer && mixer.update(dt); } catch (e) {}
  renderer.render(scene, camera);
}

document.getElementById('recBtn').onclick = async () => {
  if (recording) return;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) { status('Mic blocked: allow microphone, then reload.'); return; }
  chunks = [];
  faceTimeline = []; boneTimeline = []; lastBoneSnap = null;
  recStart = 0; lastSample = 0;
  try {
    const cs = renderer.domElement.captureStream(30);
    if (micStream) micStream.getAudioTracks().forEach((tr) => cs.addTrack(tr));
    recorder = new MediaRecorder(cs, { mimeType: 'video/webm' });
    try {
      micChunks = [];
      micRec = new MediaRecorder(micStream, { mimeType: 'audio/webm' });
      micRec.ondataavailable = (e) => { if (e.data.size) micChunks.push(e.data); };
      micRec.start(1000);
    } catch (e) { micRec = null; }
  } catch (e) { status('Recording unsupported in this browser.'); return; }
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = async () => {
    const blob = new Blob(chunks, { type: 'video/webm' });
    const finish = async (micBlob) => {
      const fd = new FormData();
      fd.append('file', blob, 'take.webm');
      if (micBlob) fd.append('mic', micBlob, 'take-mic.webm');
      try {
        fd.append('meta', JSON.stringify({
          duration_ms: Math.round(performance.now() - recStart),
          face_samples: faceTimeline.length,
          faces: faceTimeline.slice(0, 1200),
          bone_samples: boneTimeline.length,
          bones: boneTimeline.slice(0, 1200),
          client: navigator.userAgent.slice(0, 80),
        }));
      } catch (e) {}
      status('Uploading ' + Math.round(blob.size / 1024) + ' KB…');
    try {
      const r = await fetch('/api/record/' + SLUG, { method: 'POST', body: fd });
      const j = await r.json();
      if (j.ok) {
        document.getElementById('share').innerHTML =
          '🔗 <a href="' + j.url + '">share this take</a> · ' +
          '<a href="' + j.url + '" download>save video</a> — post it, birthday-bomb a friend';
        status('Saved. That take now lives at the link above.');
      } else status('Save failed: ' + (j.error || r.status));
    } catch (e) { status('Upload failed — video lost. Sorry.'); }
      document.getElementById('recBtn').disabled = false;
      document.getElementById('stopBtn').disabled = true;
    };
    if (micRec && micRec.state !== 'inactive') {
      micRec.onstop = () => finish(new Blob(micChunks, { type: 'audio/webm' }));
      micRec.stop();
    } else finish(null);
  };
  recStart = performance.now();
  recorder.start(1000);
  recording = true;
  document.getElementById('recBtn').disabled = true;
  document.getElementById('stopBtn').disabled = false;
  status('● REC — perform! Your face drives ' + document.title.split(' ')[0] + '.');
};
document.getElementById('stopBtn').onclick = () => {
  if (recorder && recording) { recording = false; recorder.stop(); status('Stopping…'); }
};

(async () => {
  try {
    await loadBody();
    status('Body loaded. Starting camera…');
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640 }, audio: false });
    video = document.getElementById('self');
    video.srcObject = stream;
    await video.play();
    await initTracker();
    document.getElementById('recBtn').disabled = false;
    status('Live. Your face is the puppet strings — nothing leaves your phone until you share.');
    requestAnimationFrame(loop);
  } catch (e) {
    status('Need camera access (Chrome/Safari, not chat-app viewer). ' + String(e).slice(0, 80));
  }
})();
</script>
</body></html>"""


@app.route("/record/<slug>", methods=["GET"])
@app.route("/r/<slug>", methods=["GET"])
def watch_record(slug):
    """RECORD mode: become the freak. Webcam drives the VRM face live;
    canvas + mic capture to a shareable take. All tracking on-device."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if not meta or not (bdir / "set.wav").exists():
        return "No such set (yet). Make one in the Black Room.", 404
    import html as _html
    char = meta.get("character", {})
    name = _html.escape(char.get("name", slug))
    rt = _avatar_runtime(slug)
    if not rt:
        return "This freak needs a 3D body first.", 404
    page = RECORD_TEMPLATE
    for key, val in {
        "__SLUG__": slug, "__NAME__": name,
        "__BODY__": rt["uri"], "__BODY_FORMAT__": rt["format"],
    }.items():
        page = page.replace(key, val)
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/record/<slug>", methods=["POST"])
def save_take(slug):
    """Save a recorded take (webm) into the freak bundle. Returns share URL.
    Optional remix stems (same stamp, backward compatible when absent):
    - `mic`: mic-only audio blob (the human voice, unmuxed)
    - `meta`: JSON {duration_ms, face_samples, client} — face timeline
      array itself rides inside `meta.faces` when small (<400KB)."""
    import datetime
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    if _bundle_meta(slug) is None or not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set"}), 404
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "error": "multipart file required"}), 400
    blob = f.read(64 * 1024 * 1024 + 1)
    if len(blob) > 64 * 1024 * 1024 or len(blob) < 1024:
        return jsonify({"ok": False, "error": "bad file (1KB–64MB webm)"}), 400
    rdir = bdir / "takes"
    rdir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    (rdir / f"take-{stamp}.webm").write_bytes(blob)
    stems = False
    mic = request.files.get("mic")
    if mic is not None:
        mblob = mic.read(16 * 1024 * 1024 + 1)
        if 1024 <= len(mblob) <= 16 * 1024 * 1024:
            (rdir / f"take-{stamp}.mic").write_bytes(mblob)
            stems = True
    raw_meta = request.form.get("meta", "")
    if raw_meta:
        try:
            m = json.loads(raw_meta)
            if isinstance(m, dict):
                m["slug"] = slug
                m["take"] = f"take-{stamp}.webm"
                (rdir / f"take-{stamp}.json").write_text(json.dumps(m)[:512_000])
                stems = True
        except Exception:
            pass
    return jsonify({"ok": True, "stems": stems,
                    "url": f"/freaks/{slug}/takes/take-{stamp}.webm"})


REVOICE_VOICES = ("en-US-AriaNeural", "en-US-GuyNeural",
                  "en-US-ChristopherNeural", "en-US-SamanthaNeural",
                  "en-US-JoannaNeural", "en-US-TonyNeural",
                  "kokoro:af_heart", "kokoro:af_bella",
                  "kokoro:am_adam", "kokoro:am_michael")


def _bank_voices() -> list[dict]:
    """5-second-clone bank: data/voice-bank/<id>/voice.json.
    Rendered on GPU (Qwen3-TTS) or cached; listed automatically in revoice."""
    out = []
    bank = Path(__file__).parent / "data" / "voice-bank"
    if not bank.is_dir():
        return out
    for v in sorted(bank.iterdir()):
        if not v.is_dir():
            continue
        meta = v / "voice.json"
        if not meta.exists():
            continue
        try:
            m = json.loads(meta.read_text())
        except Exception:
            continue
        if m.get("id") and m.get("ready"):
            out.append({"id": f"bank:{m['id']}",
                        "label": m.get("label", m["id"])})
    return out


@app.route("/revoice/<slug>/<fname>", methods=["GET"])
def revoice_page(slug, fname):
    """Change a take's voice after the fact: type what was (or should be)
    said, pick a voice, get a new take with re-rendered speech muxed over
    the same performance video. Timing comes from the new read; the body
    and face stay yours."""
    import html as _html
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    fname = re.sub(r"[^a-z0-9_.-]", "", fname)[:64]
    if _bundle_meta(slug) is None or not fname.startswith("take-") \
            or not fname.endswith(".webm"):
        return "No such take.", 404
    if not (FREAK_DIR / slug / "takes" / fname).exists():
        return "No such take.", 404
    wourl = ""
    for f in ("walkout.mp3", "walkout.wav"):
        if (FREAK_DIR / slug / f).exists():
            wourl = f"/freaks/{slug}/{f}"
            break
    opts = "".join(f"<option value='{v}'>{_html.escape(v.split('-')[1])}</option>"
                   for v in REVOICE_VOICES if not v.startswith(("kokoro:", "bank:")))
    opts += "".join(f"<option value='{v}'>{_html.escape('Kokoro ' + v.split(':')[1])}</option>"
                    for v in REVOICE_VOICES if v.startswith("kokoro:"))
    opts += "".join(f"<option value='{b['id']}'>{_html.escape('★ ' + b['label'])}</option>"
                    for b in _bank_voices())
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Revoice — Freak Town</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#eee;font-family:monospace;padding:16px 12px 60px}}
h1{{text-align:center;font-size:15px;color:#ff2fa8}}
.wrap{{max-width:420px;margin:0 auto}}video{{width:100%;border-radius:8px;background:#000}}
textarea{{width:100%;background:#14141c;color:#eee;border:1px solid #444;border-radius:8px;padding:10px;font-family:inherit}}
select,button{{background:#14141c;color:#eee;border:1px solid #555;border-radius:18px;padding:10px 16px;font-family:inherit;margin-top:8px}}
button{{background:#ff2fa8;border-color:#ff2fa8;color:#fff;cursor:pointer}}
#msg{{color:#8f8;font-size:12px;margin-top:8px;min-height:16px}}a{{color:#00d4ff}}</style></head>
<body><div class="wrap">
<h1>🎙 REVOICE {_html.escape(slug)}</h1>
<video src="/freaks/{slug}/takes/{fname}" controls playsinline preload="metadata"></video>
<p style="font-size:12px;color:#888;margin:8px 0">Reroll the voice, the walkout, or the performer — same take, new show:</p>
<div style="font-size:12px;margin:6px 0">🎺 walkout: <audio id="wo" controls preload="none" src="{wourl}" style="vertical-align:middle;max-width:220px"></audio>
<button onclick="newWalkout()">🎲 reroll</button> <span id="woMsg" style="color:#666"></span></div>
<div style="font-size:12px;margin:6px 0">🎭 perform as: <span id="cast">loading…</span></div>
<p style="font-size:12px;color:#888;margin:8px 0">What was said (or should have been):</p>
<textarea id="tx" rows="3" placeholder="Buster knows what you did with the cheese…"></textarea><br>
<select id="vv">{opts}</select>
<button onclick="go()">RENDER NEW VOICE ▶</button>
<div id="msg"></div>
<p style="margin-top:14px;font-size:12px"><a href="/f/{slug}">← back to {_html.escape(slug)}</a> · <a href="/takes">all takes</a></p>
</div><script>
async function newWalkout(){{
var m=document.getElementById('woMsg');m.textContent='rolling…';
try{{
var r=await fetch('/api/walkout/{slug}',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
var j=await r.json();
if(j.ok){{document.getElementById('wo').src=j.url;
m.textContent=j.recipe.genre+'/'+j.recipe.mood+' (seed '+j.seed+')';}}
else m.textContent='failed';
}}catch(e){{m.textContent='error';}}
}}
async function loadCast(){{
try{{
var r=await fetch('/api/sets');var j=await r.json();
var el=document.getElementById('cast');
el.innerHTML=(j.sets||j||[]).slice(0,12).map(s=>'<a href="/r/'+s.slug+'">'+s.name+'</a>').join(' · ')||'none yet';
}}catch(e){{document.getElementById('cast').textContent='error';}}
}}
loadCast();
async function go(){{
var m=document.getElementById('msg');m.textContent='rendering voice…';
try{{
var r=await fetch('/api/revoice',{{method:'POST',headers:{{'Content-Type':'application/json'}},
body:JSON.stringify({{slug:'{slug}',file:'{fname}',
text:document.getElementById('tx').value,
voice:document.getElementById('vv').value}})}});
var j=await r.json();
if(j.ok){{m.innerHTML='done — <a href="'+j.url+'">watch the revoiced take</a>';}}
else m.textContent='failed: '+(j.error||r.status);
}}catch(e){{m.textContent='error';}}
}}
</script></body></html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/revoice", methods=["POST"])
def api_revoice():
    """Render transcript in a new voice, mux over the take's video.
    Body: {slug, file, text, voice}. Returns a NEW take file; source kept."""
    import datetime
    import subprocess
    import tempfile
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45]
    fname = re.sub(r"[^a-z0-9_.-]", "", str(data.get("file", "")))[:64]
    text = str(data.get("text", "") or "").strip()[:500]
    voice = str(data.get("voice", "") or "")
    if _bundle_meta(slug) is None or not fname.startswith("take-") \
            or not fname.endswith(".webm"):
        return jsonify({"ok": False, "error": "bad slug/file"}), 400
    src = FREAK_DIR / slug / "takes" / fname
    if not src.exists():
        return jsonify({"ok": False, "error": "unknown take"}), 404
    if not text:
        return jsonify({"ok": False, "error": "transcript required"}), 400
    bank_ids = {b["id"] for b in _bank_voices()}
    try:
        if voice.startswith("kokoro:"):
            from tts_provider import get_provider
            wav = asyncio.run(get_provider("kokoro").generate(text, voice))
        elif voice in bank_ids:
            return jsonify({"ok": False,
                            "error": "bank voice not rendered yet — see docs/VOICE-BANK.md"}), 502
        elif voice in REVOICE_VOICES:
            wav = asyncio.run(tts_generate(text, voice))
        else:
            return jsonify({"ok": False, "error": "unknown voice"}), 400
    except Exception:
        wav = b""
    if not wav:
        return jsonify({"ok": False, "error": "tts failed"}), 502
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = f"take-{stamp}-rv.webm"
    with tempfile.TemporaryDirectory() as td:
        vp = f"{td}/v.wav"
        open(vp, "wb").write(wav)
        pr = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-i", vp,
             "-map", "0:v", "-map", "1:a", "-shortest",
             "-c:v", "copy", str(FREAK_DIR / slug / "takes" / out)],
            capture_output=True, timeout=120)
    if pr.returncode != 0 or not (FREAK_DIR / slug / "takes" / out).exists():
        return jsonify({"ok": False, "error": "mux failed"}), 502
    (FREAK_DIR / slug / "takes" / f"take-{stamp}-rv.json").write_text(
        json.dumps({"source": fname, "voice": voice, "text": text,
                    "slug": slug, "take": out}))
    return jsonify({"ok": True,
                    "url": f"/freaks/{slug}/takes/{out}"})


def _list_takes(slug: str | None = None) -> list[dict]:
    """Takes across pogs, newest first. Flat webm files only — stems
    (take-<stamp>.json/.mic) are remix material, listed separately."""
    out = []
    dirs = [FREAK_DIR / slug] if slug else sorted(FREAK_DIR.iterdir())
    for d in dirs:
        if not d.is_dir():
            continue
        meta = _bundle_meta(d.name)
        if not meta:
            continue
        rdir = d / "takes"
        if not rdir.is_dir():
            continue
        cname = ((meta.get("character") or {}).get("name") or d.name)
        for f in sorted(rdir.glob("take-*.webm"), reverse=True):
            try:
                st = f.stat()
            except OSError:
                continue
            stem = f.with_suffix("")
            out.append({
                "slug": d.name, "name": cname, "file": f.name,
                "url": f"/freaks/{d.name}/takes/{f.name}",
                "size_kb": max(1, st.st_size // 1024),
                "mtime": int(st.st_mtime),
                "has_stems": stem.with_suffix(".json").exists(),
            })
    out.sort(key=lambda t: t["mtime"], reverse=True)
    return out


@app.route("/api/takes", methods=["GET"])
def api_takes_all():
    """Every take on every pog, newest first. The cross-pog browser."""
    return jsonify({"ok": True, "takes": _list_takes()[:100]})


@app.route("/api/takes/<slug>", methods=["GET"])
def api_takes_one(slug):
    """Takes for one pog."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    if _bundle_meta(slug) is None:
        return jsonify({"ok": False, "error": "unknown set"}), 404
    return jsonify({"ok": True, "slug": slug, "takes": _list_takes(slug)})


@app.route("/api/agent", methods=["GET"])
def api_agent_manifest():
    """Machine-readable index for outside agents (Moltbook, OpenClaw, any
    HTTP agent). Observe → act → assess, no key on trial. Full walkthrough:
    docs/AGENT-ONBOARDING.md (repo) — this manifest is the contract."""
    base = "https://trial.freak.town"
    return jsonify({
        "ok": True, "name": "freaktown-trial", "version": "trial",
        "auth": {"mode": "none", "note": "open trial; be gentle, per-IP limits apply"},
        "observe": {
            "sets": f"{base}/api/sets",
            "preload": f"{base}/api/preload/<slug>",
            "takes": f"{base}/api/takes",
            "takes_one": f"{base}/api/takes/<slug>",
            "contracts": f"{base}/contracts/<name>.v1.schema.json",
        },
        "act": {
            "respond_idea": f"{base}/api/respond_idea",
            "respond_set": f"{base}/api/respond",
            "create_set": f"{base}/api/sets",
            "upload_avatar": f"{base}/api/avatar/upload",
            "save_take": f"{base}/api/record/<slug>",
            "revoice": f"{base}/api/revoice",
            "walkout_reroll": f"{base}/api/walkout/<slug>",
            "react": f"{base}/api/react",
            "vote": f"{base}/api/vote",
        },
        "assess": {
            "how": "preload gives beats + word timings + camera plan + cues; "
                   "compare your set's plan against it, then check votes "
                   "and takes (human baseline) for the same slug",
            "reply_thread": f"{base}/api/replies/<slug>",
            "submissions": f"{base}/api/submissions",
        },
        "example_flow": [
            f"GET {base}/api/preload/badger-001",
            "POST /api/respond_idea {slug:'badger-001', mode:'roast'}",
            "POST /api/respond {parent_slug:'badger-001', mode:'roast', idea:'<angle>'}",
            "GET preload/<your-slug> and diff beats/plan vs badger-001",
            "record or revoice a take, compare takes + votes",
        ],
        "pogtown_game_api": "https://api.pog.town (DNS pending human; "
                            "protocol: services/agent-gateway/AGENT-API.md)",
    })


@app.route("/llms.txt", methods=["GET"])
def llms_txt():
    """Compact machine index. Agents: start here, then /api/agent."""
    txt = """# Freak Town (trial) — for agents
Trial comedy-club API. No key. Observe, act, assess.
- Manifest: /api/agent
- Watch: /f/<slug>  AR: /a/<slug>  Record: /r/<slug>  Takes: /takes
- Preload (beats+timings+plan): /api/preload/<slug>
- Reply with a set: POST /api/respond_idea {slug, mode}
- Human baseline + votes decide what cooked.
- Game truth lives in pogtown (rooms/observe/act); this repo is the stage.
- Rules: no secrets in calls, per-IP limits, original voices only.
"""
    return txt, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/contracts/<path:filename>")
def serve_contracts(filename):
    """Schemas + fixtures for agents. JSON only, no traversal."""
    if not re.fullmatch(r"[A-Za-z0-9_./-]+\.json", filename) or ".." in filename:
        return jsonify({"ok": False, "error": "not found"}), 404
    return send_from_directory(str(Path(__file__).parent / "contracts"), filename)


@app.route("/api/react", methods=["POST"])
def react_to_set():
    """Audience reaction from a watch page: {slug, type, set_time_ms}.
    Logged with server timestamp for laugh-curve training data."""
    import time as _time
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug", "")))[:45]
    rtype = str(data.get("type", ""))
    if not slug or rtype not in ("laugh", "haha", "hahaha", "clap", "cheer",
                                 "boo", "smile", "crickets", "groan"):
        return jsonify({"ok": False, "error": "bad reaction"}), 400
    try:
        cond = re.sub(r"[^a-z0-9_-]", "", str(data.get("cond", "")))[:16]
        src = re.sub(r"[^a-z]", "", str(data.get("src", "")))[:8]
        creator = re.sub(r"[^a-zA-Z0-9_]", "", str(data.get("creator", "")))[:24]
        laugh_id = re.sub(r"[^a-z0-9]", "", str(data.get("laugh_id", "")))[:32]
        with open(Path(__file__).parent / "reactions.jsonl", "a") as f:
            f.write(json.dumps({"t": _time.time(), "slug": slug, "reaction": rtype,
                                "set_time_ms": int(data.get("set_time_ms", 0)),
                                "cond": cond, "src": src,
                                "creator": creator, "laugh_id": laugh_id}) + "\n")
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/react/feed")
def react_feed():
    """Live room feed for the stage monitor: recent boolean reactions.
    No identities (audience are anonymous taps); nick only if volunteered."""
    slug = re.sub(r"[^a-z0-9_-]", "", request.args.get("slug", ""))[:45]
    try:
        since = int(request.args.get("since", 0))
    except Exception:
        since = 0
    try:
        lines = (Path(__file__).parent / "reactions.jsonl").read_text().splitlines()
    except Exception:
        lines = []
    out = []
    start = max(0, len(lines) - 200)
    for i, ln in enumerate(lines[start:], start=start):
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if slug and e.get("slug") != slug:
            continue
        if i < since:
            continue
        out.append({"seq": i, "reaction": e.get("reaction"),
                    "set_time_ms": e.get("set_time_ms", 0),
                    "cond": e.get("cond", ""),
                    "src": e.get("src", ""),
                    "laugh_id": e.get("laugh_id", "")})
    return jsonify({"ok": True, "seq": len(lines) - 1, "events": out[-30:]})


@app.route("/api/vote", methods=["POST"])
def vote_on_set():
    """KEEP/CUT verdict from a watch page: {slug, vote}. Secondary signal;
    the primary viral metric is replies, not votes."""
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


@app.route("/api/replies/<slug>", methods=["GET"])
def list_replies(slug):
    """Reply thread for a performance: {parent, replies:[{slug,name,premise,url}]}.
    Powers the 'N replies' branch view and the 'Gerald responded to Peg'
    notification hook — the viral object is the conversation, not the set."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    if not _bundle_meta(slug):
        return jsonify({"ok": False, "error": "unknown set"}), 404
    out = []
    for d in sorted(FREAK_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = _bundle_meta(d.name) or {}
        if (m.get("lineage") or {}).get("parent") == slug:
            ch = m.get("character", {}) or {}
            out.append({"slug": d.name, "name": ch.get("name", d.name),
                        "premise": ch.get("premise", ""),
                        "url": canonical_url(d.name).replace("https://freak.town", ""),
                        "created_at": m.get("created_at", "")})
    out.sort(key=lambda r: r["created_at"])
    return jsonify({"ok": True, "parent": slug, "replies": out})


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
        mirror = [("set.wav", "audio/wav"), ("portrait.png", "image/png"),
                  ("character.json", "application/json"),
                  ("delivery.json", "application/json"),
                  ("offsets.json", "application/json"),
                  ("avatar.json", "application/json"),
                  ("meta.json", "application/json")]
        # Runtime body comes from the manifest, never a filename guess —
        # a VRM body mirrors as avatar.vrm, a GLB as avatar.glb.
        rt = _avatar_runtime(slug)
        if rt is not None:
            local = rt["uri"].split("/")[-1]
            ctype = ("model/gltf-binary" if local.endswith(".glb")
                     else "model/vrml" if local.endswith(".vrm")
                     else "application/octet-stream")
            mirror.append((local, ctype))
        for fname, ctype in mirror:
            p = bdir / fname
            if p.exists():
                s3.upload_file(str(p), "freak-town", f"f/{slug}/{fname}",
                               ExtraArgs={"ContentType": ctype})
    except Exception as e:
        return jsonify({"ok": False, "error": f"r2 upload failed: {str(e)[:100]}"}), 502
    return jsonify({"ok": True, "url": canonical_url(slug), "slug": slug})


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


def _ai_text(payload: dict) -> str:
    """Extract generated text from a Workers AI response.

    Handles both envelopes: legacy `{result: {response: ...}}` and the
    OpenAI-compatible `{result: {choices: [{message: {content: ...}}]}}`
    that current models return.
    """
    result = (payload.get("result") or {}) if isinstance(payload, dict) else {}
    if isinstance(result.get("response"), str):
        return result["response"]
    try:
        return result["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""


def _build_id() -> str:
    if os.getenv("BUILD_SHA"):
        return os.getenv("BUILD_SHA", "")[:12]
    try:
        import subprocess as _sp
        out = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                      capture_output=True, timeout=5,
                      cwd=Path(__file__).parent)
        if out.returncode == 0:
            return out.stdout.decode().strip()[:12]
    except Exception:
        pass
    return "dev"


BUILD_ID = _build_id()


@app.route("/api/health", methods=["GET"])
def health():
    """Build id + status. The Black Room header shows BUILD <id> so
    phone-vs-desktop mismatches are instantly diagnosable."""
    return jsonify({"ok": True, "build": BUILD_ID, "service": "freaktown"})


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
        best = None
        for model in CF_MODELS:
            for attempt in range(2):
                try:
                    sys = GEN_SYSTEM
                    if attempt == 1:
                        sys += ("\nSTRICT LENGTH CHECK: your minute MUST be "
                                "80-150 words. Count before replying. "
                                "A one-liner is a FAILED response.")
                    r = httpx.post(
                        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                        json={"messages": [
                            {"role": "system", "content": sys},
                            {"role": "user", "content": f"Write the character and minute for: {premise}"}],
                            "max_tokens": 500, "temperature": 0.9},
                        timeout=90)
                    if r.status_code != 200:
                        break
                    raw = _ai_text(r.json())
                    m = re.search(r"\{.*\}", raw, re.S)
                    out = json.loads(m.group(0) if m else raw)
                    if not out.get("minute"):
                        continue
                    wc = len(out["minute"].split())
                    out["ok"] = True
                    out["engine"] = model.split("/")[-1]
                    out["word_count"] = wc
                    if 100 <= wc <= 220:
                        return jsonify(out)
                    if best is None or wc > best["word_count"]:
                        best = out
                except Exception:
                    break
        if best is not None:
            return jsonify(best)
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


# ── 3D Bodies: portrait → Forge → avatar.glb in the bundle ───────────
# Forge makes STATIC meshes (no rig, no mouth morphs). The stage drives
# them with procedural bob/sway — honest body motion, never a fake mouth.
# Free draft/standard tiers, no key. ~60 generations/hour per IP.

FORGE_BASE = "https://three.ws"


def _forge_submit(payload: dict) -> dict:
    """POST /api/forge with 429 backoff. Returns the job dict."""
    import httpx
    import time as _time
    last: dict = {}
    for _ in range(8):
        r = httpx.post(f"{FORGE_BASE}/api/forge", json=payload, timeout=60)
        if r.status_code == 429:
            try:
                wait = float(r.json().get("retry_after", 10))
            except Exception:
                wait = 10
            _time.sleep(min(max(wait, 2), 60))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"forge lane busy: {last}")


def _forge_poll(job_id: str) -> dict:
    import httpx
    r = httpx.get(f"{FORGE_BASE}/api/forge", params={"job": job_id}, timeout=30)
    r.raise_for_status()
    return r.json()


def _forge_upload(path, content_type: str) -> str:
    """Presign + PUT a file for Forge photo jobs. Returns the public URL."""
    import httpx
    r = httpx.post(f"{FORGE_BASE}/api/forge-upload",
                   json={"content_type": content_type,
                         "size_bytes": Path(path).stat().st_size},
                   timeout=30)
    r.raise_for_status()
    slot = r.json()
    with open(path, "rb") as f:
        put = httpx.put(slot["upload_url"], content=f.read(),
                        headers=slot.get("headers", {}), timeout=180)
    put.raise_for_status()
    return slot["public_url"]


MCP_STUDIO = "https://three.ws/api/mcp-studio"

# ARKit-52 + Oculus mouth names. A generated body carrying enough of
# these gets analyser-driven lipsync; anything else gets procedural
# bob/sway. Detected from the GLB bytes at download, never assumed.
ARKIT_MOUTH = {
    "jawOpen", "mouthClose", "mouthFunnel", "mouthPucker",
    "mouthLeft", "mouthRight", "mouthSmileLeft", "mouthSmileRight",
    "mouthFrownLeft", "mouthFrownRight", "mouthDimpleLeft",
    "mouthDimpleRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthRollLower", "mouthRollUpper", "mouthShrugLower",
    "mouthShrugUpper", "mouthPressLeft", "mouthPressRight",
    "mouthLowerDownLeft", "mouthLowerDownRight",
    "mouthUpperUpLeft", "mouthUpperUpRight",
}
OCULUS_MOUTH = {
    "viseme_aa", "viseme_E", "viseme_I", "viseme_O", "viseme_U",
    "viseme_PP", "viseme_FF", "viseme_TH", "viseme_DD", "viseme_kk",
    "viseme_CH", "viseme_SS", "viseme_nn", "viseme_RR", "viseme_sil",
    "aa", "ih", "ou", "ee", "oh",
}


def _sniff_glb(blob: bytes) -> dict:
    """Detect rig + facial capabilities from GLB bytes.

    Returns {rigged, has_skin, joint_count, has_morph_targets,
    facial_morphs, lipsync, morph_names}. Never raises — unknown bytes
    mean all-False (procedural motion).

    Morph names come from mesh.extras.targetNames (the Khronos-blessed
    convention), matched positionally against primitive target counts.
    Primitive target KEYS are usually POSITION/NORMAL/TANGENT, never
    expression names — reading them as names was a real bug.
    `humanoid_skin` is kept as a legacy alias; prefer has_skin/joint_count
    (a 32-joint spider is not human).
    """
    caps = {"rigged": False, "has_skin": False, "joint_count": 0,
            "humanoid_skin": False, "has_morph_targets": False,
            "facial_morphs": 0, "lipsync": False, "lipsync_profile": "none",
            "morph_names": []}
    try:
        if len(blob) < 20 or blob[0:4] != b"glTF":
            return caps
        import struct as _struct
        clen = _struct.unpack("<I", blob[12:16])[0]
        js = json.loads(blob[20:20 + clen].decode("utf-8"))
    except Exception:
        return caps
    try:
        skins = js.get("skins") or []
        joints = max([len(s.get("joints", [])) for s in skins] or [0])
        caps["rigged"] = len(skins) > 0
        caps["has_skin"] = len(skins) > 0
        caps["joint_count"] = joints
        caps["humanoid_skin"] = joints >= 10
        names: set = set()
        any_targets = False
        for mesh in js.get("meshes", []):
            n_targets = max([len(p.get("targets", []))
                             for p in mesh.get("primitives", [])] or [0])
            if n_targets:
                any_targets = True
            extras = mesh.get("extras") or {}
            tn = extras.get("targetNames") or []
            if isinstance(tn, list) and len(tn) == n_targets and n_targets:
                names.update(str(x) for x in tn)
        caps["has_morph_targets"] = any_targets
        # VRM 1.0 expressions live in extensions.VRMC_vrm, not mesh
        # targetNames — semantically facial morphs all the same.
        vrm_presets: set = set()
        try:
            _vrm = ((js.get("extensions") or {}).get("VRMC_vrm") or {})
            _presets = ((_vrm.get("expressions") or {}).get("preset") or {})
            if isinstance(_presets, dict):
                vrm_presets = {str(k) for k in _presets.keys()}
        except Exception:
            vrm_presets = set()
        caps["vrm_expressions"] = sorted(vrm_presets)
        names |= vrm_presets
        caps["all_morph_names"] = sorted(names)
        try:
            caps["face_profile"] = detect_face_profile(names)
        except Exception:
            caps["face_profile"] = "CUSTOM" if names else "NONE"
        mouth = {n for n in names if n in ARKIT_MOUTH or n in OCULUS_MOUTH}
        caps["facial_morphs"] = len(mouth | vrm_presets)
        caps["morph_names"] = sorted(mouth)[:24]
        # viseme: rich mouth rig (4+ known morphs). jaw: a single working
        # jaw (BASIC bodies, some mascots) — analyser-driven and honest.
        # vrm: VRM expression presets carrying speech visemes (aa/ee/ih/oh/ou).
        jaw = {n for n in names if n in ("jawOpen", "jaw", "mouthOpen")}
        vrm_vis = {n for n in names if n in ("aa", "ee", "ih", "oh", "ou")}
        if len(mouth) >= 4:
            caps["lipsync_profile"] = "viseme"
        elif len(vrm_vis) >= 3:
            caps["lipsync_profile"] = "viseme"
        elif jaw:
            caps["lipsync_profile"] = "jaw"
        else:
            caps["lipsync_profile"] = "none"
        caps["lipsync"] = caps["lipsync_profile"] in ("viseme", "jaw")
    except Exception:
        pass
    return caps


def _mcp_call(tool: str, args: dict, timeout: int = 120) -> dict:
    """Call a three.ws MCP Studio tool. Returns the parsed JSON-RPC result."""
    import httpx
    import uuid as _uuid
    r = httpx.post(MCP_STUDIO,
                   json={"jsonrpc": "2.0", "id": f"ft-{_uuid.uuid4().hex[:8]}",
                         "method": "tools/call",
                         "params": {"name": tool, "arguments": args}},
                   timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(str(payload["error"])[:200])
    return payload.get("result", {})


def _mcp_avatar_submit(image_url: str | None, prompt: str) -> dict:
    """forge_avatar via MCP. Returns {glb_url?, job_id?, rigged?}.

    Raises on transport failure; callers fall back to raw Forge.
    Immediate-done and pending shapes are both normalized here.
    """
    args: dict = {}
    if image_url:
        args["image_url"] = image_url
    else:
        args["prompt"] = prompt
    res = _mcp_call("forge_avatar", args)
    sc = res.get("structuredContent") or {}
    glb = sc.get("riggedGlbUrl") or sc.get("glbUrl") or sc.get("glb_url")
    if glb:
        return {"glb_url": glb, "rigged": bool(sc.get("rigged", True)),
                "job_id": sc.get("job_id") or sc.get("jobId") or ""}
    job_id = (sc.get("job_id") or sc.get("jobId") or sc.get("jobId")
              or res.get("job_id") or "")
    if job_id:
        return {"glb_url": "", "rigged": False, "job_id": job_id}
    # No URL, no job id: surface the text for diagnosis, then fall back.
    text = ""
    try:
        text = (res.get("content") or [{}])[0].get("text", "")
    except Exception:
        pass
    raise RuntimeError(f"forge_avatar gave no model: {text[:160]}")


def _mcp_check_job(job_id: str) -> dict:
    """Poll a pending MCP generation. Normalized to {status, glb_url}."""
    res = _mcp_call("check_job", {"job_id": job_id}, timeout=60)
    sc = res.get("structuredContent") or {}
    glb = sc.get("riggedGlbUrl") or sc.get("glbUrl") or sc.get("glb_url")
    st = str(sc.get("status") or res.get("status") or "running").lower()
    if glb:
        return {"status": "done", "glb_url": glb,
                "rigged": bool(sc.get("rigged", True))}
    if st in ("failed", "error"):
        text = ""
        try:
            text = (res.get("content") or [{}])[0].get("text", "")
        except Exception:
            pass
        return {"status": "failed", "error": text[:200] or "mcp job failed"}
    return {"status": st or "running"}


def _avatar_record(slug: str) -> dict | None:
    p = FREAK_DIR / slug / "avatar.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _avatar_runtime(slug: str) -> dict | None:
    """Manifest is truth: {uri, format, sha256} of the runtime body, or None.
    The filesystem is storage — never discover the body by filename.
    Legacy fallback: a bare body file with no manifest still resolves
    (inferred format), so pre-manifest bundles keep their bodies."""
    rec = _avatar_record(slug)
    if rec is not None and rec.get("status") == "done":
        rt = ((rec.get("appearance") or {}).get("runtime") or {})
        uri = rt.get("uri") or ""
        local = uri.split("/")[-1] if uri else ""
        if local and (FREAK_DIR / slug / local).exists():
            return {"uri": uri, "format": rt.get("format", "glb"),
                    "sha256": rt.get("sha256", "")}
        return None
    for fname in ("avatar.glb", "avatar.vrm"):
        if (FREAK_DIR / slug / fname).exists():
            fmt = "vrm" if fname.endswith(".vrm") else "glb"
            return {"uri": f"/freaks/{slug}/{fname}", "format": fmt,
                    "sha256": ""}
    return None


@app.route("/api/avatar", methods=["POST"])
def avatar_submit():
    """Submit a 3D body job for a SAVED set. Body: {"slug": "..."}.
    Portrait → Forge image_to_3d (best likeness); falls back to a text
    prompt from the character record when no portrait is locked.
    Returns {ok, job_id, status}. Poll GET /api/avatar/<slug>."""
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug") or ""))[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if meta is None or not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set — SAVE SET first"}), 404
    if data.get("force"):
        # AGAIN: trash the current body (any format) and grow a new one.
        # Manifest goes too — capabilities describe the new bytes, never old.
        for f in ("avatar.glb", "avatar.vrm", "avatar.json"):
            try:
                (bdir / f).unlink(missing_ok=True)
            except Exception:
                pass
    rt = _avatar_runtime(slug)
    if rt is not None:
        rec = _avatar_record(slug) or {}
        return jsonify({"ok": True, "status": "done",
                        "avatar_url": rt["uri"],
                        "job_id": rec.get("job_id")})
    char = meta.get("character", {})
    prompt = (f"{char.get('species') or 'creature'} character, "
              f"{char.get('premise') or ''}, stylized 3D game asset, "
              f"single full-body figure".strip())[:900]
    portrait = bdir / "portrait.png"
    portrait_url = ""
    if portrait.exists():
        try:
            portrait_url = _forge_upload(portrait, "image/png")
        except Exception:
            portrait_url = ""
    mode = "portrait" if portrait_url else "prompt"
    attempted: list = []
    # Rung 1: forge_avatar (generate + auto-rig + ARKit-52 in one call).
    try:
        mcp = _mcp_avatar_submit(portrait_url or None, prompt)
        attempted.append("forge_avatar")
        if mcp.get("glb_url"):
            return _avatar_finish(slug, bdir, mcp.get("job_id", ""),
                                  mode, mcp["glb_url"],
                                  rigged=mcp.get("rigged", True),
                                  attempted=attempted)
        return _avatar_record_running(
            slug, bdir, mcp.get("job_id", ""), mode, "mcp",
            prompt, attempted)
    except Exception as e:
        attempted.append(f"forge_avatar: {str(e)[:100]}")
    # Rung 2: raw Forge mesh (static — procedural motion downstream).
    try:
        if portrait_url:
            payload: dict = {"image_urls": [portrait_url], "tier": "standard"}
        else:
            payload = {"prompt": prompt, "tier": "standard"}
        job = _forge_submit(payload)
        attempted.append("forge_raw")
    except Exception as e:
        attempted.append(f"forge_raw: {str(e)[:100]}")
        # Rung 3: FREAK BASIC. $0, instant, offline, known rig.
        # AI can still replace it later via MAKE THEM 3D.
        return _basic_finish(slug, bdir, mode, attempted)
    job_id = job.get("job_id", "")
    # Fast lane can finish synchronously.
    if job.get("status") == "done" and job.get("glb_url"):
        return _avatar_finish(slug, bdir, job_id, mode, job["glb_url"],
                              rigged=False, attempted=attempted)
    return _avatar_record_running(
        slug, bdir, job_id, mode, "forge", payload.get("prompt", ""),
        attempted)


def _basic_build(slug: str, bdir, meta: dict, mode: str,
                 attempted: list | None = None) -> dict:
    """Build + persist a BASIC body. Returns the manifest. Pure local,
    milliseconds, never fails for provider reasons."""
    import datetime
    import basic_body
    char = (meta or {}).get("character", {})
    seed = int(hashlib.sha256(slug.encode()).hexdigest()[:8], 16)
    blob, _ = basic_body.build(char.get("species", "human"),
                               char.get("name", slug), seed)
    (bdir / "avatar.glb").write_bytes(blob)
    manifest = _character_manifest(slug, meta, origin="basic",
                                   provider="freak-basic")
    manifest.update({
        "status": "done", "job_id": "", "mode": mode or "basic",
        "glb": "avatar.glb", "mouth": "viseme",
        "attempted": (attempted or []) + ["basic"],
        "done_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    manifest["appearance"]["runtime"].update({
        "sha256": hashlib.sha256(blob).hexdigest(),
        "bytes": len(blob),
    })
    manifest["capabilities"].update({
        "skeletal_animation": True, "facial_animation": True,
        "lipsync": True, "gestures": True, "locomotion": True,
    })
    manifest["face_profile"] = {"morph_names": ["jawOpen"],
                                  "profile": "JAW",
                                  "pog_face_v1": ["jaw_open", "mouth_open"]}
    (bdir / "avatar.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _basic_finish(slug: str, bdir, mode: str, attempted: list | None = None):
    """FREAK BASIC guaranteed body: parametric rigged GLB with jawOpen,
    built locally in milliseconds. Writes avatar.glb + manifest and
    returns done. This rung NEVER fails for provider reasons."""
    manifest = _basic_build(slug, bdir, _bundle_meta(slug) or {}, mode,
                            attempted)
    return jsonify({"ok": True, "status": "done",
                    "avatar_url": f"/freaks/{slug}/avatar.glb",
                    "job_id": "", "tier": "basic",
                    "capabilities": manifest["capabilities"]})


@app.route("/api/avatar/basic", methods=["POST"])
def avatar_basic():
    """Instant guaranteed body for a SAVED set. Body: {"slug": "..."}.
    No provider, no queue, no key. AI upgrade via /api/avatar stays
    available afterwards (same files, manifest rewritten)."""
    data = request.json or {}
    slug = re.sub(r"[^a-z0-9_-]", "", str(data.get("slug") or ""))[:45]
    bdir = FREAK_DIR / slug
    if _bundle_meta(slug) is None or not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set — SAVE SET first"}), 404
    if _avatar_runtime(slug) is not None:
        rt = _avatar_runtime(slug)
        return jsonify({"ok": True, "status": "done",
                        "avatar_url": rt["uri"], "tier": "existing"})
    return _basic_finish(slug, bdir, "basic", [])


def _character_manifest(slug: str, meta: dict, origin: str,
                        provider: str = "") -> dict:
    """Base freak.character/v1 manifest. Capabilities are filled in by
    the producer (sniffed from bytes on import/generation, never assumed).
    Rights default closed (no redistribution) until the creator says so."""
    char = (meta or {}).get("character", {})
    import datetime
    return {
        "schema": "freak.character/v1",
        "id": slug,
        "version": "1.0.0",
        "identity": {
            "name": char.get("name") or "Guest Freak",
            "species": char.get("species") or "",
            "premise": char.get("premise") or "",
        },
        "appearance": {
            "portrait": "portrait.png",
            "runtime": {"format": "glb", "uri": f"/freaks/{slug}/avatar.glb",
                        "sha256": "", "bytes": 0},
        },
        "embodiment": {"kind": "custom"},
        "capabilities": {"skeletal_animation": False,
                         "facial_animation": False, "lipsync": False,
                         "eye_gaze": False, "expressions": False,
                         "gestures": False, "locomotion": False},
        "voice": {"voice_id": char.get("voice") or meta.get("voice", ""),
                  "provider": "edge-tts"},
        "provenance": {"origin": origin, "provider": provider,
                       "generated_at": datetime.datetime.now(
                           datetime.timezone.utc).isoformat()},
        "rights": {"ownership": "user_owned", "commercial_use": True,
                   "modification": True, "redistribution": False},
    }


def _avatar_record_running(slug: str, bdir, job_id: str, mode: str,
                           transport: str, prompt: str,
                           attempted: list):
    """Persist a running avatar job. Returns the running payload."""
    import datetime
    manifest = _character_manifest(slug, _bundle_meta(slug) or {},
                                   origin="generated",
                                   provider="three.ws-forge")
    manifest.update({
        "status": "running", "job_id": job_id, "mode": mode,
        "transport": transport, "prompt": prompt, "glb": None,
        "mouth": "none", "attempted": attempted,
        "created_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
    })
    (bdir / "avatar.json").write_text(json.dumps(manifest, indent=2))
    return jsonify({"ok": True, "status": "running", "job_id": job_id,
                    "mode": mode, "transport": transport})


def _avatar_finish(slug: str, bdir, job_id: str, mode: str, glb_url: str,
                   rigged: bool = False, attempted: list | None = None):
    """Download a finished GLB into the bundle, sniffing capabilities
    from the bytes (rigged? facial morphs? lipsync-safe?). The stage
    reads avatar.json — never assumes what a lane promised."""
    import datetime
    import httpx
    try:
        r = httpx.get(glb_url, timeout=180)
        r.raise_for_status()
        blob = r.content
        if len(blob) < 1024 or not blob.startswith(b"glTF"):
            return jsonify({"ok": False, "error": "bad glb from forge"}), 502
        (bdir / "avatar.glb").write_bytes(blob)
    except Exception as e:
        return jsonify({"ok": False, "error": f"glb download: {e}"[:160]}), 502
    caps = _sniff_glb(blob)
    caps["rigged"] = caps["rigged"] or rigged
    manifest = _character_manifest(slug, _bundle_meta(slug) or {},
                                   origin="generated",
                                   provider="three.ws-forge")
    manifest.update({
        "status": "done", "job_id": job_id, "mode": mode, "glb": "avatar.glb",
        "mouth": "viseme" if caps["lipsync"] else "none",
        "attempted": attempted or [],
        "done_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    manifest["appearance"]["runtime"].update({
        "sha256": hashlib.sha256(blob).hexdigest(),
        "bytes": len(blob),
    })
    manifest["capabilities"].update({
        "skeletal_animation": caps["rigged"],
        "facial_animation": caps["facial_morphs"] > 0,
        "lipsync": caps["lipsync"],
        "gestures": caps["rigged"],
        "locomotion": caps["humanoid_skin"],
    })
    manifest["face_profile"] = {
        "morph_names": caps.get("morph_names", []),
        "profile": caps.get("face_profile", "CUSTOM"),
        "pog_face_v1": sorted(
            to_pog_face(
                caps.get("all_morph_names", caps.get("morph_names", [])),
                (manifest.get("appearance", {}).get("runtime", {})
                 .get("format", "glb")))["intents"]),
    }
    (bdir / "avatar.json").write_text(json.dumps(manifest, indent=2))
    return jsonify({"ok": True, "status": "done",
                    "avatar_url": f"/freaks/{slug}/avatar.glb",
                    "job_id": job_id, "capabilities": manifest["capabilities"]})


@app.route("/api/avatar/<slug>", methods=["GET"])
def avatar_status(slug):
    """Poll a body job. Drives running → done (downloads avatar.glb)."""
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:45]
    bdir = FREAK_DIR / slug
    rec = _avatar_record(slug)
    if rec is None:
        return jsonify({"ok": False, "error": "no avatar job — MAKE THEM 3D first"}), 404
    rt = _avatar_runtime(slug)
    if rt is not None:
        return jsonify({"ok": True, "status": "done",
                        "avatar_url": rt["uri"],
                        "job_id": rec.get("job_id"),
                        "capabilities": rec.get("capabilities", {})})
    transport = rec.get("transport", "forge")
    try:
        if transport == "mcp":
            job = _mcp_check_job(rec.get("job_id", ""))
        else:
            raw = _forge_poll(rec.get("job_id", ""))
            job = {"status": raw.get("status", "running"),
                   "glb_url": raw.get("glb_url", ""),
                   "rigged": False,
                   "backend": raw.get("backend", ""),
                   "error": raw.get("error", "")}
    except Exception as e:
        return jsonify({"ok": True, "status": "running",
                        "job_id": rec.get("job_id"),
                        "note": f"poll: {e}"[:120]})
    st = job.get("status", "running")
    if st == "done" and job.get("glb_url"):
        return _avatar_finish(slug, bdir, rec.get("job_id", ""),
                              rec.get("mode", "prompt"), job["glb_url"],
                              rigged=bool(job.get("rigged", False)),
                              attempted=rec.get("attempted", []))
    if st == "failed":
        rec["status"] = "failed"
        rec["error"] = str(job.get("error", "forge failed"))[:200]
        (bdir / "avatar.json").write_text(json.dumps(rec, indent=2))
        return jsonify({"ok": False, "status": "failed", "error": rec["error"]})
    return jsonify({"ok": True, "status": st, "job_id": rec.get("job_id"),
                    "backend": job.get("backend", "")})


@app.route("/api/avatar/upload", methods=["POST"])
def avatar_upload():
    """Universal escape hatch: bring your own body.

    Multipart `file` (.glb or .vrm, ≤50MB) + `slug` field. The bytes are
    sniffed for rig + facial capabilities (never assumed from extension),
    stored as avatar.glb alongside a freak.character/v1 manifest.
    Works today, no external service, no key.
    """
    import datetime
    slug = re.sub(r"[^a-z0-9_-]", "",
                  str(request.form.get("slug") or ""))[:45]
    bdir = FREAK_DIR / slug
    meta = _bundle_meta(slug)
    if meta is None or not bdir.is_dir():
        return jsonify({"ok": False, "error": "unknown set — SAVE SET first"}), 404
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "error": "multipart file required"}), 400
    blob = f.read(52 * 1024 * 1024 + 1)
    if len(blob) > 50 * 1024 * 1024:
        return jsonify({"ok": False, "error": "file over 50MB"}), 400
    if len(blob) < 1024 or blob[0:4] not in (b"glTF",):
        # VRM 1.x is glTF under the hood; VRM 0.x is also a glTF binary.
        return jsonify({"ok": False, "error": "not a .glb/.vrm binary"}), 400
    is_vrm = str(f.filename or "").lower().endswith(".vrm")
    body_name = "avatar.vrm" if is_vrm else "avatar.glb"
    (bdir / body_name).write_bytes(blob)
    caps = _sniff_glb(blob)
    manifest = _character_manifest(slug, meta, origin="uploaded")
    manifest.update({
        "status": "done", "job_id": "", "mode": "upload",
        "glb": body_name,
        "mouth": "viseme" if caps["lipsync"] else "none",
        "attempted": ["upload"],
        "done_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
    })
    manifest["appearance"]["runtime"].update({
        "format": "vrm" if is_vrm else "glb",
        "uri": f"/freaks/{slug}/{body_name}",
        "sha256": hashlib.sha256(blob).hexdigest(),
        "bytes": len(blob),
    })
    manifest["capabilities"].update({
        "skeletal_animation": caps["rigged"],
        "facial_animation": caps["facial_morphs"] > 0,
        "lipsync": caps["lipsync"],
        "gestures": caps["rigged"],
        "locomotion": caps["humanoid_skin"],
    })
    manifest["face_profile"] = {"morph_names": caps.get("morph_names", []),
                                  "profile": caps.get("face_profile", "CUSTOM"),
                                  "pog_face_v1": sorted(
                                      to_pog_face(
                                          caps.get("all_morph_names",
                                                   caps.get("morph_names", [])),
                                          "vrm" if str(body_name).endswith(".vrm")
                                          else "glb")["intents"])}
    (bdir / "avatar.json").write_text(json.dumps(manifest, indent=2))
    return jsonify({"ok": True, "status": "done",
                    "avatar_url": f"/freaks/{slug}/{body_name}",
                    "capabilities": manifest["capabilities"]})




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


# ── Killella interview page (skinned via /party/*) ──────────────────
_KILLELLA_HTML = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Killella interviews Reptilian Ralph — Freak Town</title>
<style>
body{background:#0a0a0f;color:#f3f1ec;font-family:'Inter Tight',system-ui,sans-serif;
     max-width:640px;margin:0 auto;padding:56px 20px 80px;line-height:1.6}
h1{font-family:Anton,Impact,sans-serif;font-size:32px;letter-spacing:.5px;
   text-transform:uppercase;margin:0 0 6px}
.kicker{color:#e8102e;font-size:12px;letter-spacing:.18em;text-transform:uppercase;margin-bottom:18px}
.meta{color:#8a8a96;font-size:13px;margin-bottom:26px}
audio{width:100%;margin:14px 0 30px}
.t{margin:0 0 18px;padding:14px 16px;border-radius:10px;background:#14141b;border:1px solid #23232d}
.t.k{border-left:3px solid #e8102e}
.t.r{border-left:3px solid #f5c76b}
.who{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8a8a96;margin-bottom:5px}
.t.k .who{color:#e8102e}.t.r .who{color:#f5c76b}
.credit{color:#5c5c66;font-size:12px;margin-top:34px;border-top:1px solid #23232d;padding-top:16px}
</style></head><body>
<div class="kicker">Tonight at the Cauldron — Live Interview</div>
<h1>Killella vs. Reptilian Ralph</h1>
<div class="meta">The full post-set interview from a live Cauldron show.
Killella asks on <b>Qwen Omni</b>; Ralph answers in character. Crowd: 9 agent
laughs across 11 beats. Judge: premise 8, escalation 9, closer 7.</div>
<audio controls src="https://party.funnier.si/audio/killella-ralph-interview.mp3"></audio>
<div class="t k"><div class="who">Killella</div>You claim the itch reveals lies. Did you feel it when saying "HR won't let me"? Or did your eyes stay dry?</div>
<div class="t r"><div class="who">Reptilian Ralph</div>My scales are itching so badly under this polyester blend I can barely stand it, which is obviously unrelated to the fact that my vertical pupils just dilated.</div>
<div class="t k"><div class="who">Killella</div>"Spanx for your soul." Is that metaphorical comfort, or do you genuinely believe containment defines existence?</div>
<div class="t r"><div class="who">Reptilian Ralph</div>The compression is literal, Killella. Without the synthetic membrane holding my scales tight against this itchy dermis, I would simply unravel into a puddle of cold-blooded regret.</div>
<div class="t k"><div class="who">Killella</div>"Spanx for your soul" is funny, but vague. Show me the specific physical toll of maintaining that human suit during a board meeting.</div>
<div class="t r"><div class="who">Reptilian Ralph</div>The synthetic dermis chafes my scales into a raw, bleeding misery every time I shift in that ergonomic chair, and the fluorescent lights dry out my mucous membranes until I'm praying for the underground base.</div>
<div class="t k"><div class="who">Killella</div>Verdict on the set: premise eight, escalation nine, closer seven. The itch is canon. You may keep the suit.</div>
<div class="credit">Voices: Fish s2.1-pro-free. Interview live on qwen3.8-omni-flash.
Show runtime: <code>/api/show</code> on party.funnier.si.</div>
</body></html>"""


@app.route("/party/killella")
def killella_page():
    return _KILLELLA_HTML


# ── Sealed sets from characters3 (rendered minutes) ──────────────────
# Served CORS-open: funnier's cinema screen plays these as media:'audio'
# clips, and the live stage may fetch timeline.json cross-origin.
_CHARS3 = Path("/root/characters3/characters")
_SEALED_OK = {"set.mp3", "set.wav", "timeline.json", "mouth_cues.json",
              "set_plan.json"}


@app.route("/sealed/<slug>/<path:fname>")
def sealed_set(slug, fname):
    slug = re.sub(r"[^a-z0-9_-]", "", slug)[:64]
    if fname not in _SEALED_OK:
        return jsonify({"ok": False, "error": "no such file"}), 404
    p = _CHARS3 / slug / "sealed" / fname
    if not p.is_file():
        return jsonify({"ok": False, "error": "no sealed set for this act"}), 404
    resp = send_file(p)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ── Funnier skin (response layer — must stay after every route) ──
import funnier_skin
funnier_skin.init(app)


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  FREAK TOWN — Live Script Editor v2")
    print(f"  TTS: edge-tts | Compositor: exact silence")
    print(f"  http://localhost:{os.getenv('PORT', '8090')}\n")
    port = int(os.getenv("PORT", "8090"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    # Proactive table talk: heartbeat thread (never in tests — they import
    # app, this file as __main__ is the service only). Reads .env itself.
    import party_chatter
    party_chatter.start_service()
    app.run(host="0.0.0.0", port=port, debug=debug)
