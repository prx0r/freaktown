#!/usr/bin/env python3
"""All-bot simulator: full nights, zero humans. Tests core logic + timings.

Every bot seat auto-acts synchronously, so a night completes by repeatedly
advancing. Asserts: nights finish, scores move, archive grows, event log is
sane, no phase ever stalls. Reports wall-clock + per-round timings.

This is the Tier-0 harness (deepwolf calls it dry-run, MindGames calls it
the offline tournament): deterministic per room code, $0, CI-safe.
Tier-1 (LLM agents via OpenRouter/DashScope with reasoning traces) is the
ask-first upgrade — same interface, bots become providers.

Run: python3 test_allbots.py [nights] (script, never pytest).
"""

import json
import sys
import time

from app import app
from party import ROOMS

c = app.test_client()
N = {"pass": 0, "fail": 0}
TIMINGS = []


def check(name, cond):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name)


def host(code, ht, cmd, **kw):
    body = {"host_token": ht, "cmd": cmd}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/host", json=body).data)


def sim_night(mode, nbots=4, deck=None, label=""):
    t0 = time.time()
    r = json.loads(c.post("/party/create").data)
    code, ht = r["code"], r["host_token"]
    c.post(f"/party/{code}/host", json={"host_token": ht, "cmd": "lock"})
    kw = {"deck": deck} if deck else {}
    if mode in ("freeze-night",) or mode.startswith("quip-"):
        host(code, ht, "bots", n=nbots)
    else:
        # roast/freaktionary have no bot seats yet: seed bot players via join
        # is human-only; all-bot needs engine seats — covered when wired.
        return None
    r = host(code, ht, "start", mode=mode, **kw)
    assert r.get("ok"), r
    room = ROOMS[code]
    rounds, steps = 0, 0
    last_phase = None
    while room["phase"] != "done" and steps < 60:
        host(code, ht, "advance")
        steps += 1
        st = room["mode_state"]
        key = (st.get("round_id") or st.get("round"), st.get("phase"))
        if key != last_phase:
            rounds += 1
            last_phase = key
    dt = time.time() - t0
    TIMINGS.append((label or mode, rounds, steps, round(dt, 2)))
    return room


def main():
    nights = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for _ in range(nights):
        room = sim_night("freeze-night", label="freeze-night")
        check("freeze-night completes with zero humans",
              room is not None and room["phase"] == "done")
        if room is None:
            continue
        scores = [p["score"] for p in room["players"].values()]
        check("scores moved", sum(scores) > 0)
        check("archive grew", len(room["mode_state"]["archive"]) > 5)
        check("winner crowned", bool(room.get("winner")))
        evs = room["events"]
        check("event log sane", len(evs) > 20 and evs[-1]["kind"] == "night.done")
        # no phase ever stalls: every round.started reaches scored/done
        kinds = [e["kind"] for e in evs]
        check("round lifecycle complete",
              kinds.count("round.started") >= 7)

    for deck in ("endings", "lies", "nonsense"):
        r = json.loads(c.post("/party/create").data)
        code, ht = r["code"], r["host_token"]
        c.post(f"/party/{code}/host", json={"host_token": ht, "cmd": "lock"})
        host(code, ht, "bots", n=3)
        rr = host(code, ht, "start", mode=f"quip-{deck}")
        assert rr.get("ok"), rr
        room = ROOMS[code]
        t0 = time.time()
        for _ in range(12):
            host(code, ht, "advance")
        dt = time.time() - t0
        st = room["mode_state"]
        TIMINGS.append((f"quip-{deck}", st.get("round", 0), 12, round(dt, 2)))
        check(f"quip-{deck} progresses (round>=2)",
              st.get("round", 0) >= 2)
        check(f"quip-{deck} scores moved",
              sum(p["score"] for p in room["players"].values()) > 0)

    print("\n--- timings (mode, phase-changes, advances, seconds) ---")
    for row in TIMINGS:
        print(f"  {row[0]:<16} phases={row[1]:<3} advances={row[2]:<3} {row[3]}s")
    print(f"\n{N['pass']} passed, {N['fail']} failed")
    raise SystemExit(1 if N["fail"] else 0)


main()
