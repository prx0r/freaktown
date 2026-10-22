#!/usr/bin/env python3
"""Party agent SDK: TableCraft-style agentRules + player SDK for FUNNIER party.

ADDITIVE ONLY: new file, no rewrites. Game truth stays in party.py;
this is a front door for agents (and solo humans) to play every mode
with the same HTTP contract phones use.

    from scripts.party_agent_sdk import PartyAgent, AGENT_RULES, solo_night
    agent = PartyAgent(base="http://127.0.0.1:8090")
    agent.join(code, "Ralph-AI")
    print(agent.state(code))   # redacted view: what YOUR seat may see
    agent.act_guess(code, "pigeon")

Providers (bots become providers, same interface):
  - DeckProvider ($0 default): seeded deck lines/guesses/votes. CI-safe.
  - JevEyesProvider (ask-first spend ~$0.0001/call): typesafe/jev-1.14 via
    OpenRouter Decisions API (Noul/Choice/Score/Box). OPENROUTER_API_KEY is
    Jev-ONLY per owner rule. Uses: freaktionary drawing -> Box(where)+
    Noul(is it X?), stone-face smile -> Noul(cracked?), vote choice.
  - FishVoiceProvider ($0): Fish s2.1-pro-free (same TTS endpoint, model
    header only, fair-use, no TTFA/DPA guarantees). Speaks lines on request.
    Room never waits for audio — text reveal is the game, audio is garnish.

TableCraft lesson applied: every mode ships machine-readable agentRules
so any LLM knows exactly what actions are legal. GAOS lesson applied:
server is authoritative; illegal/late replies never wedge a match
(server returns ok:false, room keeps moving).
"""
from __future__ import annotations

import base64
import json
import os
import random
import urllib.request
from pathlib import Path

# ── agentRules (machine-readable, per mode) ──────────────────────────

AGENT_RULES = {
    "freaktionary": {
        "roles": ["drawer", "guesser"],
        "legal": ["draw.batch(points[[x,y] 0..1, <=200])", "guess(text<=60)"],
        "secrets": "drawer word ONLY via GET /party/<code>/view (your seat); never on SSE stream",
        "win": "guesser +2, drawer +1 on correct guess; timeout reveals, no points",
        "solo": "bots guess from word-list+decoys (seeded); bot drawer lays simple strokes",
    },
    "roast-relay": {
        "roles": ["author", "voter"],
        "legal": ["line(text<=180)", "vote(choice index, no self-vote)"],
        "secrets": "none (all lines public at reveal); votes anonymous-count only",
        "win": "most votes +3",
        "solo": "bots author from RR_BOT_LINES deck, vote seeded no-self-vote",
    },
    "freeze-night": {
        "roles": ["contestant", "voter"],
        "legal": ["entry(text)", "vote(choice)", "callback(event-id, x1.5 once/night)"],
        "secrets": "none beyond anonymous entries",
        "win": "vote-% of pool + sweep(25); Last-Lash triple pool(300)",
        "solo": "bots via _fz_bots_act deck",
    },
    "quip-*": {
        "roles": ["author", "voter"],
        "legal": ["entry(text)", "vote(choice[])", "caught-that(event-id)"],
        "twists": "normal (most wins) / inverted (fewest wins) / liar (name the lie)",
        "solo": "bots via _qc_bots_act deck",
    },
    "stone-face": {
        "roles": ["confessor", "holder"],
        "legal": ["info(text<=120)", "crack | smile_detected"],
        "secrets": "infos public at assemble; cracks public with source",
        "win": "survivors +3",
        "solo": "bots confess deck + 0.35 crack/line; Jev Noul(cracked?) upgrade path",
        "eyes": "jev-1.14 Noul smile check (opt-in, 3s cooldown, never scored, boolean only)",
    },
    "poker": {
        "roles": ["bettor"],
        "legal": ["check | call | bet | fold (actor only, fixed-limit 2/4, 3-raise cap)"],
        "secrets": "hole cards ONLY via /view (your seat); board/pot/actor public",
        "win": "side pots, split ties, pot conserved",
        "solo": "bots play pot-odds + ~10% bluffs via _pk_drive",
    },
}

JEV_MODEL = "typesafe/jev-1.14"
JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
FISH_ENDPOINT = "https://api.fish.audio/v1/tts"


def _api(base, path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


class PartyAgent:
    """One agent seat. Same HTTP contract as a phone. Server is truth."""

    def __init__(self, base="http://127.0.0.1:8090", name="Agent-1"):
        self.base = base.rstrip("/")
        self.name = name
        self.code = None
        self.token = None
        self.pid = None

    def join(self, code, freak=None):
        self.code = code.upper()
        r = _api(self.base, f"/party/{self.code}/join",
                 {"name": self.name, "freak": freak or self.name})
        self.token = r.get("token")
        self.pid = r.get("player_id")
        return r

    def state(self, code=None):
        """Redacted view: what YOUR seat may legitimately see."""
        code = (code or self.code or "").upper()
        return _api(self.base, f"/party/{code}/view",
                     {"token": self.token} if self.token else {})

    def rules(self, mode):
        key = mode if mode in AGENT_RULES else (
            "quip-*" if str(mode).startswith("quip-") else mode)
        return AGENT_RULES.get(key, {})

    # ── legal actions (server validates; illegal returns ok:false, never wedges)
    def act(self, code, kind, **kw):
        code = (code or self.code or "").upper()
        return _api(self.base, f"/party/{code}/input",
                     {"token": self.token, "kind": kind, **kw})

    def act_guess(self, code, text):
        return self.act(code, "guess", text=text)

    def act_line(self, code, text):
        return self.act(code, "line", text=text)

    def act_vote(self, code, choice):
        return self.act(code, "vote", choice=choice)

    def act_draw(self, code, points):
        return self.act(code, "draw.batch", points=points)


# ── Jev-1.14 eyes (OPTIONAL, ask-first spend) ─────────────────────────
# Same contract as scripts/agent_eyes.py: screenshot/PNG -> Decisions API
# -> typed Noul/Choice/Box. OPENROUTER_API_KEY is Jev-ONLY per owner rule.

def jev_ask(png_path, questions, key=None):
    """Ask Jev-1.14 typed questions about a PNG. Returns answers dict."""
    key = key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("REFUSING: OPENROUTER_API_KEY missing (Jev-only key).")
    img = base64.b64encode(Path(png_path).read_bytes()).decode()
    body = json.dumps({
        "model": JEV_MODEL,
        "state": ["Party screenshot:",
                  {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{img}"}}],
        "questions": questions}).encode()
    req = urllib.request.Request(
        JEV_ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://funnier.si/",
                 "X-Title": "funnier-party-agent-sdk"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def jev_smile_check(png_path, key=None):
    """Stone-face upgrade path: Noul cracked? Boolean only, caller enforces
    3s cooldown + opt-in + never-scored (same privacy as smile-referee.js)."""
    d = jev_ask(png_path, {"cracked": {
        "type": "noul",
        "instructions": "Is the person smiling or laughing (teeth or upturned mouth)?"}},
        key=key)
    try:
        return float(d["answers"]["cracked"]["noul"])
    except Exception:
        return 0.0


def jev_where(png_path, description, key=None):
    """Freaktionary upgrade path: Box(where is X?) + Noul(is it there?).
    Always pair Box with Noul — Box always returns a box, never 'not found'."""
    d = jev_ask(png_path, {
        "present": {"type": "noul",
                    "instructions": f"Is {description} visible in the drawing?"},
        "where": {"type": "box", "instructions": description}}, key=key)
    a = d.get("answers", {})
    box = (a.get("where") or {}).get("box")
    noul = float((a.get("present") or {}).get("noul", 0.0))
    return {"present_p": noul, "box": box, "model": d.get("model")}


# ── Fish voice ($0 s2.1-pro-free) ─────────────────────────────────────
# Same TTS endpoint as paid s2.1-pro; select free tier with model header.
# Fair-use, no TTFA/DPA guarantees. Room never waits — text is the game.

def fish_speak(text, out_path="/tmp/party_line.mp3", key=None,
               voice_id=None, model="s2.1-pro-free"):
    """Speak one line via Fish free tier. Returns out_path or raises."""
    key = key or os.environ.get("FISH_API_KEY", "")
    if not key:
        raise RuntimeError("FISH_API_KEY missing (free tier still needs a key).")
    body = json.dumps({"text": text[:600],
                        "format": "mp3",
                        **({"reference_id": voice_id} if voice_id else {})}).encode()
    req = urllib.request.Request(
        FISH_ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "model": model})
    with urllib.request.urlopen(req, timeout=60) as r:
        Path(out_path).write_bytes(r.read())
    return out_path


# ── solo helper (1 human + N agents, any mode) ────────────────────────

def solo_night(mode, nbots=3, base="http://127.0.0.1:8090",
               deck=None, target="the host's air fryer obsession"):
    """Create room, lock, seat bots, start. Returns (code, host_token).
    Pure HTTP, same path as test_allbots.sim_night. $0 deck bots."""
    r = _api(base, "/party/create")
    code, ht = r["code"], r["host_token"]
    _api(base, f"/party/{code}/host", {"host_token": ht, "cmd": "lock"})
    kw = {"deck": deck} if deck else {}
    _api(base, f"/party/{code}/host",
         {"host_token": ht, "cmd": "bots", "n": nbots})
    kw2 = dict(kw)
    if mode.startswith("quip-"):
        kw2["deck"] = deck or mode.split("quip-", 1)[1]
    if mode == "roast-relay":
        kw2["target"] = target
    r = _api(base, f"/party/{code}/host",
             {"host_token": ht, "cmd": "start", "mode": mode, **kw2})
    assert r.get("ok"), r
    return code, ht


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "roast-relay"
    code, _ = solo_night(mode)
    print(json.dumps({"ok": True, "mode": mode, "code": code,
                      "rules": AGENT_RULES.get(mode, AGENT_RULES.get("quip-*")),
                      "join": f"/join/{code}"}, indent=1))
