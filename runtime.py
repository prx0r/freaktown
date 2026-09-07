"""Show runtime — the daily show state machine.

No DB. No Redis. Pure Python dataclasses.

Flow:
  ELLA_INTRO → ACT 1 → VOTE → ACT 2 → VOTE → ... → ELLA_OUTRO → ENDED
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ShowPhase(str, Enum):
    ELLA_INTRO = "ella_intro"
    ACT = "act"
    RETURN_VOTE = "return_vote"
    ELLA_OUTRO = "ella_outro"
    ENDED = "ended"


class ActStatus(str, Enum):
    QUEUED = "queued"
    PLAYING = "playing"
    VOTING = "voting"
    COMPLETED = "completed"


@dataclass
class Act:
    comedian: dict
    position: int = 0
    status: ActStatus = ActStatus.QUEUED
    started_at: datetime | None = None
    ended_at: datetime | None = None

    # audience
    laugh_count: int = 0
    laugh_timeline: list[dict] = field(default_factory=list)
    peak_laugh_ms: int = 0
    peak_laugh_count: int = 0
    return_votes: int = 0
    return_total: int = 0

    @property
    def name(self) -> str:
        return self.comedian["name"]

    @property
    def return_rate(self) -> float:
        return self.return_votes / max(1, self.return_total)

    @property
    def peak_laugh_pct(self) -> float:
        """Laugh coverage — what fraction of the set had laughter."""
        if not self.laugh_timeline or self.return_total == 0:
            return 0.0
        # Count distinct 2-second windows with laughs vs total possible windows
        active_windows = len(set(b["ms"] for b in self.laugh_timeline))
        total_windows = max(1, 60 // 2)  # 60-sec set, 2-sec windows
        return min(1.0, active_windows / total_windows)

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "name": self.name,
            "slug": self.comedian["slug"],
            "status": self.status.value,
            "laugh_count": self.laugh_count,
            "peak_laugh_pct": round(self.peak_laugh_pct * 100, 1),
            "return_rate": round(self.return_rate * 100, 1),
        }


@dataclass
class Show:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    date: str = ""
    phase: ShowPhase = ShowPhase.ELLA_INTRO
    acts: list[Act] = field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    total_laughs: int = 0

    @property
    def total_duration_sec(self) -> int:
        intro = 15
        outro = 20
        vote_window = 5
        acts = sum(60 for _ in self.acts) + (vote_window * len(self.acts))
        return intro + acts + outro

    def add_act(self, comedian: dict):
        act = Act(comedian=comedian, position=len(self.acts) + 1)
        self.acts.append(act)

    def get_current_act(self) -> Act | None:
        for a in self.acts:
            if a.status in (ActStatus.PLAYING, ActStatus.VOTING):
                return a
        return None

    def get_next_act(self) -> Act | None:
        for a in self.acts:
            if a.status == ActStatus.QUEUED:
                return a
        return None

    def record_laugh(self, timestamp_ms: int):
        act = self.get_current_act()
        if not act or act.status != ActStatus.PLAYING:
            return
        act.laugh_count += 1
        self.total_laughs += 1
        bucket = (timestamp_ms // 500) * 500
        for b in act.laugh_timeline:
            if b["ms"] == bucket:
                b["count"] += 1
                if b["count"] > act.peak_laugh_count:
                    act.peak_laugh_count = b["count"]
                    act.peak_laugh_ms = bucket
                return
        act.laugh_timeline.append({"ms": bucket, "count": 1})
        if 1 > act.peak_laugh_count:
            act.peak_laugh_count = 1
            act.peak_laugh_ms = bucket

    def record_return_vote(self, vote: bool):
        act = self.get_current_act()
        if not act or act.status != ActStatus.VOTING:
            return
        act.return_total += 1
        if vote:
            act.return_votes += 1

    def summary(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "total_duration_sec": self.total_duration_sec,
            "total_laughs": self.total_laughs,
            "acts": [a.to_dict() for a in self.acts],
        }


def pick_lineup(comedians: list[dict], count: int = 5) -> list[dict]:
    """Pick a random lineup from available comedians."""
    shuffled = comedians[:]
    random.shuffle(shuffled)
    return shuffled[:count]
