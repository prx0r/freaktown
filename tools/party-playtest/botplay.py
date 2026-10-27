#!/usr/bin/env python3
"""Real-HTTP bot players for Freak Town party games.

Each "phone" is a client that only does what a phone can: GET its /view and
act on the screen it is shown (components), via POST /input. The "stage"
polls /stream and the host POSTs /host commands. Plays every game to a
winner, then play-again, then back to the lobby.

usage: python3 botplay.py [BASE_URL] [scenario ...]
"""
import json
import random
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8090"
ARGS = [a for a in sys.argv[1:] if not a.startswith("http")]
WORDS = ["air fryer", "traffic cone", "divorce court", "pigeon", "Tesco",
         "haunted Roomba", "LinkedIn", "cryptocurrency", "dentist", "karaoke"]
RESULTS = []
# local server: never route through the sandbox HTTP(S)_PROXY
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))


def req(method, path, body=None, expect_json=True):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw, code = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    if not expect_json:
        return code, raw
    try:
        return code, json.loads(raw)
    except Exception:
        return code, {"_raw": raw[:200].decode(errors="replace")}


class Phone:
    def __init__(self, code, name, freak):
        self.code, self.name = code, name
        _, d = req("POST", f"/party/{code}/join", {"name": name, "freak": freak})
        assert d.get("ok") and d["role"] == "player", d
        self.tok = d["seat_token"]
        self.seq = 0
        self.sent = set()
        self.rng = random.Random(name)
        self.guessed = set()

    def view(self):
        _, d = req("GET", f"/party/{self.code}/view?seat_token={self.tok}")
        return d["view"]

    def inp(self, kind, **kw):
        self.seq += 1
        body = {"seat_token": self.tok, "client_seq": f"{self.name}-{self.seq}",
                "kind": kind, **kw}
        return req("POST", f"/party/{self.code}/input", body)[1]

    def act(self):
        """Do whatever the current screen asks. Returns a short action tag."""
        v = self.view()
        scr, comps = v.get("screen"), v.get("components") or []
        if scr == "lobby":
            if not (v.get("you") or {}).get("ready"):
                req("POST", f"/party/{self.code}/ready", {"seat_token": self.tok})
                return "ready"
            return None
        if scr == "drawer":
            time.sleep(0.06)
            pts = [[round(self.rng.random(), 3), round(self.rng.random(), 3)] for _ in range(8)]
            r = self.inp("draw.batch", points=pts)
            return "draw" if r.get("ok") else None
        sub = next((c for c in comps if c["type"] == "submit"), None)
        if sub:
            kind = sub.get("kind") or "entry"
            if kind == "guess":
                left = [w for w in WORDS if w not in self.guessed] or WORDS
                w = self.rng.choice(left)
                self.guessed.add(w)
                r = self.inp("guess", text=w)
                return "guess-hit" if r.get("correct") else "guess"
            text = f"{self.name}'s {kind} #{self.rng.randint(100, 999)} about soup"
            extra = {}
            if any(c["type"] == "toggle" for c in comps):
                extra["truth"] = self.rng.random() < 0.5
            r = self.inp(kind, text=text, **extra)
            if r.get("ok"):
                self.sent.add(text)
                return kind
            return f"{kind}-rejected:{r.get('error')}"
        ch = next((c for c in comps if c["type"] == "choice"), None)
        if ch:
            act = ch.get("action") or {"kind": "vote", "as": "choice"}
            opts = [o for o in ch["options"] if o["text"] not in self.sent] or ch["options"]
            if not opts:
                return None
            if (act.get("multi") or 1) > 1:
                r = self.inp(act["kind"], choices=[o["id"] for o in opts[:2]])
            else:
                o = self.rng.choice(opts)
                r = self.inp(act["kind"], **{act["as"]: o["id"]})
            if r.get("ok"):
                return act["kind"]
            return f"{act['kind']}-rejected:{r.get('error')}"
        if any(c.get("id") == "rejoin" for c in comps):
            return None
        return None


class Host:
    def __init__(self):
        _, d = req("POST", "/party/create")
        self.code, self.tok = d["code"], d["host_token"]
        self.last_seq = 0
        self.events = []

    def cmd(self, cmd, **kw):
        return req("POST", f"/party/{self.code}/host", {"host_token": self.tok, "cmd": cmd, **kw})

    def poll(self):
        _, d = req("GET", f"/party/{self.code}/stream?last_seq={self.last_seq}&once=1")
        self.last_seq = d["seq"]
        self.events += d["events"]
        return d["snapshot"]


def sub_phase(snap):
    for k in ("freaktionary", "roast-relay", "quip", "freeze-night"):
        if snap.get(k):
            return k, snap[k].get("phase")
    return None, None


def play(host, phones, mode=None, pack=None, rounds=None, auto_advance=False,
         max_ticks=900, on_tick=None, **startkw):
    kw = dict(startkw)
    if rounds:
        kw["rounds"] = rounds
    if pack:
        kw["pack"] = pack
    code, r = host.cmd("start", mode=mode, **kw) if mode else host.cmd("start", **kw)
    assert r.get("ok"), (mode, pack, code, r)
    actions, phases, t0 = {}, [], time.time()
    stalled = 0
    for tick in range(max_ticks):
        snap = host.poll()
        if snap["room_phase"] == "done":
            break
        did = False
        for ph in phones:
            a = ph.act()
            if a:
                did = True
                actions[a] = actions.get(a, 0) + 1
        if on_tick:
            on_tick(tick, snap)
        snap = host.poll()
        k, p = sub_phase(snap)
        key = (k, (snap.get(k) or {}).get("round"), p)
        if not phases or phases[-1] != key:
            phases.append(key)
        if p in ("scored", "revealed") and not did:
            if auto_advance:
                time.sleep(0.5)
            else:
                host.cmd("advance")
        elif not did:
            stalled += 1
            if p == "drawing" and stalled > 40:
                host.cmd("advance")  # nobody guessed: let the timer's job be done
                stalled = 0
            else:
                time.sleep(0.05)
    snap = host.poll()
    return {"snap": snap, "actions": actions, "phases": phases,
            "secs": round(time.time() - t0, 1)}


def record(name, ok, **info):
    RESULTS.append({"scenario": name, "ok": bool(ok), **info})
    print(("PASS " if ok else "FAIL ") + name + "  " + json.dumps(info)[:400], flush=True)


def full_game(label, mode=None, n_humans=4, n_bots=0, pack=None, rounds=None, **kw):
    h = Host()
    phones = [Phone(h.code, f"{label[:6]}{i}", f"Freak {label[:5]} {i}") for i in range(n_humans)]
    for ph in phones:
        ph.act()  # ready up in the lobby
    if n_bots:
        assert h.cmd("bots", n=n_bots)[1].get("ok")
    h.cmd("lock")
    res = play(h, phones, mode=mode, pack=pack, rounds=rounds, **kw)
    snap = res["snap"]
    kinds = [e["kind"] for e in h.events]
    done = snap["room_phase"] == "done"
    end_ev = next((k for k in ("night.done", "pack.done", "game.done") if k in kinds), None)
    record(f"{label}: full game to a winner", done and bool(snap.get("champion")) and end_ev,
           champion=snap.get("champion"), end=end_ev, secs=res["secs"],
           actions=res["actions"], phase_changes=len(res["phases"]),
           scores={p["name"]: p["score"] for p in snap["scores"]})
    # play again (1 round, scores reset) then back to lobby
    if mode:
        res2 = play(h, phones, mode=mode, rounds=1 if mode != "freeze-night" else None, **kw)
        s2 = res2["snap"]
        record(f"{label}: play again", s2["room_phase"] == "done" and bool(s2.get("champion")),
               champion=s2.get("champion"), secs=res2["secs"])
    code, r = h.cmd("lobby")
    snap = h.poll()
    v = phones[0].view()
    record(f"{label}: back to lobby", r.get("ok") and snap["room_phase"] == "lobby"
           and v["screen"] == "lobby" and all(p["score"] == 0 for p in snap["scores"]))
    return h, phones


def main():
    only = set(ARGS)
    def want(n):
        return not only or n in only

    _, modes_html = req("GET", "/play", expect_json=False)
    if want("freaktionary"):
        full_game("freaktionary", "freaktionary", n_humans=4)
        full_game("freaktionary+bots", "freaktionary", n_humans=2, n_bots=2)
    if want("roast"):
        full_game("roast-relay", "roast-relay", n_humans=4, target="the group chat")
        full_game("roast-relay+bots", "roast-relay", n_humans=1, n_bots=2)
    if want("freeze"):
        full_game("freeze-night", "freeze-night", n_humans=4)
        full_game("freeze-night+bots", "freeze-night", n_humans=2, n_bots=2)
    if want("quip"):
        for deck in ["endings", "walkins", "objects", "least-funny", "wrong-answers",
                     "lies", "monologues", "dubs", "eulogies", "lyrics", "nonsense"]:
            full_game(f"quip-{deck}", f"quip-{deck}", n_humans=3)
        full_game("quip-lies+bots", "quip-lies", n_humans=1, n_bots=3)
    if want("pack"):
        full_game("pack FREAK NIGHT", pack="FREAK NIGHT", n_humans=4)
        full_game("pack QUICK FIRE", pack="QUICK FIRE", n_humans=3)
    if want("hostless"):
        # host never advances: scored screens auto-advance off the stage poll
        full_game("quip-endings hostless", "quip-endings", n_humans=3, rounds=2,
                  auto_advance=True)
    print(f"\n{sum(r['ok'] for r in RESULTS)} passed, {sum(not r['ok'] for r in RESULTS)} failed")
    json.dump(RESULTS, open("botplay_results.json", "w"), indent=1)
    raise SystemExit(0 if all(r["ok"] for r in RESULTS) else 1)


if __name__ == "__main__":
    main()
