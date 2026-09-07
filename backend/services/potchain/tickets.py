"""FREAK TICKET — submission credits. Deliberately not crypto.

A ticket is one submission credit: the holder thinks "I'm entering the
show", never "I'm buying an asset". Tickets are non-transferable,
non-tradeable, expire never, and live in this service (persisted to the
DB before public launch; in-memory for Episode Zero).

Sources:
  free weekly ticket  — one per user per ISO week, claimed
  reputation          — earned by creator stats (REGULARs, wins)
  sponsor grant       — sponsors give away tickets
  admin grant         — manual, for community winners etc.
  purchase            — $1 eventually (not yet; source exists, unused)

Redemption: one ticket per submission. redeem() is atomic per call.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TicketGrant:
    user_id: str
    source: str
    granted_at: float = field(default_factory=time.time)
    note: str = ""


VALID_SOURCES = ("weekly", "reputation", "sponsor_grant", "admin_grant", "purchase")


class TicketWallet:
    """In-memory ticket balances. Replace with a DB table pre-launch."""

    def __init__(self):
        self._balance: dict[str, int] = {}
        self._grants: list[TicketGrant] = []
        self._last_weekly: dict[str, str] = {}  # user_id -> ISO week "2026-W37"

    def balance(self, user_id: str) -> int:
        return self._balance.get(user_id, 0)

    def grant(self, user_id: str, source: str, count: int = 1, note: str = "") -> int:
        if source not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        if source == "purchase":
            raise ValueError("ticket purchase is not enabled yet")
        if not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")
        for _ in range(count):
            self._grants.append(TicketGrant(user_id=user_id, source=source, note=note))
        self._balance[user_id] = self.balance(user_id) + count
        return self._balance[user_id]

    def claim_weekly(self, user_id: str, now: float | None = None) -> int:
        """Free weekly ticket. One per ISO week. Idempotent within a week."""
        now = time.time() if now is None else now
        week = datetime.fromtimestamp(now, timezone.utc).strftime("%G-W%V")
        if self._last_weekly.get(user_id) == week:
            raise ValueError("weekly ticket already claimed")
        self._last_weekly[user_id] = week
        return self.grant(user_id, "weekly", 1, note=week)

    def redeem(self, user_id: str) -> int:
        """Spend one ticket on a submission. Returns remaining balance."""
        if self.balance(user_id) <= 0:
            raise ValueError("no tickets: claim your free weekly ticket")
        self._balance[user_id] -= 1
        return self._balance[user_id]

    def grants_for(self, user_id: str) -> list[TicketGrant]:
        return [g for g in self._grants if g.user_id == user_id]


ticket_wallet = TicketWallet()
