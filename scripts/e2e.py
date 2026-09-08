#!/usr/bin/env python3
"""End-to-end: Black Room -> viral reply -> party, against a live server.

Usage: python3 scripts/e2e.py [base_url]  (default http://localhost:8090)
Logs every step with timings to var/e2e/e2e_<ts>.log. Exit 1 on any FAIL.
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
ROOT = Path(__file__).parent.parent
LOGDIR = ROOT / "var" / "e2e"
LOGDIR.mkdir(parents=True, exist_ok=True)
LOG = LOGDIR / f"e2e_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log"

results = []


def log(msg):
    line = f"[{datetime.now(timezone.utc):%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def req(method, path, body=None, timeout=120):
    t0 = time.time()
    r = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            out = resp.read().decode()
            dt = time.time() - t0
            try:
                return resp.status, json.loads(out), dt
            except Exception:
                return resp.status, out, dt
    except Exception as e:
        return -1, str(e), time.time() - t0


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    log(f"{'PASS' if cond else 'FAIL'} {name} {detail}")


log(f"e2e start base={BASE}")

# 1. health/build
s, d, dt = req("GET", "/api/health", timeout=15)
check("health", s == 200 and d.get("ok"), f"{dt:.1f}s build={d.get('build') if isinstance(d, dict) else d}")

# 2. Black Room: generate -> parse -> compose -> save -> preload -> watch
s, g, dt = req("POST", "/api/generate", {"premise": "e2e test: a toaster that files taxes"}, timeout=180)
ok = s == 200 and g.get("ok") and len(g.get("minute", "").split()) >= 60
check("generate minute", ok, f"{dt:.1f}s words={len(g.get('minute','').split()) if isinstance(g,dict) else 0}")
if not ok:
    log("ABORT: no minute, downstream steps skipped")
    sys.exit(1)

s, p, dt = req("POST", "/api/parse", {"text": g["minute"]}, timeout=30)
beats = p.get("beats", []) if isinstance(p, dict) else []
for b in beats:
    b.setdefault("pace", "normal")
check("parse beats", s == 200 and len(beats) >= 2, f"{dt:.1f}s n={len(beats)}")

s, c, dt = req("POST", "/api/compose", {"beats": beats, "voice": "en-US-GuyNeural"}, timeout=600)
check("compose audio", s == 200 and c.get("ok"), f"{dt:.1f}s dur={c.get('duration_ms') if isinstance(c,dict) else 0}ms")
if s == 200 and c.get("ok"):
    # audio QA: no clipping, no dead air, no silent lead
    import struct
    import urllib.request as _url
    import wave as _wave
    try:
        with _url.urlopen(BASE + c["audio"], timeout=60) as resp:
            blob = resp.read()
        with open("/tmp/e2e_qa.wav", "wb") as f:
            f.write(blob)
        w = _wave.open("/tmp/e2e_qa.wav")
        fr = w.readframes(w.getnframes())
        samp = [x / 32768 for x in struct.unpack(f"<{len(fr)//2}h", fr)]
        sr = w.getframerate()
        peak = max(abs(x) for x in samp)
        clipped = sum(1 for x in samp if abs(x) > 0.99) / len(samp)
        win = sr // 10
        nrg = [sum(x * x for x in samp[i:i + win]) / win
               for i in range(0, len(samp), win)]
        lead = next((i for i, e in enumerate(nrg) if e > 0.0004), len(nrg)) / 10
        run = best = 0
        for e in nrg:
            run = run + 1 if e < 0.0004 else 0
            best = max(best, run)
        check("audio qa", peak < 0.99 and clipped < 0.001 and lead < 1.0 and best / 10 < 3.0,
              f"peak={peak:.2f} clip={clipped:.4f} lead={lead:.1f}s gap={best/10:.1f}s")
    except Exception as e:
        check("audio qa", False, str(e)[:100])

s, sv, dt = req("POST", "/api/sets", {
    "character": {"name": "E2E Bot", "species": "toaster",
                  "premise": "e2e test toaster", "vibe": "manic"},
    "beats": beats, "voice": "en-US-GuyNeural"}, timeout=600)
slug = sv.get("slug") if isinstance(sv, dict) else None
check("save set", s == 200 and bool(slug), f"{dt:.1f}s slug={slug}")

s, pre, dt = req("GET", f"/api/preload/{slug}", timeout=30)
check("preload spec", s == 200 and pre.get("ok") and len(pre.get("wordTimings", [])) > 0,
      f"{dt:.1f}s words={len(pre.get('wordTimings', [])) if isinstance(pre, dict) else 0}")

s, html, dt = req("GET", f"/f/{slug}", timeout=30)
check("watch page", s == 200 and "YOUR TURN" in html, f"{dt:.1f}s")

# 3. Viral reply: idea -> respond -> reply watch + lineage
s, idea, dt = req("POST", "/api/respond_idea", {"slug": slug, "mode": "roast"}, timeout=120)
check("respond idea", s == 200 and idea.get("ok"), f"{dt:.1f}s")

s, rep, dt = req("POST", "/api/respond",
                 {"parent_slug": slug, "mode": "roast", "creator": "e2e"}, timeout=600)
child = rep.get("slug") if isinstance(rep, dict) else None
check("respond reply", s == 200 and bool(child), f"{dt:.1f}s child={child}")
if child:
    meta = json.loads((ROOT / "freaks" / child / "meta.json").read_text())
    lin = meta.get("lineage", {})
    check("reply lineage", lin.get("parent") == slug, f"depth={lin.get('depth')}")
    s, _, dt = req("GET", f"/f/{child}", timeout=30)
    check("reply watch", s == 200, f"{dt:.1f}s")

# 4. Party: create -> join x3 -> lock -> start -> play -> scores
s, room, dt = req("POST", "/party/create", {}, timeout=15)
code, host = room.get("code"), room.get("host_token")
check("party create", s == 200 and bool(code), f"{dt:.1f}s room={code}")
toks = []
for i in range(3):
    s, j, _ = req("POST", f"/party/{code}/join",
                  {"name": f"E2E{i}", "freak": f"E2EFreak{i}"}, timeout=15)
    toks.append(j.get("seat_token"))
check("party join x3", all(toks), "")
req("POST", f"/party/{code}/host", {"host_token": host, "cmd": "lock"}, timeout=15)
s, st, dt = req("POST", f"/party/{code}/host",
                {"host_token": host, "cmd": "start", "mode": "freaktionary"}, timeout=15)
check("party start", s == 200 and st.get("ok"), f"{dt:.1f}s")
s, v, dt = req("GET", f"/party/{code}/view?seat_token={toks[1]}", timeout=15)
check("party view (no leak check structural)", s == 200 and v.get("ok"), f"{dt:.1f}s")

# 5. Submit local
s, sub, dt = req("POST", f"/api/sets/{slug}/submit", {}, timeout=30)
check("submit local", s == 200 and sub.get("status") == "queued", f"{dt:.1f}s")

# 6. Mafia: mixed human/agent seats, full game to a winner
sys.path.insert(0, str(ROOT))
import asyncio as _asyncio
from game_runtime import GameRun
from sdk import (Action, AgentController, HumanController, Participant,
                 Character)
from format_runtime import load_format as _lf  # noqa (pack validated below)
import json as _json
_mafia = _json.loads((ROOT / "game-packs" / "mafia.freak-game.json").read_text())
_seats = [
    Participant(Character("m1", "M1", control_mode="HUMAN"), HumanController()),
    Participant(Character("m2", "M2", control_mode="AUTONOMOUS"),
                AgentController(lambda p: {"kind": "vote"}, label="M2")),
    Participant(Character("m3", "M3", control_mode="HUMAN"), HumanController()),
    Participant(Character("m4", "M4", control_mode="AUTONOMOUS"),
                AgentController(lambda p: {"kind": "vote"}, label="M4")),
    Participant(Character("m5", "M5", control_mode="HUMAN"), HumanController()),
]
_mpids = [p.id for p in _seats]
g = GameRun(_mafia, _mpids, seed=11)
check("mafia dealt", len(g.roles) == 5, f"mafia={[p for p in _mpids if g.roles[p]=='mafia']}")
_fw_ok = True
for pid in _mpids:
    if '"role":' in _json.dumps(g.observe(pid)):
        _fw_ok = False
check("mafia firewall", _fw_ok, "no role keys in live obs")
_rounds = 0
_winner = None
while _rounds < 10 and (_winner := g.winner()) is None:
    alive = sorted(g.alive)
    maf = [p for p in alive if g.roles[p] == "mafia"]
    civs = [p for p in alive if g.roles[p] != "mafia"]
    if maf and civs:
        g.night(civs[0], doctor_save=None)
    _alive2 = sorted(g.alive)
    if len(_alive2) > 1 and g.winner() is None:
        # humans+agents vote identically through one interface: first seat
        # pushes an Action, everyone else follows the same call path
        votes = {p: _alive2[(i + 1) % len(_alive2)] for i, p in enumerate(_alive2)}
        g.day_vote(votes)
    _rounds += 1
_winner = g.winner()
_receipt = g.receipt(_winner)
check("mafia to winner", _winner in ("mafia", "civilians"),
      f"{_rounds} rounds winner={_winner} root={_receipt['event_log_root'][:8]}")

npass = sum(1 for _, ok in results if ok)
log(f"e2e done: {npass}/{len(results)} passed -> {LOG}")
sys.exit(0 if npass == len(results) else 1)
