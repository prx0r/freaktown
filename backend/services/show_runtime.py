"""Show Runtime — the 6-minute daily show engine.

No live LLM. No conversation. No crypto. No judges.
Just: Ella intro → 5 acts → return vote → outro.

This is the entire show. Brutally simple.

Reference: anime.dm — Episode 1 format
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ShowPhase(str, Enum):
    PRESHOW = "preshow"
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


# ── Act ─────────────────────────────────────────────────────────────

@dataclass
class ShowAct:
    """A single act in the show — one character's 60-second performance."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position: int = 0
    comedian_id: str = ""
    character_name: str = ""
    draft_id: str = ""
    performance_plan: dict = field(default_factory=dict)
    audio_url: str = ""
    duration_ms: int = 60000
    status: ActStatus = ActStatus.QUEUED

    # Timing
    started_at: datetime | None = None
    ended_at: datetime | None = None

    # Audience data
    laugh_count: int = 0
    laugh_timeline: list[dict] = field(default_factory=list)  # [{ms, count}]
    peak_laugh_ms: int = 0
    peak_laugh_count: int = 0
    return_votes: int = 0
    return_total: int = 0

    @property
    def return_rate(self) -> float:
        if self.return_total == 0:
            return 0
        return self.return_votes / self.return_total

    @property
    def peak_laugh_pct(self) -> float:
        """Peak laugh as percentage of active viewers."""
        if self.return_total == 0:
            return 0
        return min(1.0, self.peak_laugh_count / max(1, self.return_total))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": self.position,
            "character_name": self.character_name,
            "comedian_id": self.comedian_id,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "laugh_count": self.laugh_count,
            "peak_laugh_pct": round(self.peak_laugh_pct * 100, 1),
            "return_votes": self.return_votes,
            "return_total": self.return_total,
            "return_rate": round(self.return_rate * 100, 1),
        }


# ── Show ────────────────────────────────────────────────────────────

@dataclass
class DailyShow:
    """A single daily show instance.

    Format:
      Ella intro (15 sec)
      Act 1 (60 sec) + return vote (5 sec)
      Act 2 (60 sec) + return vote (5 sec)
      Act 3 (60 sec) + return vote (5 sec)
      Act 4 (60 sec) + return vote (5 sec)
      Act 5 (60 sec) + return vote (5 sec)
      Ella outro (20 sec)

    Total: ~6 minutes
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: str = ""  # "2026-09-06"
    phase: ShowPhase = ShowPhase.PRESHOW
    acts: list[ShowAct] = field(default_factory=list)
    max_acts: int = 5

    # Show timing
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    # Global audience
    peak_viewers: int = 0
    total_chat_messages: int = 0
    total_laughs: int = 0

    # Ella lines (pre-generated, not live)
    ella_intro_text: str = ""
    ella_outro_text: str = ""
    ella_act_transitions: list[str] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> int:
        intro = 15000
        outro = 20000
        vote_window = 5000
        acts = sum(a.duration_ms for a in self.acts) + (vote_window * len(self.acts))
        return intro + acts + outro

    @property
    def total_duration_sec(self) -> int:
        return self.total_duration_ms // 1000

    def add_act(self, act: ShowAct):
        """Add an act to the show."""
        act.position = len(self.acts) + 1
        self.acts.append(act)

    def get_act(self, act_id: str) -> ShowAct | None:
        for a in self.acts:
            if a.id == act_id:
                return a
        return None

    def get_next_act(self) -> ShowAct | None:
        for a in self.acts:
            if a.status == ActStatus.QUEUED:
                return a
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "phase": self.phase.value,
            "acts": [a.to_dict() for a in self.acts],
            "total_duration_sec": self.total_duration_sec,
            "peak_viewers": self.peak_viewers,
            "total_laughs": self.total_laughs,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


# ── Show Runner ─────────────────────────────────────────────────────

class ShowRunner:
    """Manages the lifecycle of a daily show.

    Not a live LLM. Not a conversation engine.
    Just sequencing pre-compiled acts with audience interaction.
    """

    def __init__(self):
        self.shows: dict[str, DailyShow] = {}

    def create_show(self, date: str, acts: list[ShowAct] | None = None) -> DailyShow:
        """Create a new daily show."""
        show = DailyShow(
            date=date,
            phase=ShowPhase.PRESHOW,
        )

        if acts:
            for act in acts[:5]:  # max 5 acts
                show.add_act(act)

        self.shows[show.id] = show
        return show

    def start_show(self, show_id: str) -> DailyShow:
        """Start the show — begin with Ella intro."""
        show = self.shows.get(show_id)
        if not show:
            raise ValueError(f"Show {show_id} not found")

        show.phase = ShowPhase.ELLA_INTRO
        show.started_at = datetime.now(timezone.utc)
        return show

    def start_act(self, show_id: str, act_id: str) -> ShowAct:
        """Start playing an act."""
        show = self.shows.get(show_id)
        if not show:
            raise ValueError(f"Show {show_id} not found")

        act = show.get_act(act_id)
        if not act:
            raise ValueError(f"Act {act_id} not found")

        show.phase = ShowPhase.ACT
        act.status = ActStatus.PLAYING
        act.started_at = datetime.now(timezone.utc)
        return act

    def end_act(self, show_id: str, act_id: str) -> ShowAct:
        """End an act — start return voting."""
        show = self.shows.get(show_id)
        if not show:
            raise ValueError(f"Show {show_id} not found")

        act = show.get_act(act_id)
        if not act:
            raise ValueError(f"Act {act_id} not found")

        act.status = ActStatus.VOTING
        act.ended_at = datetime.now(timezone.utc)
        show.phase = ShowPhase.RETURN_VOTE
        return act

    def record_laugh(self, show_id: str, act_id: str, timestamp_ms: int):
        """Record a laugh at a specific timestamp."""
        show = self.shows.get(show_id)
        if not show:
            return

        act = show.get_act(act_id)
        if not act or act.status != ActStatus.PLAYING:
            return

        act.laugh_count += 1
        show.total_laughs += 1

        # Find or create bucket (500ms resolution)
        bucket_ms = (timestamp_ms // 500) * 500
        found = False
        for bucket in act.laugh_timeline:
            if bucket["ms"] == bucket_ms:
                bucket["count"] += 1
                found = True
                break

        if not found:
            act.laugh_timeline.append({"ms": bucket_ms, "count": 1})

        # Track peak
        if bucket_count := next((b["count"] for b in act.laugh_timeline if b["ms"] == bucket_ms), 0):
            if bucket_count > act.peak_laugh_count:
                act.peak_laugh_count = bucket_count
                act.peak_laugh_ms = bucket_ms

    def record_return_vote(self, show_id: str, act_id: str, vote: bool):
        """Record a return vote (SEE THEM AGAIN?)."""
        show = self.shows.get(show_id)
        if not show:
            return

        act = show.get_act(act_id)
        if not act or act.status != ActStatus.VOTING:
            return

        act.return_total += 1
        if vote:
            act.return_votes += 1

    def end_show(self, show_id: str) -> DailyShow:
        """End the show — Ella outro."""
        show = self.shows.get(show_id)
        if not show:
            raise ValueError(f"Show {show_id} not found")

        show.phase = ShowPhase.ENDED
        show.ended_at = datetime.now(timezone.utc)

        # Mark remaining acts
        for act in show.acts:
            if act.status in (ActStatus.QUEUED, ActStatus.PLAYING):
                act.status = ActStatus.COMPLETED
                if not act.ended_at:
                    act.ended_at = datetime.now(timezone.utc)

        return show

    def get_show_summary(self, show_id: str) -> dict:
        """Get a summary of the show for post-show synthesis."""
        show = self.shows.get(show_id)
        if not show:
            return {}

        acts_summary = []
        for act in show.acts:
            # Find the biggest laugh
            biggest = max(act.laugh_timeline, key=lambda b: b["count"]) if act.laugh_timeline else None

            acts_summary.append({
                "position": act.position,
                "character_name": act.character_name,
                "comedian_id": act.comedian_id,
                "duration_ms": act.duration_ms,
                "laugh_count": act.laugh_count,
                "peak_laugh_pct": round(act.peak_laugh_pct * 100, 1),
                "peak_laugh_ms": act.peak_laugh_ms,
                "biggest_laugh_time": biggest["ms"] if biggest else 0,
                "return_rate": round(act.return_rate * 100, 1),
                "return_votes": act.return_votes,
                "laugh_timeline": act.laugh_timeline,
            })

        return {
            "show_id": show.id,
            "date": show.date,
            "total_duration_sec": show.total_duration_sec,
            "total_laughs": show.total_laughs,
            "peak_viewers": show.peak_viewers,
            "acts": acts_summary,
        }


# Singleton
show_runner = ShowRunner()
