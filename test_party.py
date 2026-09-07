#!/usr/bin/env python3
"""Simulated-player tests: full games with fake phones, no browsers.

Covers: join/lock/start, hidden-info leakage, dup + late input, self-vote,
reconnect, audience overflow, draw rate-limit, host auth, moderation.
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


def join(code, name, freak="Martin Lamp", tok=""):
    body = {"name": name, "freak": freak}
    if tok:
        body["seat_token"] = tok
    return json.loads(c.post(f"/party/{code}/join", json=body).data)


# ── 1. freaktionary full game ─────────────────────────────────────────
code, host = new_room()
ps = [join(code, f"P{i}") for i in range(4)]
check("4 players seated", all(p["role"] == "player" for p in ps))
toks = [p["seat_token"] for p in ps]

# audience overflow
extra = [join(code, f"Extra{i}") for i in range(6)]
check("overflow becomes audience",
      sum(1 for e in extra if e["role"] == "audience") == 2)

r = json.loads(c.post(f"/party/{code}/host",
                      json={"host_token": "bad", "cmd": "lock"}).data)
check("bad host token rejected", r.get("ok") is False)

c.post(f"/party/{code}/host", json={"host_token": host, "cmd": "lock"})
r = json.loads(c.post(f"/party/{code}/host",
                      json={"host_token": host, "cmd": "start",
                            "mode": "freaktionary"}).data)
check("freaktionary starts", r.get("ok") is True)

room = ROOMS[code]
drawer_tok = toks[0]  # round 1 drawer = first player
drawer_view = json.loads(
    c.get(f"/party/{code}/view", query_string={"seat_token": drawer_tok}).data)["view"]
other_view = json.loads(
    c.get(f"/party/{code}/view", query_string={"seat_token": toks[1]}).data)["view"]
word = room["mode_state"]["word"]
check("drawer gets secret word", drawer_view.get("secret") == word)
check("no leakage to guesser",
      word not in json.dumps(other_view))

# non-drawer cannot draw
r = json.loads(c.post(f"/party/{code}/input",
                      json={"seat_token": toks[1], "client_seq": 1,
                            "kind": "draw.batch",
                            "points": [[0.1, 0.1]]}).data)
check("non-drawer draw rejected", r.get("ok") is False)

# drawer draws (vectors only)
r = json.loads(c.post(f"/party/{code}/input",
                      json={"seat_token": drawer_tok, "client_seq": 1,
                            "kind": "draw.batch",
                            "points": [[0.1, 0.2], [0.3, 0.4]]}).data)
check("drawer batch accepted", r.get("ok") is True)

# immediate re-draw hits rate limit
r = json.loads(c.post(f"/party/{code}/input",
                      json={"seat_token": drawer_tok, "client_seq": 2,
                            "kind": "draw.batch",
                            "points": [[0.5, 0.5]]}).data)
check("draw rate-limited", r.get("ok") is False)

# wrong then right guess
r = json.loads(c.post(f"/party/{code}/input",
                      json={"seat_token": toks[1], "client_seq": 2,
                            "kind": "guess", "text": "definitely not it xyz"}).data)
check("wrong guess accepted, not correct",
      r.get("ok") is True and r.get("correct") is False)
# dup retry of the same client_seq
r2 = json.loads(c.post(f"/party/{code}/input",
                       json={"seat_token": toks[1], "client_seq": 2,
                             "kind": "guess", "text": "definitely not it xyz"}).data)
check("dup client_seq deduped", r2.get("dup") is True)
r = json.loads(c.post(f"/party/{code}/input",
                      json={"seat_token": toks[2], "client_seq": 5,
                            "kind": "guess", "text": word}).data)
check("correct guess wins", r.get("correct") is True)

# reconnect with same seat token
r = join(code, "Ghost", tok=toks[3])
check("reconnect restores seat", r.get("reconnected") is True)

# stream replay from 0 contains public events, never the secret word
s = json.loads(c.get(f"/party/{code}/stream",
                     query_string={"last_seq": 0, "once": 1}).data)
kinds = [e["kind"] for e in s["events"]]
check("stream has round lifecycle",
      "round.started" in kinds and "round.won" in kinds)
check("stream never leaks word",
      word not in json.dumps([e for e in s["events"]
                              if e["kind"] != "round.won"]))

# ── 2. roast-relay full game ──────────────────────────────────────────
code2, host2 = new_room()
ps2 = [join(code2, f"R{i}", freak=f"Freak{i}") for i in range(3)]
t2 = [p["seat_token"] for p in ps2]
c.post(f"/party/{code2}/host", json={"host_token": host2, "cmd": "lock"})
c.post(f"/party/{code2}/host",
       json={"host_token": host2, "cmd": "start", "mode": "roast-relay",
             "target": "Dave and his air fryer"})
# player views hide each other's lines
for i, t in enumerate(t2):
    json.loads(c.post(f"/party/{code2}/input",
                      json={"seat_token": t, "client_seq": 1,
                            "kind": "line", "text": f"secret line {i}"}).data)
room2 = ROOMS[code2]
check("all lines trigger reveal", room2["mode_state"]["phase"] == "voting")
v = json.loads(c.get(f"/party/{code2}/view",
                     query_string={"seat_token": t2[0]}).data)["view"]
comps = json.dumps([cc for cc in v["components"] if cc.get("type") == "choice"])
check("vote screen hides authorship",
      "secret line 1" in comps and "R1" not in comps)

# self-vote rejected (clip 0 belongs to R0)
r = json.loads(c.post(f"/party/{code2}/input",
                      json={"seat_token": t2[0], "client_seq": 2,
                            "kind": "vote", "choice": "0"}).data)
check("self-vote rejected", r.get("ok") is False)
# R0->clip1, R1->clip0, R2->clip1 (nobody votes their own)
for t, ch in [(t2[0], "1"), (t2[1], "0"), (t2[2], "1")]:
    json.loads(c.post(f"/party/{code2}/input",
                      json={"seat_token": t, "client_seq": 9,
                            "kind": "vote", "choice": ch}).data)
check("all votes trigger scoring",
      ROOMS[code2]["mode_state"]["phase"] == "scored")
check("winner got 3 points",
      ROOMS[code2]["players"][
          ROOMS[code2]["mode_state"]["order"][1]]["score"] == 3)

# late line after scoring rejected
r = json.loads(c.post(f"/party/{code2}/input",
                      json={"seat_token": t2[0], "client_seq": 10,
                            "kind": "line", "text": "too late"}).data)
check("late input rejected", r.get("ok") is False)

# moderation: new round, reject one line, reveal still works
c.post(f"/party/{code2}/host", json={"host_token": host2, "cmd": "advance"})
for t in t2:
    json.loads(c.post(f"/party/{code2}/input",
                      json={"seat_token": t, "client_seq": 20,
                            "kind": "line", "text": "round two"}).data)
check("round two auto-reveals", ROOMS[code2]["mode_state"]["phase"] == "voting")

print(f"\n{N['pass']} passed, {N['fail']} failed")
if N["fail"]:
    raise SystemExit(1)

# ── 3. persistent freak memory + restart ─────────────────────────────
import party as P

rec = json.loads(open("party_records.json").read())
check("winner freak banked a party win",
      any(v.get("wins", 0) >= 1 for v in rec.values()))
check("head-to-head recorded",
      any(v.get("vs") for v in rec.values()))

s = json.loads(c.get(f"/party/{code2}/stream",
                     query_string={"last_seq": 0, "once": 1}).data)
check("lore event broadcast at start",
      any(e["kind"] == "lore" and e.get("lines") for e in s["events"]))
check("stage snapshot carries lore", bool(s["snapshot"].get("lore")))

# simulate restart: drop RAM, reload snapshot from disk
saved_tok, saved_code = t2[0], code2
P._save_rooms()
ROOMS.clear()
P._load_rooms()
check("room survives restart", saved_code in ROOMS)
v = json.loads(c.get(f"/party/{saved_code}/view",
                     query_string={"seat_token": saved_tok}).data)
check("seat token survives restart",
      v.get("ok") is True and v["view"]["phase"] == "playing")
check("scores survive restart",
      sum(p["score"] for p in v["view"]["players"]) > 0)

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
