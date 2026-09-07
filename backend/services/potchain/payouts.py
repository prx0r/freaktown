"""Payout math — deterministic winner split in integer atomic units.

  70% Ella winner (official champion — Ella is the real judge)
  20% Stream champion (People's Champion)
  10% season pot (rolls forward, becomes narrative)

Integer math only. Dust from flooring goes to the season pot
(deterministic, documented, auditable). Splits always sum to total.

Edge cases:
- Same wallet wins both → it receives 90%, season keeps 10%.
- No Stream champion (no votes) → the 20% rolls to the season pot.
- Ella winner is always required: the contract never pays without one.
"""

ELLA_BPS = 7000
STREAM_BPS = 2000
SEASON_BPS = 1000
BPS_DENOM = 10_000


def split_pot(total_atomic: int, stream_champion: bool = True) -> dict[str, int]:
    """Split a locked pot. Returns atomic-unit shares summing to total."""
    if not isinstance(total_atomic, int) or total_atomic < 0:
        raise ValueError("total must be a non-negative integer of atomic units")
    ella = total_atomic * ELLA_BPS // BPS_DENOM
    stream = (total_atomic * STREAM_BPS // BPS_DENOM) if stream_champion else 0
    season = total_atomic - ella - stream  # dust lands here, deterministically
    assert ella + stream + season == total_atomic
    return {"ella_winner": ella, "stream_champion": stream, "season_pot": season}


def payout_event_payload(
    show_id: str,
    ella_wallet: str,
    stream_wallet: str | None,
    total_atomic: int,
    network: str,
) -> dict:
    """Canonical show.payout event payload (also the claim instructions)."""
    split = split_pot(total_atomic, stream_champion=bool(stream_wallet))
    same_wallet = bool(stream_wallet) and stream_wallet == ella_wallet
    return {
        "show_id": show_id,
        "network": network,
        "total_atomic": total_atomic,
        "ella_wallet": ella_wallet,
        "stream_wallet": stream_wallet,
        "same_wallet_won_both": same_wallet,
        "ella_share_atomic": split["ella_winner"] + (split["stream_champion"] if same_wallet else 0),
        "stream_share_atomic": 0 if same_wallet else split["stream_champion"],
        "season_share_atomic": split["season_pot"],
        "rule": "ella70/stream20/season10",
    }
