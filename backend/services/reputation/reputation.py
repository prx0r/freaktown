"""Reputation — character records, creator pseudonyms, leaderboard, tickets.

Two reputations, both public, neither doxxing anyone:

  character reputation — record (W/L), best Ella, best Stream, clips,
      Golden Tickets, regular status, rivals (future: head-to-head)
  creator reputation   — pseudonymous code (creator_7F32), Freaks created,
      wins, tickets, career laughs, best character

Golden Tickets are scarce status objects: globally numbered, permanently
attached to the character, issued by Ella only.

Regular rule (v1): >= 3 appearances AND >= 2 KEEPs. Tunable; recorded in
the output so rule changes are auditable per-evaluation.
"""

import hashlib
import uuid
from dataclasses import dataclass, field

REGULAR_MIN_APPEARANCES = 3
REGULAR_MIN_WINS = 2
REGULAR_RULE_VERSION = "regular.v1"


def creator_code(user_id: uuid.UUID | str) -> str:
    """Pseudonymous creator identity: creator_7F32.

    Deterministic per user, opaque (sha256, truncated), no PII.
    A creator becomes renowned for hilarious Freaks without exposure.
    """
    digest = hashlib.sha256(f"freak-town-creator:{user_id}".encode()).hexdigest()
    return f"creator_{digest[:4].upper()}"


@dataclass
class AppearanceResult:
    """One judged appearance, decoupled from ORM for pure aggregation."""
    appearance_id: str
    comedian_id: str
    ella_verdict: str | None = None  # KEEP / CUT / None (unjudged)
    ella_score: float | None = None
    stream_score: float | None = None
    peak_laugh_share: float | None = None
    golden_ticket: bool = False


@dataclass
class CharacterRecord:
    comedian_id: str
    appearances: int = 0
    wins: int = 0
    losses: int = 0
    best_ella: float | None = None
    best_stream: float | None = None
    best_laugh_share: float | None = None
    golden_tickets: int = 0
    is_regular: bool = False
    regular_rule: str = REGULAR_RULE_VERSION

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    def to_dict(self) -> dict:
        return {
            "comedian_id": self.comedian_id,
            "record": self.record,
            "appearances": self.appearances,
            "wins": self.wins,
            "losses": self.losses,
            "best_ella": self.best_ella,
            "best_stream": self.best_stream,
            "best_laugh_share": self.best_laugh_share,
            "golden_tickets": self.golden_tickets,
            "is_regular": self.is_regular,
            "regular_rule": self.regular_rule,
        }


def aggregate_character(comedian_id: str, results: list[AppearanceResult]) -> CharacterRecord:
    """Fold a character's judged appearances into its public record."""
    rec = CharacterRecord(comedian_id=comedian_id)
    mine = [r for r in results if r.comedian_id == comedian_id]
    rec.appearances = len(mine)
    for r in mine:
        if r.ella_verdict == "KEEP":
            rec.wins += 1
        elif r.ella_verdict == "CUT":
            rec.losses += 1
        if r.ella_score is not None:
            rec.best_ella = r.ella_score if rec.best_ella is None else max(rec.best_ella, r.ella_score)
        if r.stream_score is not None:
            rec.best_stream = r.stream_score if rec.best_stream is None else max(rec.best_stream, r.stream_score)
        if r.peak_laugh_share is not None:
            rec.best_laugh_share = (
                r.peak_laugh_share if rec.best_laugh_share is None
                else max(rec.best_laugh_share, r.peak_laugh_share)
            )
        if r.golden_ticket:
            rec.golden_tickets += 1
    rec.is_regular = (
        rec.appearances >= REGULAR_MIN_APPEARANCES and rec.wins >= REGULAR_MIN_WINS
    )
    return rec


@dataclass
class CreatorStats:
    creator_code: str
    freaks_created: int = 0
    total_appearances: int = 0
    total_wins: int = 0
    golden_tickets: int = 0
    best_character_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "creator_code": self.creator_code,
            "freaks_created": self.freaks_created,
            "total_appearances": self.total_appearances,
            "total_wins": self.total_wins,
            "golden_tickets": self.golden_tickets,
            "best_character_id": self.best_character_id,
        }


def aggregate_creator(
    user_id: uuid.UUID | str,
    comedian_ids: list[str],
    records: dict[str, CharacterRecord],
) -> CreatorStats:
    """Fold a creator's characters into their public (pseudonymous) stats."""
    stats = CreatorStats(creator_code=creator_code(user_id))
    stats.freaks_created = len(comedian_ids)
    best_wins = -1
    for cid in comedian_ids:
        rec = records.get(cid)
        if not rec:
            continue
        stats.total_appearances += rec.appearances
        stats.total_wins += rec.wins
        stats.golden_tickets += rec.golden_tickets
        if rec.wins > best_wins:
            best_wins = rec.wins
            stats.best_character_id = cid
    return stats


def leaderboard(records: list[CharacterRecord], limit: int = 50) -> list[CharacterRecord]:
    """Rank characters: wins first, then best Ella, then fewest losses."""
    return sorted(
        records,
        key=lambda r: (r.wins, r.best_ella if r.best_ella is not None else -1, -r.losses),
        reverse=True,
    )[:limit]


def next_ticket_number(existing_numbers: list[int]) -> int:
    """Next global Golden Ticket number. Tickets are scarce: 1, 2, 3... forever."""
    return (max(existing_numbers) + 1) if existing_numbers else 1


def ticket_label(number: int, episode_id: str) -> str:
    return f"🏆 GOLDEN TICKET #{number:03d} (Episode {episode_id}, by Ella)"
