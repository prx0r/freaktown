#!/usr/bin/env python3
"""Simulated-player tests for stone-face (M1 STONE FACE / #7 TRY NOT TO SMILE).

Covers: min-players gate, confess + resubmit, empty/bad input, auto-assemble
weaving every info, hold screen + CRACKED button, double-crack + early-crack
rejection, host line advance, scoring (survivors +3, crack order), all-crack
shutout, solo-vs-bots completion.

Run: python3 test_stone_face.py (script, never pytest).
"""

import json

from app import app
from party import ROOMS

c = app.test_client()
N = {"pass": 0, "fail": 0}


def check(name, cond):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name)


def new_room():
    r = c.post("/party/create")
    d = json.loads(r.data)
    assert d["ok"]
    return d["code"], d["host_token"]


def join(code, name):
    return json.loads(
        c.post(f"/party/{code}/join", json={"name": name}).data)


def host(code, host_tok, cmd, **kw):
    body = {"host_token": host_tok, "cmd": cmd}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/host", json=body).data)


def inp(code, tok, seq, **kw):
    body = {"seat_token": tok, "client_seq": seq}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/input", json=body).data)


def view(code, tok):
    return json.loads(
        c.get(f"/party/{code}/view",
              query_string={"seat_token": tok}).data)["view"]


def comps(v):
    return [(x.get("type"), x.get("id")) for x in v.get("components", [])]


# ── room 1: full 3-human night ──────────────────────────────────────────
code, ht = new_room()
solo = join(code, "Solo")
check("min players gate (1P start refused)",
      host(code, ht, "start", mode="stone-face").get("ok") is False)
a = join(code, "Amy")
b = join(code, "Bo")
d = host(code, ht, "lock")
check("lock", d.get("ok") is True)
d = host(code, ht, "start", mode="stone-face")
check("start stone-face", d.get("mode") == "stone-face")

v = view(code, a["seat_token"])
check("collecting screen has info box",
      ("textarea", "info") in comps(v))

check("empty info rejected",
      inp(code, a["seat_token"], 1, kind="info",
          text="  ").get("ok") is False)
check("unknown kind rejected",
      inp(code, a["seat_token"], 2, kind="dance",
          text="x").get("ok") is False)
check("crack before set rejected",
      inp(code, a["seat_token"], 3, kind="crack").get("ok") is False)

check("info accepted", inp(code, a["seat_token"], 4, kind="info",
                            text="I narrate my own cooking like a documentary").get("ok") is True)
check("resubmit overwrites (still collecting)",
      inp(code, a["seat_token"], 5, kind="info",
          text="I narrate my own cooking like a true-crime doc").get("ok") is True)
check("all submitted -> auto performing",
      inp(code, solo["seat_token"], 1, kind="info", text="I clap in cinemas")["ok"] is True
      and inp(code, b["seat_token"], 1, kind="info", text="I fear my own doorbell")["ok"] is True
      and ROOMS[code]["mode_state"]["phase"] == "performing")

st = ROOMS[code]["mode_state"]
check("set weaves every confession (2 Ella + 3 infos)",
      len(st["set"]) == 5
      and st["set"][0]["by"] == "ELLA"
      and st["set"][-1]["by"] == "ELLA"
      and "true-crime doc" in st["set"][2]["text"]  # join order: Solo, Amy, Bo
      and "doorbell" in st["set"][3]["text"])

v = view(code, b["seat_token"])
check("hold screen has CRACKED button",
      ("button", "cracked") in comps(v))

# (seat tokens are opaque; resolve player ids via ROOMS)
def _pid(code, tok):
    for pid, p in ROOMS[code]["players"].items():
        if p["token"] == tok:
            return pid
    return None

apid, spid, bpid = (_pid(code, a["seat_token"]), _pid(code, solo["seat_token"]),
                    _pid(code, b["seat_token"]))
check("amy cracks at line 0",
      inp(code, a["seat_token"], 6, kind="crack").get("ok") is True
      and ROOMS[code]["mode_state"]["cracked"].get(apid) == 0)
check("crack recorded at line 0",
      ROOMS[code]["mode_state"]["cracked"].get(apid) == 0)
check("double crack rejected",
      inp(code, a["seat_token"], 7, kind="crack").get("ok") is False)
v = view(code, a["seat_token"])
check("cracked player sees wait screen",
      v["screen"] == "wait"
      and "CRACKED" in (v["components"][0].get("text") or ""))

check("host advance steps the set",
      host(code, ht, "advance").get("ok") is True
      and ROOMS[code]["mode_state"]["line_i"] == 1)
check("bo cracks at line 1",
      inp(code, b["seat_token"], 2, kind="crack").get("ok") is True
      and ROOMS[code]["mode_state"]["cracked"].get(bpid) == 1)

for _ in range(len(ROOMS[code]["mode_state"]["set"]) + 1):
    if ROOMS[code]["mode_state"]["phase"] == "scored":
        break
    host(code, ht, "advance")
st = ROOMS[code]["mode_state"]
check("set end -> scored", st["phase"] == "scored")
check("lone survivor +3 (solo)",
      ROOMS[code]["players"][spid]["score"] == 3)
check("crack order kept (amy, bo)",
      [p for p in st["crack_order"]] == [apid, bpid])
check("post-set crack rejected",
      inp(code, solo["seat_token"], 9, kind="crack").get("ok") is False)
v = view(code, solo["seat_token"])
check("scores screen after set", v["screen"] == "scores")

# ── room 2: everybody cracks -> shutout ─────────────────────────────────
code2, ht2 = new_room()
x = join(code2, "X")
y = join(code2, "Y")
host(code2, ht2, "lock")
host(code2, ht2, "start", mode="stone-face")
inp(code2, x["seat_token"], 1, kind="info", text="info x")
inp(code2, y["seat_token"], 1, kind="info", text="info y")
check("assembled", ROOMS[code2]["mode_state"]["phase"] == "performing")
inp(code2, x["seat_token"], 2, kind="crack")
d = inp(code2, y["seat_token"], 2, kind="crack")
check("last crack auto-scores", d.get("ok") is True
      and ROOMS[code2]["mode_state"]["phase"] == "scored")
tot = sum(p["score"] for p in ROOMS[code2]["players"].values())
check("all-crack shutout (no points)", tot == 0)

# ── room 3: solo vs bots ────────────────────────────────────────────────
code3, ht3 = new_room()
h = join(code3, "Human")
d = host(code3, ht3, "bots", n=3)  # seat bots in lobby (start needs 2+)
check("bots seat in lobby", d.get("ok") is True and len(d.get("bots", [])) == 3)
host(code3, ht3, "lock")
d = host(code3, ht3, "start", mode="stone-face")
check("start with human + 3 bots", d.get("mode") == "stone-face")
inp(code3, h["seat_token"], 1, kind="info", text="human intel")
check("human intel held for bots",
      ROOMS[code3]["mode_state"]["phase"] == "collecting")
d = host(code3, ht3, "bots", n=1)  # mid-night: seats 1 more + drives collect
check("mid-night bots drive confessions", d.get("ok") is True)
st3 = ROOMS[code3]["mode_state"]
n3 = len(ROOMS[code3]["players"])
check("bot infos assembled into set",
      st3["phase"] == "performing" and len(st3["set"]) == 2 + n3)
for _ in range(len(st3["set"]) + 2):
    if ROOMS[code3]["mode_state"]["phase"] == "scored":
        break
    host(code3, ht3, "advance")
    # human holds the whole set on purpose
check("solo night completes", ROOMS[code3]["mode_state"]["phase"] == "scored")
v3 = view(code3, h["seat_token"])
check("human sees scores screen", v3["screen"] == "scores")

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
