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

from party import party_bp

app = Flask(__name__)
app.register_blueprint(party_bp)

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
        resolve_avatar, spans_from_offsets, words_from_beats,
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
        duration_ms or (spans[-1].end_ms if spans else 0))
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
    return jsonify({
        "ok": True, "slug": slug,
        "avatarUrl": avatar_url if avatar_source != "default" else None,
        "avatarSource": avatar_source,
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


@app.route("/f/<slug>")
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
    page = WATCH_TEMPLATE
    for key, val in {
        "__SLUG__": slug, "__NAME__": name, "__PREMISE__": premise,
        "__CHAR_SLUG__": char_slug, "__SET_LABEL__": set_label,
        "__NREPLIES__": str(nreplies),
        "__IMG__": img, "__DUR__": str(dur),
        "__BEATS__": json.dumps(beats),
        "__BODY__": body_url, "__BODY_FORMAT__": body_fmt,
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
</div>
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
        mouth = {n for n in names if n in ARKIT_MOUTH or n in OCULUS_MOUTH}
        caps["facial_morphs"] = len(mouth)
        caps["morph_names"] = sorted(mouth)[:24]
        # viseme: rich mouth rig (4+ known morphs). jaw: a single working
        # jaw (BASIC bodies, some mascots) — analyser-driven and honest.
        jaw = {n for n in names if n in ("jawOpen", "jaw", "mouthOpen")}
        if len(mouth) >= 4:
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
    manifest["face_profile"] = {"morph_names": ["jawOpen"]}
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
    manifest["face_profile"] = {"morph_names": caps.get("morph_names", [])}
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


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  FREAK TOWN — Live Script Editor v2")
    print(f"  TTS: edge-tts | Compositor: exact silence")
    print(f"  http://localhost:{os.getenv('PORT', '8090')}\n")
    port = int(os.getenv("PORT", "8090"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
