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

VALID_SOURCES = ("platform_revenue", "sponsor", "tip_overflow", "manual", "chain")


def usdc_str_to_cents(amount_usdc: str) -> int:
    """'10.00' → 1000. Chain payloads carry decimal USDC strings; the
    ledger folds everything to integer cents. Max 2 decimal places."""
    from decimal import Decimal, InvalidOperation

    try:
        value = Decimal(str(amount_usdc))
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid amount_usdc: {amount_usdc!r}")
    if value <= 0:
        raise ValueError("amount must be positive")
    cents = value * 100
    if cents != int(cents):
        raise ValueError("amount_usdc supports at most 2 decimal places")
    return int(cents)


def contribution_amount_cents(payload: dict) -> int:
    """Extract a positive integer cent amount from either payload shape."""
    if "amount_cents" in payload:
        amount = payload["amount_cents"]
        if not isinstance(amount, int) or amount <= 0:
            return 0
        return amount
    if "amount_usdc" in payload:
        try:
            return usdc_str_to_cents(payload["amount_usdc"])
        except ValueError:
            return 0
    return 0


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
        total += contribution_amount_cents(e.get("payload") or {})
    return total


def pot_total_for_episode(events: list[dict], episode_id: str) -> int:
    """Tonight's pot in cents."""
    return pot_total([e for e in events if str(e.get("episode_id")) == str(episode_id)])


def format_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"
