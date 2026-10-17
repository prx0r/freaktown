#!/usr/bin/env python3
"""Trial live minutes: play full sets through the LIVE server end to end.

For each slug: bill lists it -> room loads with all components -> heat +
acting + bed fetch -> set.wav + bed download and are real audio -> entrance
-> paced reactions -> finale. Reports timings + failures. No mocks.

Usage: /usr/bin/python3 scripts/trial_minutes.py [slug ...] [--base URL]
"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8090"
SLUGS = ["cathy-prior-f3ac25", "biscuit-4cb995", "chris-prior-72abda"]


def get(path, raw=False):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        body = r.read()
        return body if raw else (r.status, body.decode())


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def trial(slug):
    t0 = time.time()
    out = {"slug": slug, "ok": True, "notes": []}
    try:
        s, bill = get("/perform")
        assert s == 200 and slug in bill, "bill missing slug"
        s, room = get(f"/perform/{slug}")
        assert s == 200, "room"
        for marker in ["showtimeBtn", "crowdbar", "heatstrip", "pf-hold",
                       "smileToggle", "appearBtn", "crowd.wav", "__vrmFace",
                       "const MOUTH = 'v1'"]:
            assert marker in room, f"room missing {marker}"
        s, room0 = get(f"/perform/{slug}?mouth=v0")
        assert s == 200 and "const MOUTH = 'v0'" in room0, "v0 arm"
        heat = json.loads(get(f"/api/perform/{slug}/heat")[1])
        assert heat.get("ok") and heat["beats"], "heat"
        acting = json.loads(get(f"/api/perform/{slug}/acting")[1])
        assert acting.get("ok") and acting["events"], "acting"
        wav = get(f"/freaks/{slug}/set.wav", raw=True)
        assert wav[:4] == b"RIFF" and len(wav) > 100000, "set audio"
        bed = get(f"/api/perform/{slug}/crowd.wav", raw=True)
        assert bed[:4] == b"RIFF", "bed audio"
        # entrance -> watch -> react arc (paced, one tap per beat-third)
        r = post("/api/react", {"slug": slug, "type": "cheer",
                                "set_time_ms": 0, "cond": "trial"})
        assert r.get("ok"), "entrance cheer"
        n = len(heat["beats"])
        for i in range(0, n, 3):
            post("/api/react", {"slug": slug, "type": "haha",
                                "set_time_ms": heat["beats"][i]["start"],
                                "cond": "trial"})
            time.sleep(0.2)
        post("/api/react", {"slug": slug, "type": "hahaha",
                            "set_time_ms": heat["beats"][-1]["start"],
                            "cond": "trial"})
        out["beats"] = n
        out["set_kb"] = len(wav) // 1024
        out["bed_kb"] = len(bed) // 1024
    except Exception as e:
        out["ok"] = False
        out["notes"].append(str(e)[:200])
    out["secs"] = round(time.time() - t0, 1)
    return out


def main():
    slugs = [a for a in sys.argv[1:] if not a.startswith("--")] or SLUGS
    global BASE
    for a in sys.argv[1:]:
        if a.startswith("--base="):
            BASE = a.split("=", 1)[1]
    results = [trial(s) for s in slugs]
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'} {r['slug']}: "
              f"{r.get('beats', 0)} beats, set {r.get('set_kb', 0)}KB, "
              f"bed {r.get('bed_kb', 0)}KB, {r['secs']}s {r['notes']}")
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
