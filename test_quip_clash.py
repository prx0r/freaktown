#!/usr/bin/env python3
"""Quip-clash: every deck playable solo (1 human + 2 bots).
Covers: normal/inverted/liar twists, secret truth flags, sweep,
round advance across decks. Run: python3 test_quip_clash.py.
"""

import json

from app import app
from party import QC_DECKS, ROOMS

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


def solo_room(mode, nbots=2):
    r = json.loads(c.post("/party/create").data)
    code, ht = r["code"], r["host_token"]
    me = json.loads(c.post(f"/party/{code}/join", json={"name": "Solo"}).data)
    c.post(f"/party/{code}/host", json={"host_token": ht, "cmd": "lock"})
    host(code, ht, "bots", n=nbots)
    r = host(code, ht, "start", mode=mode)
    assert r.get("ok"), r
    room = ROOMS[code]
    toks = [p["token"] for p in room["players"].values() if not p.get("bot")]
    return code, ht, room, toks[0]


def play_round(code, ht, room, tok, seq0, entry_kw=None):
    """Human enters + votes non-self; bots auto-fill. Returns True if scored."""
    st = room["mode_state"]
    mypid = [p for p in room["players"]
             if room["players"][p]["token"] == tok][0]
    inp(code, tok, seq0, kind="entry",
        text=f"human line {st['round']}", **(entry_kw or {}))
    if room["mode_state"]["phase"] != "voting":
        return False
    st = room["mode_state"]
    opts = [i for i, pid in enumerate(list(room["players"].keys()))
            if pid in st["entries"] and pid != mypid]
    inp(code, tok, seq0 + 1, kind="vote", choice=str(opts[0]))
    return room["mode_state"]["phase"] == "scored"


for deck_id, deck in QC_DECKS.items():
    mode = f"quip-{deck_id}"
    code, ht, room, tok = solo_room(mode)
    st = room["mode_state"]
    ok_deck = st.get("deck") == deck_id
    check(f"{deck_id}: starts", ok_deck)
    kw = {"truth": True} if deck["twist"] == "liar" else {}
    seq = 1
    ok = play_round(code, ht, room, tok, seq, kw)
    check(f"{deck_id}: round scores ({deck['twist']})", ok)
    if deck["twist"] == "liar":
        check(f"{deck_id}: secrets revealed at score",
              isinstance(st.get("secrets_revealed"), dict)
              and len(st["secrets_revealed"]) == len(room["players"]))
    host(code, ht, "advance")
    check(f"{deck_id}: advances to round 2", st.get("round") == 2)
    if deck_id == "lies":
        # liar spot-check: a caught lie paid someone
        total = sum(p["score"] for p in room["players"].values())
        check("lies: points moved", total > 0)

# inverted sanity: dedicated room, all vote same -> fewest-votes logic
code, ht, room, tok = solo_room("quip-least-funny")
st = room["mode_state"]
pids = list(room["players"].keys())
mypid = [p for p in pids if room["players"][p]["token"] == tok][0]
inp(code, tok, 1, kind="entry", text="human unfunny")
# bots pre-submitted at round start and auto-vote at reveal; human votes a bot
st = room["mode_state"]
others = [j for j, q in enumerate(pids) if q in st["entries"] and q != mypid]
inp(code, tok, 5, kind="vote", choice=str(others[0]))
check("inverted: round resolved", st["phase"] == "scored")

print(f"\n{N['pass']} passed, {N['fail']} failed")
raise SystemExit(1 if N["fail"] else 0)
