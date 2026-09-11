#!/usr/bin/env python3
"""Mafia: secret roles, firewall observations, night/day, receipts."""

import json

from game_runtime import GameRun, _count, deal_roles

# Vendored from the killella-side handoff (they own GAME packs, we own
# SHOW packs). Do not edit here — take updates from their push.
PACK = json.load(open("game-packs/mafia.freak-game.json"))
PIDS = ["agent:a", "agent:b", "human:c", "agent:d", "human:e",
        "agent:f", "human:g", "agent:h"]


class TestDeal:
    def test_counts(self):
        assert _count("floor(n/4)", 8, 0) == 2
        assert _count("1", 8, 2) == 1
        assert _count("rest", 8, 3) == 5

    def test_deterministic(self):
        assert (deal_roles(PACK, PIDS, 4) ==
                deal_roles(PACK, PIDS, 4))
        assert (deal_roles(PACK, PIDS, 4) !=
                deal_roles(PACK, PIDS, 5))

    def test_composition_8(self):
        from collections import Counter
        c = Counter(deal_roles(PACK, PIDS, 1).values())
        assert c == {"mafia": 2, "doctor": 1, "civilian": 5}


class TestFirewall:
    def test_civilian_obs_has_no_roles(self):
        g = GameRun(PACK, PIDS, seed=1)
        for pid in PIDS:
            if g.roles[pid] == "civilian" and pid in g.alive:
                blob = json.dumps(g.observe(pid))
                # names are public (alive list); role mappings are not.
                # own role lives under "your_role" — no "role" key exists.
                assert '"role":' not in blob
                assert "known_fellows" not in g.observe(pid)
                break

    def test_mafia_see_each_other_only(self):
        g = GameRun(PACK, PIDS, seed=1)
        maf = [p for p in PIDS if g.roles[p] == "mafia"]
        assert len(maf) == 2
        obs = g.observe(maf[0])
        assert obs["known_fellows"] == [maf[1]]
        # doctor identity stays hidden even from mafia: no "role" key
        # anywhere in a live observation (names in alive list are public)
        assert '"role":' not in json.dumps(obs)

    def test_dead_role_revealed_to_all(self):
        g = GameRun(PACK, PIDS, seed=1)
        victim = next(p for p in PIDS if g.roles[p] == "civilian")
        g.night(victim)
        for pid in PIDS:
            assert g.observe(pid)["dead"][victim]["role"] == "civilian"


class TestFlow:
    def test_night_save_and_kill(self):
        g = GameRun(PACK, PIDS, seed=2)
        maf = [p for p in PIDS if g.roles[p] == "mafia"]
        doc = next(p for p in PIDS if g.roles[p] == "doctor")
        civ = next(p for p in PIDS if g.roles[p] == "civilian")
        assert g.night(civ, doctor_save=civ)["killed"] is None
        assert g.night(civ)["killed"] == civ

    def test_vote_eliminate_and_tie_stands(self):
        g = GameRun(PACK, PIDS, seed=3)
        alive = sorted(g.alive)
        # all vote alive[0] except self
        votes = {p: alive[0] for p in alive if p != alive[0]}
        assert g.day_vote(votes)["eliminated"] == alive[0]
        # tie: two blocs
        rest = sorted(g.alive)
        votes = {rest[0]: rest[1], rest[1]: rest[0]}
        assert g.day_vote(votes)["eliminated"] is None

    def test_win_conditions(self):
        g = GameRun(PACK, PIDS, seed=4)
        assert g.winner() is None
        for p in [x for x in PIDS if g.roles[x] == "mafia"]:
            g.alive.discard(p)
            g.dead[p] = {"round": "day", "cause": "vote"}
        assert g.winner() == "civilians"

    def test_receipt(self):
        g = GameRun(PACK, PIDS, seed=5)
        g.night(next(p for p in PIDS if g.roles[p] == "civilian"))
        r = g.receipt(g.winner())
        assert r["schema"] == "freaktown.receipt/v1"
        assert r["format"]["format_id"]
        assert r["event_log_root"] == g.events[-1]["hash"]
