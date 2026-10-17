#!/usr/bin/env python3
"""Agent-native audience member: listens to a /perform set and reacts.

How an agent "listens" (honest version — no ears, no mic):
  1. Pull the set's beats + heat timeline (what plays, when, predicted heat).
  2. Read each beat's text as it "plays" (paced by real timings in
     --realtime, instantly in --fast).
  3. Judge it with the mimo semantic interpreter (mechanism + confidence)
     combined with the delivery heat p.
  4. Post laugh reactions (/api/react) with the true set_time_ms, like a
     phone in the crowd. Reasoning is printed, never hidden.

Laugh rule (stated, tunable): a beat earns haha when the interpreter finds
a real mechanism (not not_a_joke) with confidence >= 0.7 AND heat >= 0.3;
HAHAHA when confidence >= 0.85 AND heat >= 0.45. Otherwise silence. The
agent's taste is therefore: mechanism x delivery, nothing else.

Usage:
  /usr/bin/python3 scripts/agent_audience.py <slug> [--fast] [--cond NAME] [--base URL]
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from interpret_joke import interpret_joke  # noqa: E402 (Go/mimo, own key)
from agent_laugh import plan_laugh, laugh_types  # noqa: E402 (delay harness)


def api(base, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def decide(ev, heat, persona="normal"):
    mechs = set(ev.get("mechanism", []))
    conf = float(ev.get("confidence_in_interpretation", 0))
    if "not_a_joke" in mechs:
        return [], f"not a joke ({conf:.2f})"
    return laugh_types(conf, heat, persona=persona), \
        f"{sorted(mechs)} @ {conf:.2f} + heat {heat:.2f}"


def run_heatsheep(args, beats):
    """Simulated average human: taps each beat with P(heat), delayed like a
    human (same harness), no judge calls. The honest 'what would the room
    do' baseline — same buttons, same stamps, no understanding."""
    import hashlib
    import random
    from agent_laugh import BURST_GAP_MS
    laughs = {"haha": 0, "hahaha": 0, "cheer": 0, "boo": 0}
    for i, b in enumerate(beats):
        heat = float(b.get("p_laugh", 0))
        # NOTE: seed excludes cond on purpose — a text agent cannot hear
        # the bed, so both arms MUST tap identically (negative control).
        rng = random.Random(int(hashlib.sha256(
            f"{args.slug}#{i}".encode()).hexdigest()[:16], 16))
        r = rng.random()
        if r < heat * 0.9:
            rtype = "hahaha" if r < heat * 0.25 else "haha"
        elif r < heat + 0.04:
            rtype = "cheer"
        elif rng.random() < 0.02:
            rtype = "boo"
        else:
            continue
        delay = 250 + rng.uniform(-60, 120) + (1.0 - heat) * 400
        at = b["end"] + int(delay)
        api(args.base, "/api/react",
            {"slug": args.slug, "type": rtype,
             "set_time_ms": at, "cond": args.cond})
        laughs[rtype] += 1
        if rtype == "hahaha":
            api(args.base, "/api/react",
                {"slug": args.slug, "type": "hahaha",
                 "set_time_ms": at + BURST_GAP_MS, "cond": args.cond})
            laughs["hahaha"] += 1
    print(f"night over: {laughs} (cond={args.cond}, heatsheep)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--fast", action="store_true",
                    help="judge instantly instead of pacing the set clock")
    ap.add_argument("--cond", default="agent",
                    help="A/B condition label logged with reactions")
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--max-beats", type=int, default=0)
    ap.add_argument("--persona", default="normal",
                    choices=["normal", "easy", "skeptic", "heatsheep"],
                    help="taste. heatsheep = simulated average human: taps "
                         "with P(heat), no judge calls, same buttons")
    args = ap.parse_args()

    heat = api(args.base, f"/api/perform/{args.slug}/heat")
    if not heat.get("ok"):
        print("no heat for slug")
        return 1
    beats = heat["beats"]
    if args.max_beats:
        beats = beats[:args.max_beats]
    print(f"agent in seat for {args.slug}: {len(beats)} beats "
          f"({'fast' if args.fast else 'realtime'}, cond={args.cond}, "
          f"persona={args.persona})")
    if args.persona == "heatsheep":
        return run_heatsheep(args, beats)
    prior = []
    laughs = {"haha": 0, "hahaha": 0}
    room_laughs_ms = []  # laughs the agent has "heard" (own posts for now;
    # multi-agent rooms share warmth via a future reactions feed)
    t0 = time.time()
    set_t0 = None
    for i, b in enumerate(beats):
        if not args.fast and i:
            dt = (b["start"] - beats[i - 1]["start"]) / 1000.0
            elapsed = time.time() - t0
            if dt > elapsed:
                time.sleep(min(dt - elapsed, 30))
        try:
            ev = interpret_joke(b["text"], prior_context="\n".join(prior[-3:]),
                                beat_id=f"{args.slug}#{i}",
                                session="freaktown-agent-audience")
        except Exception as e:
            print(f"  [{i}] judge failed: {e}")
            continue
        prior.append(f"[{i}] {ev.get('setup', '')} → {ev.get('reveal', '')}")
        conf = float(ev.get("confidence_in_interpretation", 0))
        heat = float(b.get("p_laugh", 0))
        now_ms = int((time.time() - t0) * 1000) if not args.fast else b["end"]
        if set_t0 is None:
            set_t0 = now_ms - b["start"] if not args.fast else 0
        plan = plan_laugh(b, conf, heat, room_laughs_ms, now_ms - set_t0,
                          seed=f"{args.slug}#{i}")
        types, why = decide(ev, heat + plan["contagion_boost"],
                            persona=args.persona)
        stamp = plan["react_at_ms"]
        tag = (f"onset +{stamp - b['end']}ms"
               f"{' WARM' if plan['warm'] else ''}")
        print(f"  [{i}] t={b['start']}ms heat={heat:.2f} -> "
              f"{[t for t, _ in types] or '...'} ({why} | {tag})")
        for rtype, off in types:
            at = stamp + off
            if not args.fast:
                wait = max(0.0, (set_t0 + at - (time.time() - t0) * 1000) / 1000.0)
                if wait > 0:
                    time.sleep(min(wait, 30))
            api(args.base, "/api/react",
                {"slug": args.slug, "type": rtype,
                 "set_time_ms": at, "cond": args.cond})
            room_laughs_ms.append(at)
            laughs[rtype] += 1
    print(f"night over: {laughs} (cond={args.cond})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
