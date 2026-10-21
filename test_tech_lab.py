#!/usr/bin/env python3
"""Tech-lab checks: rig pages serve, prop validator accepts/rejects.
Run: python3 test_tech_lab.py (script, never pytest).
"""

import json

from app import app

c = app.test_client()
N = {"pass": 0, "fail": 0}


def check(name, cond):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name)


for path, needle in [
    ("/party/lab", "TEST THE TECH"),
    ("/party/lab/smile", "SmileReferee.calibrate"),
    ("/party/lab/voice", "/api/tts"),
    ("/party/lab/props", "/party/prop/validate"),
    ("/party/lab/jev", "jev-preview"),
]:
    r = c.get(path)
    check(f"{path} serves", r.status_code == 200 and needle.encode() in r.data)

good = {"version": "prop_job.v1", "prompt": "peanut",
        "primitives": [{"op": "uv_sphere", "material": "shell"}],
        "materials": {"shell": {"base": "#c89b6a"}}, "style": "anime"}
r = json.loads(c.post("/party/prop/validate", json=good).data)
check("valid manifest accepted", r.get("ok") is True)

bad = dict(good, primitives=[{"op": "execute_blender_code",
                              "material": "shell"}])
r = json.loads(c.post("/party/prop/validate", json=bad).data)
check("rogue op rejected",
      r.get("ok") is False and any("uv_sphere" in e or "not in" in e
                                   for e in r.get("errors", [])))

bad2 = dict(good, style="pixar")
r = json.loads(c.post("/party/prop/validate", json=bad2).data)
check("unknown style rejected", r.get("ok") is False)

r = json.loads(c.post("/party/prop/validate", json={}).data)
check("empty manifest rejected", r.get("ok") is False)

r = c.get("/static/smile-referee.js")
check("smile module serves", r.status_code == 200 and b"SmileReferee" in r.data)

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
