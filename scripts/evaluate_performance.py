#!/usr/bin/env python3
"""Agent critic: evaluate a live performance package and score a report card.

What an agent CAN judge (all server-side, no browser needed):
  delivery  — heat curve shape (rise to payoff? dead stretches?)
  acting    — acting-timeline richness (expressions/gestures/holds/cameras)
  mouth     — viseme driver served (v0/v1 branch present in room HTML)
  crowd     — bed moments + verdict stats from the log
  observed  — reactions on record (any cond), heat-vs-taps agreement

What it CANNOT judge: whether the mouth LOOKS right (needs eyes), whether
jokes are funny (that's the audience job). Scores 0-10 per axis, stated
rules, printed reasoning. Honest limits in output.

Usage: /usr/bin/python3 scripts/evaluate_performance.py <slug> [--base URL]
"""
import argparse
import json
import sys
import urllib.request

WEIGHTS = {"hahaha": 2.0, "haha": 1.0, "laugh": 1.0, "smile": 1.0,
           "cheer": 0.5, "clap": 0.5, "boo": -1.0}


def get(base, path, raw=False):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        body = r.read()
        return (r.status, body if raw else body.decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    args = ap.parse_args()
    base, slug = args.base, args.slug
    card, notes = {}, []

    s, room = get(base, f"/perform/{slug}")
    card["served"] = s == 200
    if s != 200:
        print(json.dumps({"ok": False, "error": f"room {s}"}))
        return 1
    s, room0 = get(base, f"/perform/{slug}?mouth=v0")
    card["ab_arms"] = (s == 200 and "const MOUTH = 'v0'" in room0
                       and "const MOUTH = 'v1'" in room)
    notes.append("v0+v1 arms served" if card["ab_arms"] else "MISSING an arm")

    import re as _re
    found = sorted(set(_re.findall(r"setValue\('([a-z]+)'", room)))
    visemes = [v for v in ("aa", "ih", "oh", "ou", "ee") if v in found]
    card["mouth"] = min(10, len(visemes) * 2 + (2 if "const MOUTH = 'v1'" in room else 0))
    notes.append(f"viseme shapes driven: {visemes or 'none'} "
                 "(browser-rendered, eyes needed for looks)")

    heat = json.loads(get(base, f"/api/perform/{slug}/heat")[1])
    beats = heat.get("beats", []) if heat.get("ok") else []
    ps = [b["p_laugh"] for b in beats]
    if ps:
        rise = ps[-1] - ps[0]
        dead = sum(1 for p in ps if p < 0.2) / len(ps)
        card["delivery"] = round(max(0, min(10, 5 + rise * 12 - dead * 6)), 1)
        notes.append(f"heat {ps[0]:.2f}->{ps[-1]:.2f}, dead {dead:.0%}, "
                     f"srcs {heat.get('models')}")
    else:
        card["delivery"] = 0
        notes.append("no beats")

    acting = json.loads(get(base, f"/api/perform/{slug}/acting")[1])
    evs = acting.get("events", []) if acting.get("ok") else []
    kinds = {}
    for e in evs:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    card["acting"] = min(10, len(kinds) * 2 + min(2, len(evs) // max(1, len(beats))))
    notes.append(f"acting kinds: {kinds or 'none'}")

    s, bed = get(base, f"/api/perform/{slug}/crowd.wav", raw=True)
    card["crowd"] = 10 if (s == 200 and bed[:4] == b"RIFF" and len(bed) > 100000) else 0
    notes.append(f"bed {len(bed)//1024}KB" if card["crowd"] else "bed MISSING")

    verdict = json.loads(get(base, f"/api/perform/{slug}/verdict")[1])
    card["observed"] = 0
    if verdict.get("ok"):
        card["observed"] = min(10, int(verdict["energy"] // 2) + int(verdict["coverage"] * 4))
        notes.append(f"verdict: killed={verdict['killed']} energy={verdict['energy']} "
                     f"cov={verdict['coverage']} crowd={verdict['creators']}")
    card["total"] = round(sum([card["mouth"], card["delivery"],
                               card["acting"], card["crowd"],
                               card["observed"]]) / 5, 1)
    print(json.dumps({"ok": True, "slug": slug, "card": card, "notes": notes},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
