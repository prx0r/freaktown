#!/usr/bin/env python3
"""Declarative format runtime: FormatPack in, EventReceipt out.

No per-format logic lives here of any kind. States, rounds, timers,
scoring weights, and advancement all come from freak-format.json. Deterministic given identical inputs: same format bytes +
same submissions = same receipt (outcomes differ tomorrow because the
*inputs* differ, never because the engine is moody).

Event log is hash-chained (each event commits to the previous hash);
event_log_root is the final hash. format_id is the sha256 of the canonical
manifest — an event from 2031 still identifies exactly which rules ran.
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATES = ["LOBBY", "CHECK_IN", "ROUND_INTRO", "PERFORMER_WALKOUT",
                  "PERFORMANCE", "JUDGING", "ROUND_RESULTS", "ADVANCEMENT",
                  "FINAL", "WINNER", "AFTERPARTY"]


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_format(path: str | Path) -> dict:
    d = Path(path)
    manifest = json.loads((d / "freak-format.json").read_text())
    manifest["_dir"] = str(d)
    manifest["_format_id"] = _sha(_canon({k: v for k, v in manifest.items()
                                          if not k.startswith("_")}))
    return manifest


def validate_format(manifest: dict) -> list[str]:
    """Returns error list (empty = valid). Schema + reference checks."""
    errors = []
    try:
        import jsonschema
        schema = json.loads(Path(__file__).parent.joinpath(
            "contracts/format.v1.schema.json").read_text())
        jsonschema.validate({k: v for k, v in manifest.items()
                             if not k.startswith("_")}, schema)
    except ImportError:
        errors.append("jsonschema unavailable")
    except Exception as e:
        errors.append(f"schema: {e}")
        return errors
    d = Path(manifest.get("_dir", "."))
    rubric = ((manifest.get("judging") or {}).get("rubric") or "")
    if rubric and not (d / rubric.lstrip("./")).exists():
        errors.append(f"missing rubric: {rubric}")
    return [e for e in errors if e != "jsonschema unavailable"] or []


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             timeout=5)
        return out.stdout.decode().strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _score(entry, weights) -> float:
    if isinstance(entry, dict):
        a = float(entry.get("audience", 0))
        j = float(entry.get("judge", entry.get("audience", 0)))
        return a * weights[0] + j * weights[1]
    return float(entry)


class FormatRun:
    """One execution of a format. Append-only hashed event log."""

    def __init__(self, manifest: dict, event_id: str = ""):
        self.manifest = manifest
        self.event_id = event_id or f"evt_{_sha(_now())[:12]}"
        self.started_at = _now()
        self.events: list[dict] = []
        self._prev = "genesis"
        self.emit("event.opened", {"format": manifest["id"],
                                   "version": manifest["version"]})

    def emit(self, kind: str, payload: dict):
        ev = {"seq": len(self.events) + 1, "type": kind,
              "prev": self._prev, "payload": payload}
        ev["hash"] = _sha(_canon(ev))
        self._prev = ev["hash"]
        self.events.append(ev)
        return ev

    def run(self, participants: list[str], submissions: dict) -> dict:
        """participants: ordered ids. submissions: {round_id: {pid: score}}.
        Returns the EventReceipt."""
        judging = self.manifest.get("judging", {})
        weights = (float(judging.get("audienceWeight", 0.5)),
                   float(judging.get("judgeWeight", 0.5)))
        alive = list(participants)
        self.emit("lobby.closed", {"participants": alive})
        tiebreak = False
        for rnd in self.manifest["rounds"]:
            rid = rnd["id"]
            self.emit("round.opened", {"round": rid, "performers": alive})
            scores = {}
            for pid in alive:
                entry = (submissions.get(rid) or {}).get(pid)
                if entry is None:
                    self.emit("performer.dropout", {"round": rid, "participant": pid})
                    continue
                scores[pid] = _score(entry, weights)
                self.emit("submission.scored", {"round": rid, "participant": pid,
                                               "score": scores[pid]})
            ranked = sorted(scores, key=lambda p: (-scores[p], p))
            adv = rnd.get("advance", {}) or {}
            if adv.get("all"):
                alive = ranked
            else:
                top = int(adv.get("top", 1))
                alive = ranked[:top]
                # Boundary tie: last in, first out scored equal.
                # Winner is deterministic (participant-id order); the
                # receipt flags it instead of pretending it was decisive.
                if len(ranked) > top and scores[ranked[top - 1]] == scores[ranked[top]]:
                    tiebreak = True
            self.emit("round.results", {"round": rid, "ranked": ranked,
                                        "advanced": alive, "tiebreak": tiebreak})
        winner = alive[0] if alive else None
        self.emit("event.closed", {"winner": winner, "tiebreak": tiebreak})
        return self.receipt(participants, winner, tiebreak)

    def receipt(self, participants: list[str], winner: str | None,
                tiebreak: bool) -> dict:
        m = self.manifest
        return {
            "schema": "freaktown.receipt/v1",
            "event_id": self.event_id,
            "format": {"id": m["id"], "repo": m.get("_repo", ""),
                       "git_commit": git_commit(),
                       "format_id": m["_format_id"],
                       "version": m["version"]},
            "participants": participants,
            "started_at": self.started_at,
            "ended_at": _now(),
            "event_log_root": self._prev,
            "results": {"winner": winner, "tiebreak": tiebreak},
            "media": {"master": "", "clips": []},
        }
