"""Show pot escrow — off-chain mirror of contracts/ShowPot.sol.

The contract holds the money; this module holds the semantics both
environments share:

  OPEN → LOCKED (winner finalized) → CLAIMED (pull-based payout)
  OPEN → REFUNDED (emergency: contributors pull back)

Rules (identical on-chain):
- Contributions accepted only while OPEN.
- Only the closer role can finalize a winner, only once, only while OPEN.
- Only the recorded winner can claim, only once (pull-based).
- Refunds only in REFUNDED state, only actual contributors, only once.
- The contract never decides who is funny: it receives one authenticated
  final result (winner address) and enforces money movement from there.

LocalPotEscrow is the in-memory implementation for dev/tests. Amounts
are integer atomic USDC units (6 decimals) — never floats.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Contribution:
    wallet: str
    amount: int  # atomic USDC units
    tx: str = ""
    message: str = ""


@dataclass
class PotView:
    show_id: str
    status: str
    total: int
    contribution_count: int
    winner: str | None
    claimed: bool


class PotEscrow(ABC):
    """Escrow interface. LocalPotEscrow today, chain client tomorrow."""

    @abstractmethod
    def contribute(self, show_id: str, wallet: str, amount: int, tx: str = "", message: str = "") -> int:
        """Record a contribution. Returns new pot total. Only while OPEN."""
        ...

    @abstractmethod
    def finalize_winner(self, show_id: str, winner: str, closer: str) -> None:
        """Lock the winner. Only the closer role, only once, only while OPEN."""
        ...

    @abstractmethod
    def claim(self, show_id: str, wallet: str) -> int:
        """Winner pulls the prize. Returns amount paid. Only once."""
        ...

    @abstractmethod
    def emergency_refund(self, show_id: str, admin: str) -> None:
        """Move to REFUNDED state. Contributors pull back via withdraw_refund."""
        ...

    @abstractmethod
    def withdraw_refund(self, show_id: str, wallet: str) -> int:
        """Contributor pulls their refund. Returns amount. Only once."""
        ...

    @abstractmethod
    def view(self, show_id: str) -> PotView:
        ...


@dataclass
class _Pot:
    show_id: str
    closer: str
    status: str = "OPEN"
    contributions: list[Contribution] = field(default_factory=list)
    winner: str | None = None
    claimed: bool = False
    refunded_wallets: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return sum(c.amount for c in self.contributions)


class LocalPotEscrow(PotEscrow):
    """In-memory escrow. Deterministic. For dev, tests, and dry runs."""

    def __init__(self):
        self._pots: dict[str, _Pot] = {}

    def open(self, show_id: str, closer: str) -> None:
        if show_id in self._pots:
            raise ValueError("pot already exists")
        self._pots[show_id] = _Pot(show_id=show_id, closer=closer)

    def _get(self, show_id: str) -> _Pot:
        pot = self._pots.get(show_id)
        if not pot:
            raise ValueError("unknown show pot")
        return pot

    def contribute(self, show_id: str, wallet: str, amount: int, tx: str = "", message: str = "") -> int:
        pot = self._get(show_id)
        if pot.status != "OPEN":
            raise ValueError(f"pot is {pot.status}, not OPEN")
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive integer of atomic units")
        if not wallet:
            raise ValueError("wallet required")
        pot.contributions.append(Contribution(wallet=wallet, amount=amount, tx=tx, message=message))
        return pot.total

    def finalize_winner(self, show_id: str, winner: str, closer: str) -> None:
        pot = self._get(show_id)
        if pot.status != "OPEN":
            raise ValueError(f"pot is {pot.status}, not OPEN")
        if closer != pot.closer:
            raise ValueError("only the closer can finalize")
        if not winner:
            raise ValueError("winner required")
        pot.winner = winner
        pot.status = "LOCKED"

    def claim(self, show_id: str, wallet: str) -> int:
        pot = self._get(show_id)
        if pot.status != "LOCKED":
            raise ValueError(f"pot is {pot.status}, nothing to claim")
        if wallet != pot.winner:
            raise ValueError("only the winner can claim")
        if pot.claimed:
            raise ValueError("already claimed")
        pot.claimed = True
        pot.status = "CLAIMED"
        return pot.total

    def emergency_refund(self, show_id: str, admin: str) -> None:
        pot = self._get(show_id)
        if pot.status == "CLAIMED":
            raise ValueError("already claimed, cannot refund")
        if admin != pot.closer:
            raise ValueError("only the closer can trigger refunds")
        pot.status = "REFUNDED"

    def withdraw_refund(self, show_id: str, wallet: str) -> int:
        pot = self._get(show_id)
        if pot.status != "REFUNDED":
            raise ValueError("refunds not enabled")
        if wallet in pot.refunded_wallets:
            raise ValueError("already refunded")
        amount = sum(c.amount for c in pot.contributions if c.wallet == wallet)
        if amount <= 0:
            raise ValueError("no contributions to refund")
        pot.refunded_wallets.add(wallet)
        return amount

    def view(self, show_id: str) -> PotView:
        pot = self._get(show_id)
        return PotView(
            show_id=pot.show_id,
            status=pot.status,
            total=pot.total,
            contribution_count=len(pot.contributions),
            winner=pot.winner,
            claimed=pot.claimed,
        )
