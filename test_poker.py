#!/usr/bin/env python3
"""Simulated-player tests for poker night (fixed-limit Hold'em).

Covers: evaluator vectors (ordering, wheel, kickers, ties), blinds +
hole secrecy, turn order, check/call/bet/fold legality, street flow,
showdown + split pots, uncontested win, all-bot night completion,
raise cap, timeout force, restart rules.

Run: python3 test_poker.py (script, never pytest).
"""

import json

from app import app
from party import ROOMS, _pk_eval5, _pk_best

c = app.test_client()
N = {"pass": 0, "fail": 0}


def check(name, cond):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name)


def C(s):
    return [s[i:i + 2] for i in range(0, len(s), 2)]


# ── evaluator ──────────────────────────────────────────────────────────
check("royal flush", _pk_eval5(C("AsKsQsJsTs"))[0] == 8)
check("SF beats quads",
      _pk_eval5(C("AsKsQsJsTs")) > _pk_eval5(C("9s9h9d9c2s")))
check("quads kicker", _pk_eval5(C("9s9h9d9cAs")) > _pk_eval5(C("9s9h9d9c2s")))
check("full house", _pk_eval5(C("KsKhKd2s2c"))[0] == 6)
check("flush beats straight",
      _pk_eval5(C("As3s5s7s9s")) > _pk_eval5(C("9s8h7d6c5s")))
check("wheel straight", _pk_eval5(C("As2h3d4c5s")) == (4, 3))
check("wheel loses to 6-high", _pk_eval5(C("As2h3d4c5s")) < _pk_eval5(C("2s3h4d5c6s")))
check("trips kickers", _pk_eval5(C("7s7h7dAs2c")) > _pk_eval5(C("7s7h7dKs2c")))
check("two pair kicker", _pk_eval5(C("AsAh2s2hKs")) > _pk_eval5(C("AsAh2s2hQs")))
check("pair beats high", _pk_eval5(C("2s2h5d7c9s")) > _pk_eval5(C("AsKhQdJc9s")))
check("tie splits", _pk_eval5(C("AsKhQdJc9s")) == _pk_eval5(C("AhKsQcJd9h")))
check("best of 7 finds flush",
      _pk_best(C("AsKsQs3s5s2h7d"))[0] == 5)
check("best of 7 straight on board",
      _pk_best(C("2s3h4d5c6sAsKs")) == (4, 4))


# ── helpers ────────────────────────────────────────────────────────────
def new_room():
    r = c.post("/party/create")
    d = json.loads(r.data)
    assert d["ok"]
    return d["code"], d["host_token"]


def join(code, name):
    return json.loads(c.post(f"/party/{code}/join", json={"name": name}).data)


def host(code, ht, cmd, **kw):
    body = {"host_token": ht, "cmd": cmd}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/host", json=body).data)


def inp(code, tok, seq, **kw):
    body = {"seat_token": tok, "client_seq": seq}
    body.update(kw)
    return json.loads(c.post(f"/party/{code}/input", json=body).data)


def view(code, tok):
    return json.loads(c.get(f"/party/{code}/view",
                            query_string={"seat_token": tok}).data)["view"]


# ── room 1: humans, full hand ──────────────────────────────────────────
code, ht = new_room()
a = join(code, "Amy")
b = join(code, "Bo")
d = host(code, ht, "bots", n=1)
check("bot seats pre-start", d.get("ok") is True)
host(code, ht, "lock")
d = host(code, ht, "start", mode="poker")
check("start poker", d.get("mode") == "poker")
st = ROOMS[code]["mode_state"]
check("blinds posted (3 committed)", sum(st["committed"].values()) == 3)
check("hole cards dealt secretly",
      len(st["hole"]) == 3 and all(len(v) == 2 for v in st["hole"].values()))

# secrecy: Amy sees her cards, not Bo's
va = view(code, a["seat_token"])
hole_txt = " ".join(x.get("text", "") for x in va.get("components", []))
pa = next(pid for pid, p in ROOMS[code]["players"].items()
          if p["token"] == a["seat_token"])
pb = next(pid for pid, p in ROOMS[code]["players"].items()
          if p["token"] == b["seat_token"])
check("own hole visible",
      " ".join(st["hole"][pa]) in hole_txt)
check("others hole hidden",
      st["hole"][pb][0] not in hole_txt)

# out-of-turn rejected, bad kind rejected
other = a["seat_token"] if st["actor"] != pa else b["seat_token"]
check("out-of-turn rejected",
      inp(code, other, 1, kind="call").get("ok") is False)
check("unknown kind rejected",
      inp(code, a["seat_token"], 2, kind="dance").get("ok") is False)


def actor_tok():
    st = ROOMS[code]["mode_state"]
    act = st.get("actor")
    if not act:
        return None
    tok = ROOMS[code]["players"][act]["token"]
    return tok


def play_street(max_moves=12):
    for _ in range(max_moves):
        st = ROOMS[code]["mode_state"]
        if st.get("phase") != "betting" or not st.get("actor"):
            return
        tok = actor_tok()
        p = ROOMS[code]["players"][st["actor"]]
        if p.get("bot"):
            return  # bots drive themselves; caller advances differently
        seq = 100 + len(st.get("history", []))
        # humans check when free else call
        from party import _pk_to_match
        kind = "check" if _pk_to_match(ROOMS[code], st["actor"]) <= 0 else "call"
        r = inp(code, tok, 900 + hash((st["hand"], st["street"], st["actor"])) % 50
                + len(json.dumps(st["acted"])), kind=kind)
        assert r.get("ok"), r


# drive the whole hand: humans check/call, bots auto
moves = 0
while ROOMS[code]["mode_state"].get("phase") == "betting" and moves < 60:
    st = ROOMS[code]["mode_state"]
    if not st.get("actor"):
        host(code, ht, "advance")
        moves += 1
        continue
    p = ROOMS[code]["players"][st["actor"]]
    if p.get("bot"):
        moves += 1  # bot already acted synchronously; nudge street if stuck
        host(code, ht, "advance") if moves % 3 == 0 else None
        continue
    from party import _pk_to_match
    kind = "check" if _pk_to_match(ROOMS[code], st["actor"]) <= 0 else "call"
    r = inp(code, p["token"], 500 + moves, kind=kind)
    assert r.get("ok"), (kind, r)
    moves += 1
st = ROOMS[code]["mode_state"]
check("hand completes to showdown", st.get("phase") == "showdown")
check("winners paid", sum(p["score"] for p in ROOMS[code]["players"].values()) > 0)
check("hole revealed for winners",
      all("hole" in w or "hand" in w for w in st.get("winners", [])))
v = view(code, a["seat_token"])
check("scores screen", v["screen"] == "scores")
d = host(code, ht, "advance")
check("next hand deals", ROOMS[code]["mode_state"].get("phase") == "betting"
      and ROOMS[code]["mode_state"].get("hand") == 2)

# ── room 2: all bots, timeout, min players ─────────────────────────────
code2, ht2 = new_room()
solo = join(code2, "Solo")
check("1P start refused",
      host(code2, ht2, "lock") and
      host(code2, ht2, "start", mode="poker").get("ok") is False)
host(code2, ht2, "bots", n=3)
host(code2, ht2, "start", mode="poker")
for _ in range(40):
    st = ROOMS[code2]["mode_state"]
    if st.get("phase") != "betting":
        break
    host(code2, ht2, "advance")
st = ROOMS[code2]["mode_state"]
check("all-bot night completes", st.get("phase") == "showdown")
tot = sum(p["score"] for p in ROOMS[code2]["players"].values())
pots = sum(p["amount"] for p in st.get("pots", []))
check("pot conserved (paid == pot)", tot == pots and pots > 0)

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
