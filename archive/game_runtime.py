#!/usr/bin/env python3
"""Hidden-info game runtime: game packs in, receipts out.

SHOW packs (format_runtime) are fully public: every score is visible.
GAME packs add exactly one thing: secrets. Roles are dealt, observations
are built PER PLAYER, and the firewall holds by construction — a civilian
observation object never contains another player's role, because the
builder never puts it there. No CSS hiding, no client-side filtering.

Deterministic given (pack bytes, participant order, seed, inputs).
"""

import hashlib
import json
import random
from datetime import datetime, timezone

from format_runtime import _canon, _now, _sha, git_commit


def _count(expr: str, n: int, assigned: int) -> int:
    expr = str(expr).strip()
    if expr == "rest":
        return max(0, n - assigned)
    if expr.startswith("floor(n/"):
        return max(0, n // int(expr[len("floor(n/"):-1]))
    return max(0, int(expr))


def deal_roles(pack: dict, participants: list[str], seed: int = 0) -> dict:
    """pid -> role id. Seeded shuffle, role counts from pack expressions."""
    n = len(participants)
    roles, assigned = [], 0
    for r in pack.get("roles", []):
        c = _count(r.get("count", "0"), n, assigned)
        roles.extend([r["id"]] * c)
        assigned = len(roles)
    roles = roles[:n]
    while len(roles) < n:
        roles.append((pack.get("roles") or [{"id": "civilian"}])[-1]["id"])
    rng = random.Random(f"{pack.get('id')}|{seed}")
    order = list(participants)
    rng.shuffle(order)
    return {pid: roles[i] for i, pid in enumerate(order)}


class GameRun:
    """One hidden-role game. The engine holds all secrets; each seat only
    ever receives its own observation."""

    def __init__(self, pack: dict, participants: list[str], seed: int = 0,
                 event_id: str = ""):
        self.pack = pack
        self.pids = list(participants)
        self.seed = seed
        self.event_id = event_id or f"evt_game_{_sha(str(seed))[:12]}"
        self.started_at = _now()
        self.roles = deal_roles(pack, self.pids, seed)
        self.knows = {r.get("id"): list(r.get("knows", []))
                      for r in pack.get("roles", [])}
        self.alive = set(self.pids)
        self.dead = {}  # pid -> {"round":, "cause":} (role revealed on death)
        self.events: list[dict] = []
        self._prev = "genesis"
        self.emit("game.opened", {"players": len(self.pids),
                                  "roles_dealt": True})

    def emit(self, kind: str, payload: dict):
        ev = {"seq": len(self.events) + 1, "type": kind,
              "prev": self._prev, "payload": payload}
        ev["hash"] = _sha(_canon(ev))
        self._prev = ev["hash"]
        self.events.append(ev)
        return ev

    def observe(self, pid: str) -> dict:
        """THE firewall: this dict is everything `pid` may know.
        Own role: yes. Mafia fellows (if mafia): yes. Anyone else's
        role: never present — not hidden, ABSENT."""
        if pid not in self.pids:
            raise ValueError("unknown player")
        role = self.roles[pid]
        obs = {"you": pid, "alive": sorted(self.alive),
               "dead": {p: {"role": self.roles[p], "cause": c["cause"]}
                        for p, c in self.dead.items()}}
        if pid in self.alive:
            obs["your_role"] = role
            fellows = [p for p in self.alive
                       if p != pid and self.roles[p] in self.knows.get(role, [])]
            if fellows:
                obs["known_fellows"] = sorted(fellows)
        else:
            obs["eliminated"] = True
        return obs

    def night(self, mafia_target: str | None,
              doctor_save: str | None = None) -> dict:
        """Resolve one night. Returns public outcome (no role info)."""
        target = mafia_target if mafia_target in self.alive else None
        saved = doctor_save if doctor_save in self.alive else None
        killed = target if target and target != saved else None
        if killed:
            self.alive.discard(killed)
            self.dead[killed] = {"round": "night", "cause": "mafia"}
        self.emit("night.resolved", {"killed": killed,
                                     "saved": saved == target and target is not None})
        return {"killed": killed}

    def day_vote(self, votes: dict[str, str]) -> dict:
        """votes: voter -> suspect (alive voters only, ties stand)."""
        tally: dict[str, int] = {}
        for voter, suspect in (votes or {}).items():
            if voter in self.alive and suspect in self.alive and voter != suspect:
                tally[suspect] = tally.get(suspect, 0) + 1
        out = None
        if tally:
            top = max(tally.values())
            leaders = sorted(p for p, v in tally.items() if v == top)
            out = leaders[0] if len(leaders) == 1 else None  # ties stand
        if out:
            self.alive.discard(out)
            self.dead[out] = {"round": "day", "cause": "vote"}
        self.emit("day.resolved", {"eliminated": out, "tie": out is None,
                                   "tally": tally})
        return {"eliminated": out}

    def winner(self) -> str | None:
        mafia = sum(1 for p in self.alive if self.roles[p] == "mafia")
        if mafia == 0:
            return "civilians"
        if mafia >= len(self.alive) - mafia:
            return "mafia"
        return None

    def receipt(self, winner: str | None) -> dict:
        return {
            "schema": "freaktown.receipt/v1",
            "event_id": self.event_id,
            "format": {"repo": "", "git_commit": git_commit(),
                       "format_id": _sha(_canon(self.pack)),
                       "version": str(self.pack.get("version", ""))},
            "participants": self.pids,
            "started_at": self.started_at,
            "ended_at": _now(),
            "event_log_root": self._prev,
            "results": {"winner": winner},
            "media": {"master": "", "clips": []},
        }
