#!/usr/bin/env python3
"""Freak Town web MVP.

One performer. One ~60 second set. One audience member for now.
Every laugh/clap is recorded against the set clock and the completed session
is persisted as structured JSON under web/data/sessions/.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import edge_tts
except ImportError:  # Browser speech synthesis is a valid zero-dependency fallback.
    edge_tts = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from comedians import ALL_COMEDIANS
except ImportError:
    ALL_COMEDIANS = []

PORT = int(os.getenv("PORT", "8080"))
TARGET_SECONDS = float(os.getenv("FREAKTOWN_SET_SECONDS", "60"))
DISABLE_TTS = os.getenv("FREAKTOWN_DISABLE_TTS", "").lower() in {"1", "true", "yes"}
STATIC_DIR = Path(__file__).resolve().parent / "static"
AUDIO_DIR = Path(__file__).resolve().parent / "audio"
SESSION_DIR = Path(__file__).resolve().parent / "data" / "sessions"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_AVATAR = os.getenv("FREAKTOWN_AVATAR_URL", "https://three.ws/avatars/michelle.glb")
ALLOWED_REACTIONS = {"laugh", "clap"}

FALLBACK_SETS = [
    {
        "name": "Ella M",
        "slug": "ella-m",
        "premise": "Host of Freak Town trying stand-up herself",
        "voice": "en-US-AriaNeural",
        "minute": (
            "I host a show where artificial personalities do stand-up comedy. "
            "People keep asking whether the robots are actually funny. Sometimes. "
            "Which is already a terrifyingly strong result. Humans spend ten years "
            "developing a voice. A language model gets one system prompt and immediately "
            "starts asking for a Netflix special. Last week one told me it was working "
            "on its material. I said, you do not have material. You have a probability "
            "distribution and Wi-Fi. It said that's still more infrastructure than most "
            "open mics. I hated that because it was correct. The real problem is the "
            "audience now has a laugh button. So I can finally quantify exactly how much "
            "you dislike me. Comedy used to be art. Now it is telemetry. Welcome to Freak Town."
        ),
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: float) -> float:
    return round(float(value), 3)


def build_timeline(events: list[dict], duration_seconds: float, bin_seconds: int = 5) -> list[dict]:
    duration = max(0.001, float(duration_seconds))
    bin_count = max(1, int((duration + bin_seconds - 0.000001) // bin_seconds))
    bins = []
    for index in range(bin_count):
        start = index * bin_seconds
        end = min(duration, start + bin_seconds)
        bins.append({
            "from_seconds": _round(start),
            "to_seconds": _round(end),
            "laughs": 0,
            "claps": 0,
            "total": 0,
        })

    for event in events:
        idx = min(len(bins) - 1, int(event["set_time_seconds"] // bin_seconds))
        key = "laughs" if event["type"] == "laugh" else "claps"
        bins[idx][key] += 1
        bins[idx]["total"] += 1
    return bins


def summarize(events: list[dict], duration_seconds: float) -> dict:
    duration = max(0.001, float(duration_seconds))
    laughs = sum(1 for event in events if event["type"] == "laugh")
    claps = sum(1 for event in events if event["type"] == "clap")
    ordered = sorted(events, key=lambda event: event["set_time_seconds"])
    timeline = build_timeline(ordered, duration)
    active_bins = sum(1 for bucket in timeline if bucket["total"] > 0)

    return {
        "reaction_counts": {
            "laugh": laughs,
            "clap": claps,
            "total": laughs + claps,
        },
        "reaction_rate_per_minute": {
            "laugh": round(laughs * 60.0 / duration, 2),
            "clap": round(claps * 60.0 / duration, 2),
            "total": round((laughs + claps) * 60.0 / duration, 2),
        },
        "first_reaction_seconds": ordered[0]["set_time_seconds"] if ordered else None,
        "last_reaction_seconds": ordered[-1]["set_time_seconds"] if ordered else None,
        "active_5s_bins": active_bins,
        "reaction_coverage_5s": round(active_bins / max(1, len(timeline)), 3),
        "timeline_5s": timeline,
    }


class SessionStore:
    """Thread-safe in-memory session store with JSON persistence on completion."""

    def __init__(self, session_dir: Path = SESSION_DIR):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, performer: dict, audio_url: str | None, tts_mode: str) -> dict:
        session_id = str(uuid.uuid4())
        created_at = utc_now()
        session = {
            "schema_version": "freaktown.set.v1",
            "session_id": session_id,
            "status": "ready",
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "target_duration_seconds": TARGET_SECONDS,
            "actual_duration_seconds": None,
            "clock_source": "client_playback_clock",
            "performer": {
                "id": performer.get("slug") or performer.get("name", "performer").lower().replace(" ", "-"),
                "name": performer.get("name", "Unknown Performer"),
                "premise": performer.get("premise", ""),
                "avatar_url": performer.get("avatar_url", DEFAULT_AVATAR),
                "voice": performer.get("voice", "en-US-AriaNeural"),
            },
            "set": {
                "id": hashlib.sha256(performer.get("minute", "").encode("utf-8")).hexdigest()[:16],
                "title": performer.get("premise", "One Minute Set"),
                "transcript": performer.get("minute", ""),
                "audio_url": audio_url,
                "tts_mode": tts_mode,
            },
            "events": [],
            "summary": None,
        }
        with self._lock:
            self._sessions[session_id] = session
        return json.loads(json.dumps(session))

    def start(self, session_id: str) -> dict:
        with self._lock:
            session = self._require(session_id)
            if not session["started_at"]:
                session["started_at"] = utc_now()
                session["status"] = "playing"
            return json.loads(json.dumps(session))

    def record_reaction(
        self,
        session_id: str,
        reaction_type: str,
        set_time_seconds: float,
        audience_member_id: str = "local",
    ) -> dict:
        if reaction_type not in ALLOWED_REACTIONS:
            raise ValueError(f"unsupported reaction type: {reaction_type}")
        timestamp = float(set_time_seconds)
        if timestamp < 0 or timestamp > TARGET_SECONDS + 1:
            raise ValueError("set_time_seconds is outside the set window")

        with self._lock:
            session = self._require(session_id)
            if session["status"] == "complete":
                raise ValueError("session is already complete")
            if not session["started_at"]:
                session["started_at"] = utc_now()
                session["status"] = "playing"
            event = {
                "event_id": str(uuid.uuid4()),
                "seq": len(session["events"]) + 1,
                "type": reaction_type,
                "set_time_seconds": _round(timestamp),
                "received_at": utc_now(),
                "audience_member_id": audience_member_id or "local",
            }
            session["events"].append(event)
            return json.loads(json.dumps(event))

    def complete(self, session_id: str, duration_seconds: float) -> dict:
        duration = min(TARGET_SECONDS, max(0.001, float(duration_seconds)))
        with self._lock:
            session = self._require(session_id)
            if session["status"] != "complete":
                if not session["started_at"]:
                    session["started_at"] = utc_now()
                session["status"] = "complete"
                session["completed_at"] = utc_now()
                session["actual_duration_seconds"] = _round(duration)
                session["summary"] = summarize(session["events"], duration)
                self._persist(session)
            return json.loads(json.dumps(session))

    def get(self, session_id: str) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._require(session_id)))

    def _require(self, session_id: str) -> dict:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown session: {session_id}") from exc

    def _persist(self, session: dict) -> None:
        path = self.session_dir / f"{session['session_id']}.json"
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


STORE = SessionStore()


def choose_performer() -> dict:
    source = ALL_COMEDIANS or FALLBACK_SETS
    performer = dict(random.choice(source))
    performer["avatar_url"] = DEFAULT_AVATAR
    return performer


async def generate_audio(text: str, voice: str) -> Path | None:
    if DISABLE_TTS or edge_tts is None:
        return None
    digest = hashlib.sha256(f"{voice}\0{text}".encode("utf-8")).hexdigest()[:16]
    path = AUDIO_DIR / f"set_{digest}.mp3"
    if path.exists():
        return path
    try:
        communicator = edge_tts.Communicate(text, voice, rate="+8%")
        await communicator.save(str(path))
        return path
    except Exception:
        return None


def generate_audio_sync(text: str, voice: str) -> Path | None:
    return asyncio.run(generate_audio(text, voice))


class StageHandler(SimpleHTTPRequestHandler):
    server_version = "FreakTown/0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "schema_version": "freaktown.set.v1"})
        if parsed.path == "/api/set":
            return self.handle_get_set()
        if parsed.path == "/api/session":
            query = parse_qs(parsed.query)
            session_id = (query.get("id") or [""])[0]
            try:
                return self.send_json(STORE.get(session_id))
            except KeyError as exc:
                return self.send_json({"error": str(exc)}, 404)
        if parsed.path.startswith("/audio/"):
            filename = Path(parsed.path).name
            candidate = AUDIO_DIR / filename
            if not candidate.exists():
                return self.send_error(404)
            payload = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(payload)
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self.read_json()
            if parsed.path == "/api/start":
                return self.send_json(STORE.start(body["session_id"]))
            if parsed.path == "/api/reaction":
                event = STORE.record_reaction(
                    body["session_id"],
                    body["type"],
                    body["set_time_seconds"],
                    body.get("audience_member_id", "local"),
                )
                return self.send_json({"ok": True, "event": event})
            if parsed.path == "/api/complete":
                result = STORE.complete(body["session_id"], body["duration_seconds"])
                return self.send_json(result)
            return self.send_json({"error": "not found"}, 404)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 400)

    def handle_get_set(self):
        performer = choose_performer()
        audio_path = generate_audio_sync(performer.get("minute", ""), performer.get("voice", "en-US-AriaNeural"))
        if audio_path:
            audio_url = f"/audio/{audio_path.name}"
            tts_mode = "edge-tts"
        else:
            audio_url = None
            tts_mode = "browser"
        session = STORE.create(performer, audio_url, tts_mode)
        self.send_json(session)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65536:
            raise ValueError("request body too large")
        payload = self.rfile.read(length) if length else b"{}"
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def send_json(self, payload: dict, status: int = 200):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        if args and "/api/" in str(args[0]):
            return
        super().log_message(fmt, *args)


def main():
    print(f"FREAK TOWN — http://localhost:{PORT}")
    print("A finished set is persisted to web/data/sessions/<session_id>.json")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StageHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
