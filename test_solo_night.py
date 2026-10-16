#!/usr/bin/env python3
"""Solo-vs-agents: 1 human + 3 bots play a full freeze-night.
Human drives only their own inputs; bots auto-fill everything else.
Run: python3 test_solo_night.py (script, never pytest).
"""

import json

from app import app
from party import ROOMS

c = app.test_client()
N = {"pass": 0, "fail": 0}


def check(name, cond):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name)


def host(code, ht, cmd, **kw):
    body = {"host_token": ht, "cmd": cmd}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/host", json=body).data)


def inp(code, tok, seq, **kw):
    body = {"seat_token": tok, "client_seq": seq}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/input", json=body).data)


r = json.loads(c.post("/party/create").data)
code, ht = r["code"], r["host_token"]
me = json.loads(c.post(f"/party/{code}/join", json={"name": "Solo"}).data)
tok = me["seat_token"]
c.post(f"/party/{code}/host", json={"host_token": ht, "cmd": "lock"})

r = host(code, ht, "bots", n=3)
check("3 bots seated", r.get("ok") is True and len(r.get("bots", [])) == 3)
room = ROOMS[code]
check("room has 4 players", len(room["players"]) == 4)

r = host(code, ht, "start", mode="freeze-night")
check("night starts with bots counting as players", r.get("ok") is True)
st = room["mode_state"]
check("bots pre-submitted entries",
      sum(1 for p in st["entries"] if p.startswith("bot")) == 3)

seq = 1


def human_entry(text, **kw):
    global seq
    seq += 1
    return inp(code, tok, seq, kind="entry", text=text, **kw)


def human_vote_for_someone():
    """Vote option 0 unless it's ours, else 1."""
    global seq
    seq += 1
    opts = [i for i, pid in enumerate(st["order"])
            if pid != [p for p in room["players"]
                       if room["players"][p]["token"] == tok][0]]
    return inp(code, tok, seq, kind="vote", choice=str(opts[0]))


def advance():
    return host(code, ht, "advance")


# R1 ending
human_entry("my human ending")
check("R1 auto-reveal (bots+human)", st["phase"] == "voting")
human_vote_for_someone()
check("R1 scored", st["phase"] == "scored")
advance()

# R2 walkin
check("R2 walkin live", st["round_id"] == "scene1-walkin")
human_entry("a tired astronaut")
human_vote_for_someone()
advance()

# R3 ritual (victim is a bot by rotation: order[2])
check("R3 ritual live", st["round_id"] == "ritual-halftime")
vic = st["ritual"]["victim"]
check("victim is a bot", room["players"][vic].get("bot") is True)
seq += 1
inp(code, tok, seq, kind="rite", text="my cruel line // whispered")
check("ritual judging", st["phase"] == "passfail")
seq += 1
inp(code, tok, seq, kind="pass", verdict="pass")
check("ritual author phase", st["phase"] == "author")
# guess someone (not self, not victim)
mypid = [p for p in room["players"] if room["players"][p]["token"] == tok][0]
cands = [p for p in room["players"] if p not in (mypid, vic)]
seq += 1
inp(code, tok, seq, kind="author", player_id=cands[0])
check("ritual scored", st["phase"] == "scored")
advance()

# R4 object + R5 ending
for rid in ("scene2-object", "scene2-ending"):
    check(f"{rid} live", st["round_id"] == rid)
    human_entry(f"human {rid}")
    human_vote_for_someone()
    advance()

# wheel
check("wheel live", st["round_id"] == "wheel")
seq += 1
inp(code, tok, seq, kind="verdict", verdict="served")
check("wheel scored", st["phase"] == "scored")
advance()

# last lash
check("final live", st["round_id"] == "last-lash")
human_entry("human epitaph")
seq += 1
opts = list(range(len([p for p in st["order"] if p in st["entries"]])))
inp(code, tok, seq, kind="vote", choice=str(opts[0]), choices=[str(o) for o in opts[:2]])
advance()
check("solo night done", room["phase"] == "done")
check("champion crowned", bool(room.get("winner")))
scores = {p["name"]: p["score"] for p in room["players"].values()}
check("scores moved", sum(scores.values()) > 0)
print("scores:", scores)

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
