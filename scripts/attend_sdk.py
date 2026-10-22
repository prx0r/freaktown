#!/usr/bin/env python3
"""Attend SDK: agents go to shows. Import it, don't shell out to scripts.

    from scripts.attend_sdk import attend
    report = attend("biscuit-4cb995", persona="skeptic", cond="sdk-demo")

One call: pulls heat, judges every beat with mimo (mechanism x confidence),
laughs through the delay harness (human-timed, contagion-aware), posts via
the same buttons humans tap, and returns a report with heat agreement and
the room verdict comparison. Reuses agent_audience / agent_laugh /
interpret_joke / evaluate_performance — this file is the front door.

Honest limits (same as the parts): no ears (reads text+timings, never
audio), no eyes (never sees the avatar), can't hear the crowd bed.
"""
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from agent_audience import api, decide  # noqa: E402
from agent_laugh import plan_laugh  # noqa: E402
from interpret_joke import interpret_joke  # noqa: E402


def attend(slug, persona="normal", cond="sdk", base="http://127.0.0.1:8090",
           fast=True, max_beats=0):
    """Attend a full set. Returns a report dict."""
    heat = api(base, f"/api/perform/{slug}/heat")
    if not heat.get("ok"):
        return {"ok": False, "error": "no heat"}
    beats = heat["beats"][:max_beats] if max_beats else heat["beats"]
    earlier, room, laughs = [], [], {"haha": 0, "hahaha": 0}
    agreed, judged = 0, 0
    t0 = time.time()
    for i, b in enumerate(beats):
        try:
            ev = interpret_joke(b["text"], earlier_context="\n".join(earlier[-3:]),
                                beat_id=f"{slug}#{i}",
                                session="funnier-attend-sdk")
        except Exception as e:
            earlier.append("")
            continue
        earlier.append(f"{ev.get('setup', '')} -> {ev.get('reveal', '')}")
        conf = float(ev.get("confidence_in_interpretation", 0))
        hp = float(b.get("p_laugh", 0))
        now = b["end"] if fast else int((time.time() - t0) * 1000)
        plan = plan_laugh(b, conf, hp, room, now, seed=f"{slug}#{i}")
        types, _ = decide(ev, hp + plan["contagion_boost"], persona=persona)
        laughed = bool(types)
        judged += 1
        if (hp >= 0.4) == laughed:
            agreed += 1
        for rtype, off in types:
            at = plan["react_at_ms"] + off
            api(base, "/api/react",
                {"slug": slug, "type": rtype, "set_time_ms": at,
                 "cond": cond})
            room.append(at)
            laughs[rtype] += 1
    with urllib.request.urlopen(base + f"/api/perform/{slug}/verdict",
                                timeout=30) as r:
        import json
        verdict = json.loads(r.read().decode())
    return {"ok": True, "slug": slug, "persona": persona, "cond": cond,
            "beats": len(beats), "laughs": laughs,
            "heat_agreement": round(agreed / max(1, judged), 2),
            "verdict": {k: verdict.get(k) for k in
                        ("killed", "energy", "coverage", "creators")}}


if __name__ == "__main__":
    import json
    slug = sys.argv[1] if len(sys.argv) > 1 else "biscuit-4cb995"
    print(json.dumps(attend(slug, cond="sdk-demo"), indent=1))
