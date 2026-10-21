"""Cauldron show runtime — the evening's clock, record, and verdict.

One performer comes out (walkout sting), does their minute, then Killella
interviews them. The audience laughs with buttons; agents laugh with HTTP.
The stage renders; this module never emits markup.

ADDITIVE ONLY: new file + 2-line app.py wiring. Game truth for party games
stays in party.py; per-set watch rooms stay in app.py. This owns live
*shows*: the act order, the phase clock, the laugh track, the interview,
the verdict.

Fail-soft rules (killella lesson): host owns the clock, never audio or the
model. Missing sting audio, a dead LLM key, or an empty bundle degrade to
text — never a wedge.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

show_bp = Blueprint("show", __name__)

LOCK = threading.Lock()
BASE = Path(__file__).resolve().parent
PERFORMERS_DIR = Path(os.environ.get("SHOW_PERFORMERS_DIR",
                                     "/root/characters2/freaks"))
STATE_FILE = BASE / "show_rooms.json"

# ── verdict bars (mirror of app.py KILLED rule — app.py is canonical) ──
KILLED_ENERGY = float(os.environ.get("SHOW_KILLED_ENERGY", "12.0"))
KILLED_COVERAGE = float(os.environ.get("SHOW_KILLED_COVERAGE", "0.5"))
KILLED_CREATORS = int(os.environ.get("SHOW_KILLED_CREATORS", "3"))
KILLED_BOOS = int(os.environ.get("SHOW_KILLED_BOOS", "1"))
REACT_W = {"hahaha": 2.0, "haha": 1.0, "laugh": 1.0, "smile": 1.0,
           "cheer": 0.5, "clap": 0.5, "boo": -1.0}
LAUGH_SET = {"hahaha", "haha", "laugh", "smile"}

INTERVIEW_TURNS = int(os.environ.get("SHOW_INTERVIEW_TURNS", "3"))
SET_STUB_BYTES = 100 * 1024  # set.wav smaller than this = placeholder beep
AUDIO_KINDS = ("set", "walkout", "win", "loss")

SHOWS: dict = {}


def _now() -> int:
    return int(time.time() * 1000)


def _code() -> str:
    import random as _r
    import string as _s
    return "".join(_r.choice(_s.ascii_uppercase + _s.digits) for _ in range(4))


# ── performer bundles (characters2 shape) ─────────────────────────────

def _bundle_dir(slug: str) -> Path | None:
    slug = "".join(c for c in (slug or "") if c.isalnum() or c in "-_")[:80]
    d = PERFORMERS_DIR / slug
    return d if d.is_dir() else None


def _sting(bundle: Path, audio_path: str | None) -> Path | None:
    """Resolve a show.json audio_path. Bundle dir, then characters2-wide
    audition audio, then v1 audition audio. None = stage falls back."""
    if not audio_path:
        return None
    for base in (bundle,
                 Path("/root/characters2/audition"),
                 Path("/root/characters/audition")):
        p = base / audio_path
        if p.is_file():
            return p
    return None


def list_ready() -> list:
    """Every performer whose meta.json says status=ready. Never raises."""
    out = []
    try:
        slugs = sorted(p.name for p in PERFORMERS_DIR.iterdir() if p.is_dir())
    except OSError:
        return out
    for slug in slugs:
        try:
            meta = json.loads((PERFORMERS_DIR / slug / "meta.json").read_text())
        except (OSError, ValueError):
            continue
        if meta.get("status") != "ready":
            continue
        try:
            n_beats = len(json.loads(
                (PERFORMERS_DIR / slug / "delivery.json").read_text()).get("beats", []))
        except (OSError, ValueError):
            n_beats = 0
        out.append({"slug": slug, "name": meta.get("name", slug),
                    "voice": meta.get("voice", ""), "beats": n_beats,
                    "words": meta.get("word_count", 0)})
    return out


def load_bundle(slug: str) -> dict | None:
    """Validated bundle facts for one act. Audio resolved or None+stub."""
    d = _bundle_dir(slug)
    if not d:
        return None
    try:
        meta = json.loads((d / "meta.json").read_text())
        delivery = json.loads((d / "delivery.json").read_text())
        character = json.loads((d / "character.json").read_text())
        show = json.loads((d / "show.json").read_text())
    except (OSError, ValueError):
        return None
    set_wav = d / "set.wav"
    set_ok = set_wav.is_file() and set_wav.stat().st_size > SET_STUB_BYTES
    audio = dict(show.get("audio", {}))
    stings = {}
    for kind in ("walkout", "win", "loss"):
        node = audio.get(kind, {}) if isinstance(audio, dict) else {}
        p = _sting(d, node.get("audio_path") if isinstance(node, dict) else None)
        stings[kind] = {"path": str(p) if p else None,
                        "duration_ms": (node.get("duration_ms", 0)
                                        if isinstance(node, dict) else 0),
                        "text": (node.get("text", "")
                                 if isinstance(node, dict) else "")}
    beats = delivery.get("beats", []) if isinstance(delivery, dict) else []
    return {"slug": slug,
            "name": character.get("name", meta.get("name", slug)),
            "voice": meta.get("voice", ""),
            "persona": character.get("persona", {}),
            "beats": [{"id": b.get("id", f"b{i}"),
                       "text": b.get("text", ""),
                       "performance": b.get("performance", {}),
                       "speech": b.get("speech", {})}
                      for i, b in enumerate(beats) if isinstance(b, dict)],
            "entrance": show.get("entrance", {}),
            "set_audio": str(set_wav) if set_ok else None,
            "set_stub": not set_ok,
            "stings": stings}


# ── persistence (same pattern as party_rooms.json; gitignored) ───────

def _save() -> None:
    try:
        STATE_FILE.write_text(json.dumps(SHOWS))
    except OSError:
        pass


def _load() -> None:
    try:
        data = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        SHOWS.update(data)


_load()


# ── interview (Killella vs performer) ─────────────────────────────────

KILLELLA = ("You are Killella, the Cauldron's killer-judge. Dry, surgical, "
            "never cruel about looks, always about the work. One question at "
            "a time, under 30 words. You listened to the set; now interrogate it.")

KILLELLA_DECK = [
    "Which bit died hardest, and whose fault was that — yours or the room's?",
    "Say the premise of your closer back to me in one short sentence.",
    "Pick your most hack line tonight. Why did you keep it?",
    "Who in this room was your set actually for?",
    "If you had to cut one beat to save the minute, which one goes?",
]


def _performer_system(bundle: dict) -> str:
    p = bundle.get("persona", {}) or {}
    facts = "; ".join(str(f) for f in p.get("facts", [])[:6])
    return (f"You are {bundle.get('name', 'the act')}. {p.get('deal', '')} "
            f"Facts: {facts}. Answer in character, one or two lines. "
            f"Never break character, never mention being an AI.")


def _interview_live() -> bool:
    return os.environ.get("PARTY_PI_AGENTS", "0") == "1"


def interview_turn(show: dict) -> dict:
    """One exchange: Killella asks, the act answers. Dry ($0) by default;
    live via Qwen when PARTY_PI_AGENTS=1. Fail-closed to dry on any miss."""
    act = show["act"]
    bundle = act["bundle"]
    beats = bundle.get("beats", [])
    n = len(act["interview"]) // 2
    exchange = {"n": n + 1, "live": False, "q": "", "a": ""}

    q, a = None, None
    if _interview_live():
        try:
            import scripts.party_pi_agents as pi
            ctx = ("Set beats: " + " / ".join(b.get("text", "")[:120]
                   for b in beats[:6]))
            q = pi.agent_line("interview-judge",
                              f"{ctx}. Ask your next question.",
                              "killella", system=KILLELLA)
            if q:
                a = pi.agent_line("interview-performer",
                                  f"Killella asks: {q}",
                                  act["slug"],
                                  system=_performer_system(bundle))
        except Exception:
            q, a = None, None

    if not q:
        deck_q = KILLELLA_DECK[n % len(KILLELLA_DECK)]
        beat = beats[n % len(beats)].get("text", "") if beats else ""
        q = f"{deck_q} (Your bit: \"{beat[:100]}\")" if beat else deck_q
    if not a:
        beat = beats[(n + 1) % len(beats)].get("text", "") if beats else ""
        a = (f"That's the whole bit — \"{beat[:120]}\" — and it stays in."
             if beat else "Next question.")
    else:
        exchange["live"] = True
    exchange["q"], exchange["a"] = q, a
    act["interview"].append({"who": "killella", "text": q, "live": exchange["live"]})
    act["interview"].append({"who": act["slug"], "text": a, "live": exchange["live"]})
    return exchange


# ── verdict ───────────────────────────────────────────────────────────

def _act_verdict(show: dict) -> dict:
    """Crowd (KILLED math on this act's laughs) + judge + sting pick."""
    act = show["act"]
    bundle = act["bundle"]
    beats = bundle.get("beats", [])
    energy, boos, creators = 0.0, 0, set()
    hit: set = set()
    for lf in act["laughs"]:
        t = lf.get("type", "")
        energy += REACT_W.get(t, 0)
        if t == "boo":
            boos += 1
        if lf.get("device"):
            creators.add(lf["device"])
        if t in LAUGH_SET:
            ms = lf.get("ms", 0)
            for i, b in enumerate(beats):
                start = i * max(1, (act.get("set_ms", 60000) // max(1, len(beats))))
                if start - 500 <= ms < start + 2500 + 60000 // max(1, len(beats)):
                    hit.add(i)
                    break
    coverage = len(hit) / max(1, len(beats))
    killed = (energy >= KILLED_ENERGY and coverage >= KILLED_COVERAGE
              and len(creators) >= KILLED_CREATORS and boos <= KILLED_BOOS
              and len(beats) > 0)
    judge = {"status": "pending", "scores": {}, "note": ""}
    if _interview_live():
        try:
            import scripts.party_pi_agents as pi
            txt = " / ".join(b.get("text", "")[:100] for b in beats[:8])
            r = pi.agent_line(
                "interview-judge",
                f"Score this minute 0-10 on premise, escalation, closer. "
                f"Reply ONLY like: premise 7, escalation 8, closer 6. Set: {txt}",
                "killella", system=KILLELLA)
            judge = {"status": "live", "scores": {"raw": (r or "")[:120]},
                     "note": "killella via qwen"}
        except Exception:
            pass
    sting = "win" if killed else "loss"
    return {"killed": killed, "energy": round(energy, 1),
            "coverage": round(coverage, 2), "creators": len(creators),
            "boos": boos, "judge": judge, "sting": sting,
            "sting_audio": bundle.get("stings", {}).get(sting, {}).get("path")}


# ── phase machine ─────────────────────────────────────────────────────

PHASES = ("GREEN_ROOM", "INTRO", "SET", "INTERVIEW", "VERDICT", "ENDED")


def _public_act(show: dict) -> dict:
    act = show["act"]
    bundle = act["bundle"]
    return {"slug": act["slug"], "name": bundle.get("name"),
            "voice": bundle.get("voice", ""),
            "phase": show["phase"],
            "entrance": bundle.get("entrance", {}),
            "beats": bundle.get("beats", []),
            "set_audio_url": (f"/api/show/{show['code']}/audio/set"
                              if bundle.get("set_audio") else None),
            "set_stub": bundle.get("set_stub", True),
            "sting_urls": {k: (f"/api/show/{show['code']}/audio/{k}"
                               if v.get("path") else None)
                           for k, v in bundle.get("stings", {}).items()},
            "laughs": len(act["laughs"]),
            "interview": act["interview"],
            "verdict": act["verdict"]}


def _state(show: dict) -> dict:
    return {"ok": True, "code": show["code"], "venue": show.get("venue", ""),
            "phase": show["phase"], "act_index": show["act_index"],
            "bill": show["performers"], "act": _public_act(show),
            "history": show["history"]}


def _advance_locked(show: dict) -> dict:
    phase, idx = show["phase"], show["act_index"]
    if phase == "GREEN_ROOM":
        show.update(phase="INTRO", act=_new_act(show, idx))
    elif phase == "INTRO":
        show["phase"] = "SET"
        show["act"]["set_started_at"] = _now()
    elif phase == "SET":
        show["phase"] = "INTERVIEW"
    elif phase == "INTERVIEW":
        show["act"]["verdict"] = _act_verdict(show)
        show["phase"] = "VERDICT"
        show["history"].append({"slug": show["act"]["slug"],
                                "verdict": show["act"]["verdict"]})
    elif phase == "VERDICT":
        if idx + 1 < len(show["performers"]):
            show["act_index"] = idx + 1
            show.update(phase="INTRO", act=_new_act(show, idx + 1))
        else:
            show["phase"] = "ENDED"
    show["seq"] = show.get("seq", 0) + 1
    _save()
    return _state(show)


def _new_act(show: dict, idx: int) -> dict:
    slug = show["performers"][idx]
    bundle = load_bundle(slug) or {"slug": slug, "name": slug, "voice": "",
                                   "persona": {}, "beats": [], "entrance": {},
                                   "set_audio": None, "set_stub": True,
                                   "stings": {}}
    return {"slug": slug, "bundle": bundle, "laughs": [], "interview": [],
            "verdict": None, "set_started_at": None,
            "set_ms": 60000, "started_at": _now()}


# ── routes ────────────────────────────────────────────────────────────

@show_bp.route("/api/show/performers", methods=["GET"])
def performers():
    return jsonify({"ok": True, "performers": list_ready(),
                    "dir": str(PERFORMERS_DIR)})


@show_bp.route("/api/show", methods=["GET"])
def list_shows():
    with LOCK:
        return jsonify({"ok": True,
                        "shows": [{"code": c, "phase": s["phase"],
                                   "bill": s["performers"]} for c, s in SHOWS.items()]})


@show_bp.route("/api/show/create", methods=["POST"])
def create_show():
    data = request.json or {}
    slugs = [s for s in (data.get("performers") or []) if _bundle_dir(s)]
    if not slugs:
        return jsonify({"ok": False, "error": "no ready performers"}), 400
    with LOCK:
        code = _code()
        SHOWS[code] = {"code": code, "host_token": secrets.token_urlsafe(16),
                       "venue": str(data.get("venue", "cauldron")),
                       "performers": slugs, "act_index": 0,
                       "phase": "GREEN_ROOM",
                       "act": {"slug": "", "bundle": {}, "laughs": [],
                               "interview": [], "verdict": None},
                       "history": [], "seq": 0, "created_at": _now()}
        _save()
        return jsonify({"ok": True, "code": code,
                        "host_token": SHOWS[code]["host_token"],
                        "bill": slugs})


@show_bp.route("/api/show/<code>/start", methods=["POST"])
def start_show(code):
    show = SHOWS.get((code or "").upper())
    if not show:
        return jsonify({"ok": False, "error": "no such show"}), 404
    with LOCK:
        if show["phase"] != "GREEN_ROOM":
            return jsonify({"ok": False, "error": "already started"}), 400
        return jsonify(_advance_locked(show))


@show_bp.route("/api/show/<code>/advance", methods=["POST"])
def advance(code):
    show = SHOWS.get((code or "").upper())
    if not show:
        return jsonify({"ok": False, "error": "no such show"}), 404
    data = request.json or {}
    if data.get("host_token") != show["host_token"]:
        return jsonify({"ok": False, "error": "host only"}), 403
    with LOCK:
        if show["phase"] == "ENDED":
            return jsonify({"ok": False, "error": "show over"}), 400
        return jsonify(_advance_locked(show))


@show_bp.route("/api/show/<code>", methods=["GET"])
def get_show(code):
    show = SHOWS.get((code or "").upper())
    if not show:
        return jsonify({"ok": False, "error": "no such show"}), 404
    with LOCK:
        return jsonify(_state(show))


@show_bp.route("/api/show/<code>/audio/<kind>", methods=["GET"])
def show_audio(code, kind):
    show = SHOWS.get((code or "").upper())
    if not show or kind not in AUDIO_KINDS:
        return jsonify({"ok": False, "error": "no such audio"}), 404
    bundle = show["act"].get("bundle", {}) if show["act"] else {}
    path = None
    if kind == "set":
        path = bundle.get("set_audio")
    else:
        path = (bundle.get("stings", {}).get(kind, {}) or {}).get("path")
    if not path:
        return jsonify({"ok": False, "error": "no audio for this act"}), 404
    try:
        return send_file(path)
    except OSError:
        return jsonify({"ok": False, "error": "audio unreadable"}), 404


@show_bp.route("/api/show/<code>/laugh", methods=["POST"])
def laugh(code):
    """The laugh track: buttons and agents post here. Anonymous device ids
    (one per phone; agents use seat names), like funnier's /laughs."""
    show = SHOWS.get((code or "").upper())
    if not show:
        return jsonify({"ok": False, "error": "no such show"}), 404
    data = request.json or {}
    rtype = str(data.get("type", "haha"))[:12]
    if rtype not in REACT_W:
        return jsonify({"ok": False, "error": "unknown laugh type"}), 400
    try:
        ms = int(data.get("ms", 0))
    except (TypeError, ValueError):
        ms = 0
    device = str(data.get("device", ""))[:40]
    with LOCK:
        if show["phase"] not in ("SET", "INTERVIEW"):
            return jsonify({"ok": False, "error": "not performing"}), 400
        show["act"]["laughs"].append({"ms": ms, "type": rtype,
                                      "device": device, "at": _now()})
        n = len(show["act"]["laughs"])
        _save()
        return jsonify({"ok": True, "laughs": n})


@show_bp.route("/api/show/<code>/interview", methods=["POST"])
def interview(code):
    show = SHOWS.get((code or "").upper())
    if not show:
        return jsonify({"ok": False, "error": "no such show"}), 404
    with LOCK:
        if show["phase"] != "INTERVIEW":
            return jsonify({"ok": False, "error": "not interview time"}), 400
        exchanges = len(show["act"]["interview"]) // 2
        if exchanges >= INTERVIEW_TURNS:
            return jsonify({"ok": False, "error": "interview done — advance"}), 400
        return jsonify({"ok": True, "exchange": interview_turn(show)})
