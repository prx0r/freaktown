"""Contract: every party game plays end to end, plus the edge cases.

In-process (Flask test client), no browser, no network, no spend. Each
"phone" only acts on the screen its own /view hands it, the way the real
controller page does, so these tests also hold the view contract.
"""
import json
import random

import pytest

import party
from app import app

QUIP_DECKS = sorted(party.QC_DECKS)
WORDS = party.WORDS


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(party, "ROOMS_FILE", tmp_path / "rooms.json")
    monkeypatch.setattr(party, "RECORDS_FILE", tmp_path / "records.json")
    monkeypatch.setattr(party, "PARTY_LOG", tmp_path / "events.jsonl")
    monkeypatch.setenv("PARTY_TTS", "0")
    yield


@pytest.fixture
def c():
    return app.test_client()


class Clock:
    """Controls party._now so timers can expire without sleeping."""

    def __init__(self, monkeypatch):
        self.t = 1_900_000_000.0
        monkeypatch.setattr(party, "_now", lambda: self.t)

    def jump(self, s):
        self.t += s


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


def j(resp):
    return json.loads(resp.data)


class Room:
    def __init__(self, c):
        self.c = c
        d = j(c.post("/party/create"))
        self.code, self.host_tok = d["code"], d["host_token"]

    def host(self, cmd, **kw):
        r = self.c.post(f"/party/{self.code}/host",
                        json={"host_token": self.host_tok, "cmd": cmd, **kw})
        return r.status_code, j(r)

    def join(self, name, tok=""):
        body = {"name": name, "freak": f"Freak {name}"}
        if tok:
            body["seat_token"] = tok
        return j(self.c.post(f"/party/{self.code}/join", json=body))

    def snap(self):
        return j(self.c.get(f"/party/{self.code}/stream",
                            query_string={"last_seq": 0, "once": 1}))

    @property
    def state(self):
        return party.ROOMS[self.code]


class Phone:
    def __init__(self, room, name):
        self.room, self.name = room, name
        d = room.join(name)
        assert d["role"] == "player"
        self.tok = d["seat_token"]
        self.n = 0
        self.sent = set()
        self.rng = random.Random(name)
        self.guessed = set()

    def view(self):
        return j(self.room.c.get(f"/party/{self.room.code}/view",
                                 query_string={"seat_token": self.tok}))["view"]

    def inp(self, kind, **kw):
        self.n += 1
        r = self.room.c.post(f"/party/{self.room.code}/input",
                             json={"seat_token": self.tok,
                                   "client_seq": f"{self.name}-{self.n}",
                                   "kind": kind, **kw})
        return r.status_code, j(r)

    def leave(self):
        return j(self.room.c.post(f"/party/{self.room.code}/leave",
                                  json={"seat_token": self.tok}))

    def act(self):
        v = self.view()
        comps = v.get("components") or []
        if v["screen"] == "drawer":
            party.ROOMS[self.room.code]["players"]
            for p in party.ROOMS[self.room.code]["players"].values():
                p["last_draw"], p["draw_times"] = 0.0, []  # skip the flood guard in-process
            return self.inp("draw.batch", points=[[0.1, 0.2], [0.4, 0.5]])[1].get("ok")
        sub = next((x for x in comps if x["type"] == "submit"), None)
        if sub:
            kind = sub.get("kind")
            assert kind, f"submit without kind on {v['mode']}"
            if kind == "guess":
                w = self.rng.choice([w for w in WORDS if w not in self.guessed] or WORDS)
                self.guessed.add(w)
                return self.inp("guess", text=w)[1].get("ok")
            text = f"{self.name} {kind} {self.rng.randint(0, 9999)}"
            extra = {"truth": True} if any(x["type"] == "toggle" for x in comps) else {}
            ok = self.inp(kind, text=text, **extra)[1].get("ok")
            assert ok, (v["mode"], kind)
            self.sent.add(text)
            return True
        ch = next((x for x in comps if x["type"] == "choice"), None)
        if ch:
            act = ch.get("action") or {"kind": "vote", "as": "choice"}
            opts = [o for o in ch["options"] if o["text"] not in self.sent] or ch["options"]
            if (act.get("multi") or 1) > 1:
                ok = self.inp(act["kind"], choices=[o["id"] for o in opts[:2]])[1].get("ok")
            else:
                ok = self.inp(act["kind"], **{act["as"]: self.rng.choice(opts)["id"]})[1].get("ok")
            assert ok, (v["mode"], act)
            return True
        return False


def play_to_end(room, phones, max_ticks=400):
    for _ in range(max_ticks):
        if room.state["phase"] == "done":
            return True
        did = any([p.act() for p in phones])
        st = room.state.get("mode_state") or {}
        if room.state["phase"] == "done":
            return True
        if not did:
            if st.get("phase") in ("scored", "revealed", "drawing"):
                room.host("advance")
    return room.state["phase"] == "done"


def setup(c, n, bots=0, lock=True):
    room = Room(c)
    phones = [Phone(room, f"P{i}") for i in range(n)]
    if bots:
        assert room.host("bots", n=bots)[1]["ok"]
    if lock:
        room.host("lock")
    return room, phones


def assert_finished(room, end_kind):
    s = room.snap()
    kinds = [e["kind"] for e in s["events"]]
    assert s["snapshot"]["room_phase"] == "done"
    assert end_kind in kinds
    res = s["snapshot"].get("result")
    if res is None:  # freeze-night crowns through its own finale
        assert s["snapshot"]["champion"] and room.state["winner"]
        return
    assert res["kind"] in ("win", "tie", "none")
    if res["kind"] == "win":  # a champion only when one player leads alone
        assert s["snapshot"]["champion"] == res["names"][0]
        assert room.state["winner"]
    else:
        assert not s["snapshot"].get("champion") and not room.state["winner"]


# ── one full game per game ────────────────────────────────────────────

def test_freaktionary_full_game(c):
    room, phones = setup(c, 4)
    code, r = room.host("start", mode="freaktionary")
    assert r["ok"] and r["rounds"] == 4
    assert play_to_end(room, phones)
    assert_finished(room, "game.done")
    assert room.state["mode_state"]["round"] == 4  # everyone drew once


def test_freaktionary_with_bots(c):
    room, phones = setup(c, 2, bots=2)
    assert room.host("start", mode="freaktionary")[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "game.done")


def test_roast_relay_full_game(c):
    room, phones = setup(c, 4)
    assert room.host("start", mode="roast-relay", target="the group chat")[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "game.done")
    assert room.state["mode_state"]["round"] == 3


def test_roast_relay_with_bots(c):
    room, phones = setup(c, 1, bots=2)
    assert room.host("start", mode="roast-relay")[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "game.done")


def test_freeze_night_full_game(c):
    room, phones = setup(c, 4)
    assert room.host("start", mode="freeze-night")[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "night.done")
    assert room.state["mode_state"]["ri"] >= len(party.FZ_ROUNDS)


@pytest.mark.parametrize("deck", QUIP_DECKS)
def test_quip_full_game(c, deck):
    room, phones = setup(c, 3)
    assert room.host("start", mode=f"quip-{deck}")[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "game.done")
    assert room.state["mode_state"]["round"] == party.DEFAULT_ROUNDS["quip"]


@pytest.mark.parametrize("pack", sorted(party.PACKS))
def test_pack_full_night(c, pack):
    room, phones = setup(c, 4)
    assert room.host("start", pack=pack)[1]["ok"]
    assert play_to_end(room, phones)
    assert_finished(room, "pack.done")


def test_play_again_resets_and_lobby_returns(c):
    room, phones = setup(c, 3)
    room.host("start", mode="quip-endings", rounds=1)
    assert play_to_end(room, phones)
    assert any(p["score"] for p in room.state["players"].values())
    code, r = room.host("start", mode="quip-endings", rounds=1)
    assert r["ok"] and room.state["phase"] == "playing"
    assert all(p["score"] == 0 for p in room.state["players"].values())
    assert play_to_end(room, phones)
    code, r = room.host("lobby")
    assert r["ok"] and room.state["phase"] == "lobby" and not room.state["locked"]
    assert phones[0].view()["screen"] == "lobby"
    # the lobby is open again: a new friend can sit down
    assert room.join("Late")["role"] == "player"


def test_done_screen_on_phone(c):
    room, phones = setup(c, 2)
    room.host("start", mode="quip-endings", rounds=1)
    assert play_to_end(room, phones)
    v = phones[0].view()
    assert v["screen"] == "scores"
    assert any("GAME OVER" in x.get("text", "") for x in v["components"])


# ── bugs fixed (regressions) ─────────────────────────────────────────

def test_vote_targets_option_ids_not_positions(c, clock):
    """Seat 1 wrote nothing: option ids are 0,2,3. Voting id 3 must work and
    voting the empty seat's id 1 must not score a player with no entry."""
    room, ph = setup(c, 4)
    room.host("start", mode="quip-endings")
    for i in (0, 2, 3):
        ph[i].inp("entry", text=f"entry {i}")
    clock.jump(91)
    ph[0].view()  # lazy timer: collecting -> voting with 3 options
    assert room.state["mode_state"]["phase"] == "voting"
    assert ph[0].inp("vote", choice="1")[1]["ok"] is False
    assert ph[0].inp("vote", choice="3")[1]["ok"] is True


def test_roast_vote_rejects_empty_seat(c, clock):
    room, ph = setup(c, 3)
    room.host("start", mode="roast-relay")
    ph[0].inp("line", text="a")
    ph[2].inp("line", text="c")
    clock.jump(91)
    ph[0].view()
    assert room.state["mode_state"]["phase"] == "voting"
    assert ph[0].inp("vote", choice="1")[1]["ok"] is False
    assert ph[0].inp("vote", choice="2")[1]["ok"] is True


def test_callback_marker_does_not_reveal_early(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freeze-night")
    st = room.state["mode_state"]
    st["archive"].append({"id": "e1", "round": "x", "by": "P1", "text": "t",
                          "invokes": 0})
    ph[0].inp("entry", text="with a callback", callback="e1")
    ph[1].inp("entry", text="second")
    assert st["phase"] == "collecting"  # 2 of 3 wrote; the :cb key isn't a player
    ph[2].inp("entry", text="third")
    assert st["phase"] == "voting"


def test_ritual_line_from_phone_entry_kind(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freeze-night")
    st = room.state["mode_state"]
    while st["kind"] != "humiliation-ritual":
        room.host("advance")
    victim = st["ritual"]["victim"]
    writers = [p for p in ph if room.state["players"]
               [next(k for k, v in room.state["players"].items() if v["token"] == p.tok)]["id"] != victim]
    v = writers[0].view()
    sub = next(x for x in v["components"] if x["type"] == "submit")
    assert sub["kind"] == "rite"
    assert writers[0].inp("entry", text="legacy kind still lands")[1]["ok"]


def test_last_lash_accepts_choices_only(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freeze-night")
    st = room.state["mode_state"]
    while st["kind"] != "last-lash" or st["phase"] != "collecting":
        room.host("advance")
    for i, p in enumerate(ph):
        p.inp("entry", text=f"epitaph {i}")
    assert st["phase"] == "voting"
    code, r = ph[0].inp("vote", choices=["0", "1"])  # what the phone sends
    assert r["ok"], r


def test_inverted_zero_votes_wins(c):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-least-funny")
    for i, p in enumerate(ph):
        p.inp("entry", text=f"bad {i}")
    # P0 -> 1, P1 -> 0, P2 -> 0: seat 2 got no votes = least funny
    ph[0].inp("vote", choice="1")
    ph[1].inp("vote", choice="0")
    ph[2].inp("vote", choice="0")
    st = room.state["mode_state"]
    assert st["phase"] == "scored"
    scores = [p["score"] for p in room.state["players"].values()]
    assert scores[2] == party.FZ_POOL and scores[0] == 0 and scores[1] == 0


def test_freaktionary_reveal_screen_after_win(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary")
    word = room.state["mode_state"]["word"]
    assert ph[1].inp("guess", text=word.upper() + "!")[1]["correct"] is True
    v = ph[2].view()
    assert v["screen"] == "reveal"
    assert any(word in x.get("text", "") for x in v["components"])


def test_client_seq_after_reload_not_swallowed(c):
    """A reloaded phone restarts its counter; string seqs keep inputs alive."""
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings")
    r = c.post(f"/party/{room.code}/input",
               json={"seat_token": ph[0].tok, "client_seq": 1, "kind": "entry", "text": "a"})
    assert j(r)["ok"]
    r = c.post(f"/party/{room.code}/input",
               json={"seat_token": ph[0].tok, "client_seq": "1730000000000-1",
                     "kind": "entry", "text": "b"})
    assert j(r)["ok"] and not j(r).get("dup")


# ── edge cases ────────────────────────────────────────────────────────

def test_leave_mid_round_and_rejoin_with_token(c):
    room, ph = setup(c, 4)
    room.host("start", mode="quip-endings")
    st = room.state["mode_state"]
    for p in ph[:3]:
        p.inp("entry", text=f"{p.name} line")
    assert st["phase"] == "collecting"
    assert ph[3].leave()["ok"]
    assert st["phase"] == "voting"  # nobody waits on the seat that left
    assert ph[3].inp("vote", choice="0")[0] == 409
    for i, p in enumerate(ph[:3]):
        p.inp("vote", choice=str((i + 1) % 3))
    assert st["phase"] == "scored"
    r = room.join("ignored", tok=ph[3].tok)
    assert r["reconnected"] and r["role"] == "player"
    room.host("advance")
    assert st["phase"] == "collecting"
    assert ph[3].inp("entry", text="back")[1]["ok"]


def test_leave_drawer_reveals(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary")
    assert ph[0].leave()["ok"]  # P0 is round-1 drawer
    assert room.state["mode_state"]["phase"] == "revealed"


def test_leave_during_freeze_votes_and_ritual(c):
    room, ph = setup(c, 4)
    room.host("start", mode="freeze-night")
    st = room.state["mode_state"]
    for i, p in enumerate(ph):
        p.inp("entry", text=f"e{i}")
    for i, p in enumerate(ph[:3]):
        p.inp("vote", choice=str((i + 1) % 4))
    assert st["phase"] == "voting"
    ph[3].leave()
    assert st["phase"] == "scored"
    assert play_to_end(room, ph[:3])


def test_everyone_leaves_ends_game(c):
    room, ph = setup(c, 3)
    room.host("start", mode="roast-relay")
    ph[0].leave()
    assert room.state["phase"] == "playing"
    ph[1].leave()
    assert room.state["phase"] == "done"


def test_lobby_leave_frees_seat(c):
    room = Room(c)
    p = Phone(room, "A")
    Phone(room, "B")
    assert p.leave()["freed"] is True
    assert len(room.state["players"]) == 1


@pytest.mark.parametrize("mode", ["freaktionary", "roast-relay", "freeze-night", "quip-endings"])
def test_timers_expire_without_input(c, clock, mode):
    """Nobody touches a phone: deadlines still move the game, driven only by
    the stage polling /stream, until a winner is crowned."""
    room, ph = setup(c, 3)
    room.host("start", mode=mode)
    for _ in range(80):
        if room.state["phase"] == "done":
            break
        clock.jump(95)
        room.snap()
    assert room.state["phase"] == "done", room.state["mode_state"].get("phase")


def test_timer_with_partial_input(c, clock):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings")
    ph[0].inp("entry", text="only me")
    ph[1].inp("entry", text="and me")
    clock.jump(91)
    room.snap()
    st = room.state["mode_state"]
    assert st["phase"] == "voting" and len(party._qc_assembled(room.state)) == 2
    ph[0].inp("vote", choice="1")
    ph[1].inp("vote", choice="0")
    ph[2].inp("vote", choice="0")
    assert st["phase"] == "scored"


def test_host_disconnect_room_keeps_going(c, clock):
    """Host stage closes after start: phones alone finish the game."""
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings", rounds=2)
    for _ in range(60):
        if room.state["phase"] == "done":
            break
        if not any([p.act() for p in ph]):
            clock.jump(party.SCORED_HOLD + 1)
    assert room.state["phase"] == "done"


def test_host_token_survives_restart(c):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings")
    party._save_rooms()
    party.ROOMS.clear()
    party._load_rooms()
    assert room.host("advance")[1]["ok"]
    assert ph[0].view()["phase"] == "playing"


@pytest.mark.parametrize("mode,need", [("freaktionary", 2), ("quip-endings", 2),
                                       ("roast-relay", 3), ("freeze-night", 3)])
def test_minimum_players(c, mode, need):
    room = Room(c)
    phones = [Phone(room, "Solo")]
    code, r = room.host("start", mode=mode)
    assert code == 400 and r["need"] == need
    phones.append(Phone(room, "Two"))  # 2 humans
    if need > 2:
        code, r = room.host("start", mode=mode)
        assert code == 400  # 2 humans is not enough here
        assert room.host("bots", n=need - len(phones))[1]["ok"]
    assert room.host("start", mode=mode)[1]["ok"]
    assert play_to_end(room, phones)


def test_two_player_freaktionary_and_quip_finish(c):
    for mode in ("freaktionary", "quip-endings"):
        room, ph = setup(c, 2)
        assert room.host("start", mode=mode)[1]["ok"]
        assert play_to_end(room, ph)


def test_mid_game_join_is_audience(c):
    room, ph = setup(c, 3, lock=False)
    room.host("start", mode="quip-endings")
    assert room.join("Late")["role"] == "audience"


BAD_BODIES = [None, "not json", "[]", "[1,2]", "42", '"str"', '{"kind": null}',
              '{"seat_token": ["x"], "client_seq": {"a": 1}, "kind": ["vote"]}',
              '{"choice": {"x": 1}, "choices": "abc", "text": 12345}',
              '{"points": [[1e999, "x"], [null], "zz"]}']


def test_bad_input_never_500(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freeze-night")
    tok = ph[0].tok
    paths = [f"/party/{room.code}/input", f"/party/{room.code}/host",
             f"/party/{room.code}/join", f"/party/{room.code}/ready",
             f"/party/{room.code}/leave", "/party/NOPE00/input"]
    for path in paths:
        for b in BAD_BODIES:
            r = c.post(path, data=b, content_type="application/json")
            assert r.status_code < 500, (path, b, r.status_code)
            r = c.post(path, data=b, content_type="text/plain")
            assert r.status_code < 500, (path, b, r.status_code)
    weird = [{"kind": "vote", "choice": {"x": 1}}, {"kind": "vote", "choices": [None, "9", -1]},
             {"kind": "entry", "text": ["list"]}, {"kind": "caught", "event": None},
             {"kind": "pass", "verdict": ["pass"]}, {"kind": "author", "player_id": {"a": 1}},
             {"kind": "verdict", "verdict": 1}, {"kind": "draw.batch", "points": "x"},
             {"kind": "guess", "text": None}, {"kind": "line", "text": "x" * 10000},
             {"kind": "entry", "callback": ["e1"], "text": "x"}]
    for body in weird:
        r = c.post(f"/party/{room.code}/input",
                   json={"seat_token": tok, "client_seq": json.dumps(body), **body})
        assert r.status_code < 500, (body, r.status_code)
    for cmd in [{"cmd": "start", "mode": ["x"]}, {"cmd": "start", "deck": {"a": 1}, "mode": "quip-lies"},
                {"cmd": "bots", "n": "lots"}, {"cmd": "start", "rounds": "many", "mode": "quip-dubs"},
                {"cmd": ["advance"]}, {"cmd": "start", "pack": ["x"]}, {"cmd": "reject", "player_id": [1]}]:
        r = c.post(f"/party/{room.code}/host", json={"host_token": room.host_tok, **cmd})
        assert r.status_code < 500, (cmd, r.status_code)
    assert c.get(f"/party/{room.code}/view?seat_token[]=x").status_code < 500
    assert c.get(f"/party/{room.code}/stream?last_seq=abc&once=1").status_code < 500
    assert c.get("/join/<script>").status_code < 500
    page = c.get("/join/<script>alert(1)</script>").data
    assert b"alert(1)" not in page  # room code is sanitized into the page


def test_secrets_stay_off_the_stream(c):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-lies")
    for p in ph:
        p.inp("entry", text=f"{p.name} claim", truth=True)
    s = json.dumps(room.snap())
    assert '"secrets": {' not in s.replace('"secrets": null', "")


def test_stage_has_a_start_button_for_every_game(c):
    room = Room(c)
    html = c.get(f"/party/{room.code}/stage").data.decode()
    for mode in party.MODES:
        assert f'"id": "{mode}"' in html
    for pack in party.PACKS:
        assert pack in html


# ── real-phone playability: round flow, honest results, stroke sync ──

def _stage_key(room):
    return room.snap()["snapshot"]["phase_key"]


def test_every_freaktionary_round_is_a_live_drawing_turn(c, clock):
    """Each round opens in a drawing phase with a new drawer; NEXT ROUND
    from the reveal starts the next drawing, never its reveal."""
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary")
    drawers = []
    for rnd in (1, 2, 3):
        st = room.state["mode_state"]
        assert st["round"] == rnd and st["phase"] == "drawing"
        drawers.append(st["drawer"])
        clock.jump(10)
        assert room.host("advance", expect=_stage_key(room))[1]["ok"]  # skip
        assert room.state["mode_state"]["phase"] == "revealed"
        clock.jump(3)
        assert room.host("advance", expect=_stage_key(room))[1]["ok"]  # next
    assert len(set(drawers)) == 3  # everyone drew once, in turn
    assert room.state["phase"] == "done"


def test_stale_or_double_advance_never_skips_a_round(c, clock):
    room, ph = setup(c, 2)
    room.host("start", mode="freaktionary")
    word = room.state["mode_state"]["word"]
    ph[1].inp("guess", text=word)
    key_reveal = _stage_key(room)
    clock.jump(3)
    assert room.host("advance", expect=key_reveal)[1]["ok"]
    assert room.state["mode_state"]["phase"] == "drawing"
    # the same click again (double click / sent from the old screen)
    code, r = room.host("advance", expect=key_reveal)
    assert code == 409 and r["stale"]
    # the stage already shows round 2 but the round only just began
    code, r = room.host("advance", expect=_stage_key(room))
    assert code == 409 and r["error"] == "just started"
    st = room.state["mode_state"]
    assert st["round"] == 2 and st["phase"] == "drawing"
    clock.jump(8)  # a deliberate skip later on is allowed
    assert room.host("advance", expect=_stage_key(room))[1]["ok"]
    assert room.state["mode_state"]["phase"] == "revealed"


def test_timer_reveal_then_late_click_keeps_round_two(c, clock):
    """The reveal auto-advances; a click aimed at the reveal lands late."""
    room, ph = setup(c, 2)
    room.host("start", mode="freaktionary")
    ph[1].inp("guess", text=room.state["mode_state"]["word"])
    key_reveal = _stage_key(room)
    clock.jump(party.SCORED_HOLD + 1)
    room.snap()  # stage poll drives the timer: round 2 starts
    assert room.state["mode_state"]["round"] == 2
    code, _ = room.host("advance", expect=key_reveal)
    assert code == 409
    assert room.state["mode_state"]["phase"] == "drawing"


def test_no_score_game_names_nobody(c, clock):
    room, ph = setup(c, 2)
    room.host("start", mode="freaktionary")
    for _ in range(2):
        room.host("advance")  # reveal, nobody guessed
        room.host("advance")  # next
    s = room.snap()["snapshot"]
    assert s["room_phase"] == "done"
    assert s["result"]["kind"] == "none" and s["result"]["headline"] == "NOBODY SCORED"
    assert not s.get("champion") and not room.state["winner"]
    texts = [x.get("text", "") for x in ph[0].view()["components"]]
    assert "NOBODY SCORED" in " ".join(texts) and not any("WINS" in t for t in texts)


def test_tie_is_a_tie(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary")
    for p in room.state["players"].values():
        p["score"] = 5
    room.host("end")
    res = room.snap()["snapshot"]["result"]
    assert res["kind"] == "tie" and len(res["names"]) == 3
    assert res["headline"].startswith("IT'S A TIE")
    assert room.state["winner"] is None
    rows = [x["text"] for x in ph[0].view()["components"] if ": 5" in x.get("text", "")]
    assert len(rows) == 3 and all(r.startswith("🥇") for r in rows)  # ties share gold


def test_clear_winner_named_once(c):
    room, ph = setup(c, 2)
    room.host("start", mode="freaktionary")
    ph[1].inp("guess", text=room.state["mode_state"]["word"])  # P1 +2, P0 +1
    room.host("end")
    s = room.snap()["snapshot"]
    assert s["result"]["kind"] == "win" and s["champion"] == "P1"
    assert "P1 WINS!" in json.dumps(ph[0].view()["components"])


def test_strokes_join_and_reach_guessers_and_stage(c):
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary")
    drawer = next(p for p in ph if p.view()["screen"] == "drawer")
    guesser = next(p for p in ph if p is not drawer)
    pts = [[i / 100, 0.5] for i in range(10, 60)]
    for k in range(0, 50, 10):  # one stroke, five ~150 ms batches
        assert drawer.inp("draw.batch", stroke="s1", points=pts[k:k + 10])[1]["ok"]
    assert drawer.inp("draw.batch", stroke="s2", points=[[0.2, 0.2], [0.3, 0.3]])[1]["ok"]
    v = guesser.view()
    assert v["screen"] == "guess"
    assert any(x["type"] == "canvas" and x.get("readonly") for x in v["components"])
    assert any(x["type"] == "textarea" for x in v["components"])
    strokes = v["freaktionary"]["strokes"]
    assert [len(s["points"]) for s in strokes] == [50, 2]  # continuous, not dots
    stage = room.snap()["snapshot"]["freaktionary"]
    assert stage["strokes"] == strokes and stage["rev"] == v["freaktionary"]["rev"]
    assert "word" not in json.dumps(stage) or stage["word"] is None  # secret kept
    assert guesser.inp("draw.batch", stroke="x", points=[[0.1, 0.1]])[1]["ok"] is False
    assert drawer.inp("draw.clear")[1]["ok"]
    after = room.snap()["snapshot"]["freaktionary"]
    assert after["strokes"] == [] and after["rev"] != stage["rev"]


def test_drawing_stays_on_reveal_and_rules_are_shown(c):
    room, ph = setup(c, 2)
    room.host("start", mode="freaktionary")
    ph[0].inp("draw.batch", stroke="a", points=[[0.1, 0.1], [0.9, 0.9]])
    assert any("+2" in x.get("text", "") for x in ph[1].view()["components"])
    ph[1].inp("guess", text=room.state["mode_state"]["word"])
    v = ph[1].view()
    assert v["screen"] == "reveal"
    assert any(x["type"] == "canvas" for x in v["components"])
    assert v["freaktionary"]["strokes"]


def test_words_and_prompts_do_not_repeat_in_a_game(c, clock):
    room, ph = setup(c, 3)
    room.host("start", mode="freaktionary", rounds=6)
    seen = []
    for _ in range(6):
        seen.append(room.state["mode_state"]["word"])
        room.host("advance"); room.host("advance")
    assert len(set(seen)) == 6
    room2, ph2 = setup(c, 3)
    room2.host("start", mode="quip-endings", rounds=3)
    prompts = []
    for _ in range(3):
        prompts.append(room2.state["mode_state"]["prompt"])
        for p in ph2:
            p.inp("entry", text=f"{p.name} {len(prompts)}")
        room2.host("advance"); room2.host("advance")
    assert len(set(prompts)) == 3


def test_quip_results_explain_the_score(c):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings", rounds=1)
    v = ph[0].view()
    assert any("Most votes wins" in x.get("text", "") for x in v["components"])
    for p in ph:
        p.inp("entry", text=f"{p.name} ending")
    opts = {o["text"]: o["id"] for o in ph[1].view()["components"][1]["options"]}
    ph[1].inp("vote", choice=opts["P0 ending"])
    opts2 = {o["text"]: o["id"] for o in ph[2].view()["components"][1]["options"]}
    ph[2].inp("vote", choice=opts2["P0 ending"])
    opts0 = ph[0].view()["components"][1]["options"]
    ph[0].inp("vote", choice=opts0[0]["id"])
    q = room.snap()["snapshot"]["quip"]
    assert q["phase"] == "scored" and q["round_winner"] == "P0"
    top = q["results"][0]
    assert top["by"] == "P0" and top["votes"] == 2 and top["points"] > 0
    assert "Round 1 results" in json.dumps(ph[1].view()["components"])


def test_quip_skipping_an_empty_prompt_keeps_the_round(c, clock):
    room, ph = setup(c, 3)
    room.host("start", mode="quip-endings", rounds=2)
    first = room.state["mode_state"]["prompt"]
    clock.jump(10)
    assert room.host("advance", expect=_stage_key(room))[1]["ok"]
    st = room.state["mode_state"]
    assert room.state["phase"] == "playing" and st["round"] == 1
    assert st["phase"] == "collecting" and st["prompt"] != first


def test_play_again_keeps_rounds_and_clears_result(c):
    room, ph = setup(c, 2)
    room.host("start", mode="quip-endings", rounds=2)
    assert play_to_end(room, ph)
    assert room.snap()["snapshot"]["result"]
    room.host("start", mode="quip-endings", rounds=2)
    s = room.snap()["snapshot"]
    assert s["rounds"] == 2 and "result" not in s and s["room_phase"] == "playing"


def test_stage_page_separates_next_round_from_skip(c):
    room = Room(c)
    html = c.get(f"/party/{room.code}/stage").data.decode()
    assert "data-testid=advance" in html and "data-testid=skip" in html
    assert "expect" in html  # stage sends the screen it is looking at
    phone = c.get(f"/party/{room.code}/play").data.decode()
    assert "setPointerCapture" in phone and "touch-action:none" in phone
    assert "localStorage.setItem(dk" in phone  # drafts survive reloads
