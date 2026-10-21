"""Cauldron show runtime. Run: python3 test_show.py (no network, $0)."""
import json
import tempfile
from pathlib import Path

import cauldron_show as showmod
from app import app

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL", name)


tmp = Path(tempfile.mkdtemp())
showmod.STATE_FILE = tmp / "show_rooms.json"
showmod.SHOWS.clear()
c = app.test_client()

# 1. performers link (characters2)
r = c.get("/api/show/performers")
d = r.get_json()
check("performers 200 + list", r.status_code == 200 and isinstance(d.get("performers"), list))
slugs = [p["slug"] for p in d["performers"]]
check("ralph ready", "reptilian-ralph-middle-management" in slugs)
ralph = next(p for p in d["performers"] if p["slug"] == "reptilian-ralph-middle-management")
check("ralph has beats", ralph["beats"] > 0)

# 2. create (rejects empties/unknowns)
r = c.post("/api/show/create", json={"performers": []})
check("empty bill 400", r.status_code == 400)
r = c.post("/api/show/create", json={"performers": ["no-such-act"]})
check("unknown slug 400", r.status_code == 400)
r = c.post("/api/show/create", json={"performers": ["reptilian-ralph-middle-management"],
                                     "venue": "cauldron"})
d = r.get_json()
check("create ok", r.status_code == 200 and d.get("ok") and d.get("code"))
code, host = d["code"], d["host_token"]

# 3. full phase walk: GREEN_ROOM -> INTRO -> SET -> INTERVIEW -> VERDICT -> ENDED
r = c.post(f"/api/show/{code}/start")
check("start -> INTRO", r.get_json().get("phase") == "INTRO")
d = r.get_json()
check("intro carries entrance + beats", bool(d["act"].get("beats")) and isinstance(d["act"].get("entrance"), dict))
check("intro sting urls present-or-null", "sting_urls" in d["act"])

# laughs rejected outside SET/INTERVIEW
r = c.post(f"/api/show/{code}/laugh", json={"type": "haha", "ms": 100, "device": "p1"})
check("laugh in INTRO rejected", r.status_code == 400)

r = c.post(f"/api/show/{code}/advance", json={"host_token": "wrong"})
check("advance without host token 403", r.status_code == 403)
r = c.post(f"/api/show/{code}/advance", json={"host_token": host})
check("advance -> SET", r.get_json().get("phase") == "SET")
r = c.post(f"/api/show/{code}/laugh", json={"type": "nope", "ms": 1, "device": "p1"})
check("unknown laugh type 400", r.status_code == 400)

# laugh track: energy + coverage + creators + a boo (dry, no network)
beats = d["act"]["beats"]
n = max(1, len(beats))
for i in range(n * 2):
    c.post(f"/api/show/{code}/laugh",
           json={"type": "haha", "ms": i * (60000 // max(1, n)), "device": f"p{i % 4}"})
c.post(f"/api/show/{code}/laugh", json={"type": "hahaha", "ms": 5000, "device": "p0"})
c.post(f"/api/show/{code}/laugh", json={"type": "boo", "ms": 9000, "device": "p1"})
r = c.post(f"/api/show/{code}/advance", json={"host_token": host})
check("advance -> INTERVIEW", r.get_json().get("phase") == "INTERVIEW")

# interview: dry turns, capped
seen_live = False
for i in range(showmod.INTERVIEW_TURNS):
    r = c.post(f"/api/show/{code}/interview", json={})
    d = r.get_json()
    check(f"interview turn {i + 1} ok", r.status_code == 200 and d.get("ok"))
    ex = d.get("exchange", {})
    check(f"turn {i + 1} has q+a", bool(ex.get("q")) and bool(ex.get("a")))
    seen_live = seen_live or ex.get("live", False)
check("dry mode = no live calls (flag off)", seen_live is False)
r = c.post(f"/api/show/{code}/interview", json={})
check("interview over cap rejected", r.status_code == 400)

r = c.post(f"/api/show/{code}/advance", json={"host_token": host})
d = r.get_json()
check("advance -> VERDICT", d.get("phase") == "VERDICT")
v = d["act"].get("verdict", {})
check("verdict has crowd math", v.get("energy", 0) > 0 and v.get("creators", 0) >= 3)
check("verdict sting picked", v.get("sting") in ("win", "loss"))
check("judge pending when flag off", v.get("judge", {}).get("status") == "pending")

r = c.post(f"/api/show/{code}/advance", json={"host_token": host})
check("single-act show ends", r.get_json().get("phase") == "ENDED")
r = c.post(f"/api/show/{code}/advance", json={"host_token": host})
check("advance after ENDED 400", r.status_code == 400)

# 4. audio tolerance: ralph set.wav is a stub, stings absent on this box
r = c.get(f"/api/show/{code}/audio/set")
d = c.get(f"/api/show/{code}").get_json()
check("stub set flagged + 404 audio", d["act"].get("set_stub") is True and r.status_code == 404)
r = c.get(f"/api/show/{code}/audio/walkout")
check("missing walkout 404 (stage falls back)", r.status_code == 404)

# 5. bad codes
check("unknown show 404", c.get("/api/show/ZZZZ").status_code == 404)
check("audio bad kind 404", c.get(f"/api/show/{code}/audio/bass").status_code == 404)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
