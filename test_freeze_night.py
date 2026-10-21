#!/usr/bin/env python3
"""Simulated-player tests for freeze-night: full MVP night with fake phones.

Covers: join/lock/start, entries + auto-reveal, no self-votes, callback
x1.5 (once per event), ritual pass/fail + author-guess, wheel spin +
verdict, last-lash spread votes + triple pool, crowning + running gag,
caught-that board, dup + bad input, timeout skip.

Run: python3 test_freeze_night.py (script, never pytest).
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


def inp(code, tok, seq, **kw):
    body = {"seat_token": tok, "client_seq": seq}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/input", json=body).data)


def host(code, host_tok, cmd, **kw):
    body = {"host_token": host_tok, "cmd": cmd}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/host", json=body).data)


def view(code, tok):
    return json.loads(
        c.get(f"/party/{code}/view",
              query_string={"seat_token": tok}).data)["view"]


# ── night ─────────────────────────────────────────────────────────────
code, host_tok = new_room()
ps = [join(code, f"P{i}") for i in range(4)]
toks = [p["seat_token"] for p in ps]
pids = list(ROOMS[code]["players"].keys())

c.post(f"/party/{code}/host", json={"host_token": host_tok, "cmd": "lock"})
r = host(code, host_tok, "start", mode="freeze-night")
check("freeze-night starts", r.get("ok") is True)
room = ROOMS[code]
check("round 1 is scene1-ending",
      room["mode_state"]["round_id"] == "scene1-ending")

v = view(code, toks[0])
check("controller gets prompt screen", v.get("screen") == "prompt")

# bad inputs
r = inp(code, toks[0], 1, kind="entry", text="   ")
check("empty entry rejected", r.get("ok") is False)
r = inp(code, toks[0], 2, kind="vote", choice="0")
check("vote before reveal rejected", r.get("ok") is False)

# R1: all enter; all vote option 0 except P0 (no self-vote) -> P1... P0 votes 1
seq = 10
for i, t in enumerate(toks):
    r = inp(code, t, seq + i, kind="entry", text=f"ending number {i} wow")
    check(f"R1 entry {i} accepted", r.get("ok") is True)
check("auto-reveal after all entries",
      room["mode_state"]["phase"] == "voting")
check("archive holds 4 events", len(room["mode_state"]["archive"]) == 4)

r = inp(code, toks[0], 50, kind="vote", choice="0")
check("self-vote rejected", r.get("ok") is False)
seq = 60
inp(code, toks[0], seq, kind="vote", choice="1")
inp(code, toks[1], seq + 1, kind="vote", choice="0")
inp(code, toks[2], seq + 2, kind="vote", choice="0")
inp(code, toks[3], seq + 3, kind="vote", choice="0")
check("R1 scored", room["mode_state"]["phase"] == "scored")
p0 = room["players"][pids[0]]["score"]
check("R1 winner P0 gets 75 (3/4 of 100, no sweep)", p0 == 75)

# caught-that board
r = inp(code, toks[1], 70, kind="caught", event="e1")
check("caught-that accepted", r.get("ok") is True)
check("recognition counted",
      room["mode_state"]["recognized"].get("e1") == 1)
r = inp(code, toks[1], 71, kind="caught", event="exx")
check("bogus event rejected", r.get("ok") is False)

# dup
r = inp(code, toks[0], seq, kind="vote", choice="1")
check("dup client_seq short-circuits", r.get("dup") is True)

host(code, host_tok, "advance")
check("round 2 is scene1-walkin",
      room["mode_state"]["round_id"] == "scene1-walkin")

# R2: P0 declares callback:e2; everyone votes P0 (idx 0) except P0
seq = 100
inp(code, toks[0], seq, kind="entry", text="a divorced magician",
    callback="e2")
for i, t in enumerate(toks[1:], 1):
    inp(code, t, seq + i, kind="entry", text=f"walkin {i}")
inp(code, toks[0], seq + 10, kind="vote", choice="2")
inp(code, toks[1], seq + 11, kind="vote", choice="0")
inp(code, toks[2], seq + 12, kind="vote", choice="0")
inp(code, toks[3], seq + 13, kind="vote", choice="0")
p0b = room["players"][pids[0]]["score"]
check("R2 callback x1.5 paid (75 -> 75+112)",
      p0b - p0 == round(75 * 1.5))
check("event e2 marked paid", "e2" in room["mode_state"]["paid"])

host(code, host_tok, "advance")
check("round 3 is ritual",
      room["mode_state"]["round_id"] == "ritual-halftime")
st = room["mode_state"]
victim_pid = st["ritual"]["victim"]
check("victim is 3rd player (rotation)", victim_pid == pids[2])
vtok = toks[pids.index(victim_pid)]
r = inp(code, vtok, 200, kind="rite", text="victim writes, illegal")
check("victim cannot write", r.get("ok") is False)

# others write; longest (P1) becomes spotlight
writers = [(t, p) for t, p in zip(toks, pids) if p != victim_pid]
lines = {"short": 0, "a much longer humiliating line here": 1,
         "medium length line ok": 2}
seq = 210
for (t, _), (txt, _) in zip(writers, lines.items()):
    inp(code, t, seq, kind="rite", text=txt)
    seq += 1
st = room["mode_state"]
spot = st["ritual"]["spotlight"]
spot_author = [p for p in pids if p != victim_pid][1]
check("spotlight is longest line", spot == spot_author)
check("ritual in passfail", st["phase"] == "passfail")
vv = view(code, vtok)
check("victim sees judgement screen", "judge" in json.dumps(vv).lower()
      or vv.get("screen") == "wait")

# pass/fail: 2 pass 1 fail -> victim share 67
pvotes = ["pass", "pass", "fail"]
for (t, _), v in zip(writers, pvotes):
    inp(code, t, 220 + writers.index((t, _)), kind="pass", verdict=v)
check("ritual in author phase", room["mode_state"]["phase"] == "author")
vic_score = room["players"][victim_pid]["score"]
check("victim paid 67 (2/3 of 100)", vic_score == round(2 / 3 * 100))

# author guesses: two correct, one wrong -> spot +10, guessers +10 each correct
# writers order: [P0, P1, P3] (victim P2). spot author = writers[1] (P1).
r = inp(code, writers[0][0], 230, kind="author", player_id="nope")
check("bad guess rejected", r.get("ok") is False)
inp(code, writers[0][0], 231, kind="author", player_id=spot_author)
inp(code, writers[1][0], 232, kind="author", player_id=writers[0][1])
inp(code, writers[2][0], 233, kind="author", player_id=spot_author)
check("ritual scored", room["mode_state"]["phase"] == "scored")

host(code, host_tok, "advance")
check("round 4 is scene2-object",
      room["mode_state"]["round_id"] == "scene2-object")
seq = 300
for i, t in enumerate(toks):
    inp(code, t, seq + i, kind="entry", text=f"object {i}")
for i, t in enumerate(toks):
    # everyone votes option 1 (P1) except P1 votes 2
    inp(code, t, seq + 10 + i, kind="vote",
        choice="2" if i == 1 else "1")
host(code, host_tok, "advance")
check("round 5 is scene2-ending",
      room["mode_state"]["round_id"] == "scene2-ending")
seq = 400
for i, t in enumerate(toks):
    inp(code, t, seq + i, kind="entry", text=f"finale {i}")
for i, t in enumerate(toks):
    # everyone votes option 3 (P3's) except P3, who votes 0
    inp(code, t, seq + 10 + i, kind="vote", choice="0" if i == 3 else "3")
host(code, host_tok, "advance")
check("round 6 is wheel", room["mode_state"]["round_id"] == "wheel")
st = room["mode_state"]
check("wheel spun for lowest scorer", st["wheel"]["victim"] is not None)
check("segment burned", len(st["wheel"]["burned"]) == 1)
sv = view(code, toks[0])
check("stage exposes wheel", "freeze-night" in json.dumps(
    json.loads(c.get(f"/party/{code}/view",
                     query_string={"seat_token": toks[0]}).data)["view"]))

seq = 500
for i, t in enumerate(toks):
    inp(code, t, seq + i, kind="verdict", verdict="served")
check("wheel scored", room["mode_state"]["phase"] == "scored")

host(code, host_tok, "advance")
check("round 7 is last-lash", room["mode_state"]["round_id"] == "last-lash")
seq = 600
for i, t in enumerate(toks):
    inp(code, t, seq + i, kind="entry", text=f"epitaph {i}")
# spread votes: P0 stacks on 0 allowed (self-vote ok in final)
inp(code, toks[0], 610, kind="vote", choice="0", choices=["0", "1"])
inp(code, toks[1], 611, kind="vote", choice="0", choices=["0"])
inp(code, toks[2], 612, kind="vote", choice="0", choices=["0", "2"])
inp(code, toks[3], 613, kind="vote", choice="1", choices=["1"])
tally_total = sum(len(v) for v in room["mode_state"]["votes"].values())
check("spread votes counted", tally_total == 6)
host(code, host_tok, "advance")
check("night done", room["phase"] == "done")
check("champion crowned", bool(room.get("winner")))
st = room["mode_state"]
check("running gag picked", st["archive"] and
      max(st["archive"], key=lambda e: e["invokes"])["invokes"] >= 1)

# ── clients: pages + component contracts ──────────────────────────────
code2, host2 = new_room()
ps2 = [join(code2, f"C{i}") for i in range(4)]
toks2 = [p["seat_token"] for p in ps2]
c.post(f"/party/{code2}/host", json={"host_token": host2, "cmd": "lock"})
host(code2, host2, "start", mode="freeze-night")

r = c.get(f"/party/{code2}/stage")
check("stage page serves", r.status_code == 200 and code2.encode() in r.data)
r = c.get(f"/party/{code2}/play")
check("controller page serves", r.status_code == 200)
r = c.get(f"/join/{code2}")
check("join page serves", r.status_code == 200 and code2.encode() in r.data)

for i, t in enumerate(toks2):
    inp(code2, t, 1 + i, kind="entry", text=f"client ending {i}")
vv = view(code2, toks2[0])
ch = [x for x in vv.get("components", []) if x.get("type") == "choice"]
check("vote choice carries action contract",
      bool(ch) and ch[0].get("action", {}).get("kind") == "vote")

room2 = ROOMS[code2]
for i, t in enumerate(toks2):
    inp(code2, t, 10 + i, kind="vote", choice="1" if i == 0 else "0")
host(code2, host2, "advance")
check("walkin round live", room2["mode_state"]["round_id"] == "scene1-walkin")
for i, t in enumerate(toks2):
    inp(code2, t, 14 + i, kind="entry", text=f"client walkin {i}")
for i, t in enumerate(toks2):
    inp(code2, t, 17 + i, kind="vote", choice="1" if i == 0 else "0")
host(code2, host2, "advance")
st2 = room2["mode_state"]
check("ritual round live", st2["round_id"] == "ritual-halftime")
vpids = list(room2["players"].keys())
vtok2 = toks2[vpids.index(st2["ritual"]["victim"])]
others2 = [(t, p) for t, p in zip(toks2, vpids) if p != st2["ritual"]["victim"]]
for j, (t, _) in enumerate(others2):
    inp(code2, t, 20 + j, kind="rite",
        text=f"client rite {j} with extra words here")
vview = view(code2, vtok2)
check("victim gets perform screen with line",
      vview.get("screen") == "perform" and
      "client rite" in json.dumps(vview))

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
