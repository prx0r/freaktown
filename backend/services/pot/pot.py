"""THE POT — prize pool derived from the event log.

No token, no staking. One visible number per episode and per season.

Design: the pot is a pure fold over ShowEvents of type `pot.contribution`
with payload {amount_cents, source, note}. No new tables; the event log
is the ledger, so totals are always auditable and replayable.

Sources: "platform_revenue" (ad revenue from official uploads),
"sponsor" (production-adjacent top-ups), "tip_overflow" (future).

Episode Zero honesty: the pot may be $0.00. That's funny. Ella says so.
"""

POT_EVENT_TYPE = "pot.contribution"

VALID_SOURCES = ("platform_revenue", "sponsor", "tip_overflow", "manual")


def validate_contribution(amount_cents: int, source: str) -> None:
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("amount_cents must be a positive integer")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {VALID_SOURCES}")


def contribution_payload(amount_cents: int, source: str, note: str = "") -> dict:
    validate_contribution(amount_cents, source)
    return {"amount_cents": amount_cents, "source": source, "note": note}


def pot_total(events: list[dict]) -> int:
    """Total pot in cents across all episodes (the season pot)."""
    total = 0
    for e in events:
        if e.get("type") != POT_EVENT_TYPE:
            continue
        payload = e.get("payload") or {}
        amount = payload.get("amount_cents", 0)
        if isinstance(amount, int) and amount > 0:
            total += amount
    return total


def pot_total_for_episode(events: list[dict], episode_id: str) -> int:
    """Tonight's pot in cents."""
    return pot_total([e for e in events if str(e.get("episode_id")) == str(episode_id)])


def format_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"
