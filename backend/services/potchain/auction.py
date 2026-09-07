"""Sponsor auction — the hilarious ad-read market.

During the show (or before it):

  NEXT SHOW AD READ — Current bid: $38, Acme Corp — [OUTBID]

Money never buys immunity from moderation:

  bid (intent, no money moves)
    ↓
  payment... nothing yet — bids are signed intents
    ↓
  message/ad moderation → eligible | rejected
    ↓
  close at SHOW_START - 5 minutes
    ↓
  highest eligible bid wins → winner pays via x402 sponsor action
    ↓
  on settlement, the winning amount enters the Pot (source=sponsor)

Refund policy (explicit): no money moves until the winner pays, so there
is nothing to refund. Rejected bids simply never become payable. If the
winner defaults past the payment timeout, the next-highest eligible bid
wins. Bids are intents, not transfers — this is what keeps the auction
from becoming a custody problem.

Ties: earliest bid wins (deterministic).
"""

import time
from dataclasses import dataclass, field


@dataclass
class Bid:
    bid_id: str
    episode_id: str
    bidder: str  # session or wallet id
    amount_cents: int
    copy: str  # proposed ad read text
    url: str = ""
    created_at: float = field(default_factory=time.time)
    moderation: str = "pending"  # pending | eligible | rejected
    moderation_note: str = ""


@dataclass
class AuctionResult:
    episode_id: str
    winner_bid_id: str | None
    winner_bidder: str | None
    winning_cents: int
    pot_contribution_cents: int
    defaulted: list[str] = field(default_factory=list)


class SponsorAuction:
    """One auction per episode. In-memory; the close result is persisted
    by the caller as show events (auction.closed, then pot.contribution
    on winner settlement)."""

    def __init__(self, episode_id: str, close_at: float):
        self.episode_id = episode_id
        self.close_at = close_at
        self.bids: dict[str, Bid] = {}
        self.closed = False
        self._seq = 0

    def place_bid(self, bidder: str, amount_cents: int, copy: str, url: str = "",
                  now: float | None = None) -> Bid:
        now = time.time() if now is None else now
        if self.closed or now >= self.close_at:
            raise ValueError("auction is closed")
        if not isinstance(amount_cents, int) or amount_cents <= 0:
            raise ValueError("amount_cents must be a positive integer")
        if not copy or len(copy) > 280:
            raise ValueError("copy required, max 280 chars")
        current = self.highest_eligible()
        # Floor = highest ELIGIBLE bid. Pending bids don't set the floor
        # (moderation is fast; only eligible bids can win at close).
        floor = current.amount_cents if current else 0
        if amount_cents <= floor:
            raise ValueError(f"bid must exceed current high bid of ${floor / 100:.2f}")
        self._seq += 1
        bid = Bid(
            bid_id=f"bid_{self._seq:04d}", episode_id=self.episode_id,
            bidder=bidder, amount_cents=amount_cents, copy=copy, url=url,
            created_at=now,
        )
        self.bids[bid.bid_id] = bid
        return bid

    def moderate(self, bid_id: str, eligible: bool, note: str = "") -> Bid:
        bid = self.bids.get(bid_id)
        if not bid:
            raise ValueError("unknown bid")
        if self.closed:
            raise ValueError("auction is closed")
        bid.moderation = "eligible" if eligible else "rejected"
        bid.moderation_note = note
        return bid

    def highest_eligible(self) -> Bid | None:
        eligible = [b for b in self.bids.values() if b.moderation == "eligible"]
        if not eligible:
            return None
        # Highest amount wins; earliest bid wins ties.
        return sorted(eligible, key=lambda b: (-b.amount_cents, b.created_at))[0]

    def close(self, now: float | None = None) -> AuctionResult:
        now = time.time() if now is None else now
        if self.closed:
            raise ValueError("already closed")
        self.closed = True
        winner = self.highest_eligible()
        if not winner:
            return AuctionResult(
                episode_id=self.episode_id, winner_bid_id=None,
                winner_bidder=None, winning_cents=0, pot_contribution_cents=0,
            )
        return AuctionResult(
            episode_id=self.episode_id,
            winner_bid_id=winner.bid_id,
            winner_bidder=winner.bidder,
            winning_cents=winner.amount_cents,
            pot_contribution_cents=winner.amount_cents,
        )

    def mark_defaulted(self, bid_id: str) -> AuctionResult:
        """Winner didn't pay in time: disqualify and promote the runner-up."""
        bid = self.bids.get(bid_id)
        if not bid:
            raise ValueError("unknown bid")
        bid.moderation = "rejected"
        bid.moderation_note = "defaulted: payment timeout"
        defaulted = [bid_id]
        while True:
            winner = self.highest_eligible()
            if not winner:
                return AuctionResult(
                    episode_id=self.episode_id, winner_bid_id=None,
                    winner_bidder=None, winning_cents=0,
                    pot_contribution_cents=0, defaulted=defaulted,
                )
            # Caller attempts settlement with this winner next.
            return AuctionResult(
                episode_id=self.episode_id,
                winner_bid_id=winner.bid_id,
                winner_bidder=winner.bidder,
                winning_cents=winner.amount_cents,
                pot_contribution_cents=winner.amount_cents,
                defaulted=defaulted,
            )
