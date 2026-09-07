"""On-chain POT routes — x402 paid actions, auction, tickets, finalize.

Money rules (strategy.md):
- x402 is the payment interface. The contract is the money. USDC on Base.
- Entry is free. The pot starts at $0. Settlement needs a facilitator;
  until one is configured, /settle validates payloads and reports
  honestly instead of pretending money moved.
- No $FREAK. FREAK TICKETs are non-tradeable submission credits.

  GET  /v1/pay/{action}                  → 402 + PaymentRequired (x402 v2)
  POST /v1/pay/{action}/settle           → verify via facilitator, execute
  POST /v1/auctions/{episode_id}/bids    → sponsor bid (intent, no money)
  GET  /v1/auctions/{episode_id}         → auction state
  POST /v1/auctions/{episode_id}/bids/{bid_id}/moderate → admin
  POST /v1/auctions/{episode_id}/close   → admin, highest eligible wins
  GET  /v1/tickets/balance               → my ticket balance
  POST /v1/tickets/claim-weekly          → free weekly ticket
  POST /v1/tickets/grant                 → admin grant
  POST /v1/shows/{episode_id}/finalize   → admin: lock winners, payout plan
"""

import base64
import json
import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_from_api_key, require_admin_from_api_key
from backend.db import get_db
from backend.models import Episode, ShowEvent, User
from backend.services.events import emit_event
from backend.services.pot import POT_EVENT_TYPE, pot_total
from backend.services.potchain import (
    ACTIONS,
    X_PAYMENT_HEADER,
    X_PAYMENT_RESPONSE_HEADER,
    NetworkConfig,
    SponsorAuction,
    decode_payment_required,
    encode_payment_required,
    get_facilitator,
    parse_payment_payload,
    payment_required,
    payout_event_payload,
    ticket_wallet,
    usd_cents_to_atomic,
    validate_payment_payload,
)

router = APIRouter()


def _network_config() -> NetworkConfig:
    """Chain config from env. Testnet default — mainnet must be explicit."""
    pay_to = os.getenv("POT_ESCROW_ADDRESS", "")
    network = os.getenv("POT_NETWORK", "eip155:84532")
    if network == "eip155:8453":
        if not pay_to:
            raise HTTPException(501, "mainnet escrow not configured")
        return NetworkConfig.mainnet(pay_to)
    return NetworkConfig.sepolia(pay_to)


# ── Paid actions (x402) ──────────────────────────────────────────────

@router.get("/pay/{action}")
async def pay_requirements(
    action: str,
    amount_cents: int = Query(..., gt=0),
    resource: str = Query(""),
    target: str = Query("", description="character slug for tips, episode for the rest"),
):
    """Return 402 + x402 v2 PaymentRequired for a paid show action."""
    if action not in ACTIONS:
        raise HTTPException(404, f"unknown paid action: {action}")
    try:
        config = _network_config()
    except HTTPException:
        raise
    if not config.pay_to:
        raise HTTPException(501, "pot escrow not deployed yet (POT_ESCROW_ADDRESS unset)")
    try:
        required = payment_required(
            action, resource or f"freak-town:{action}:{target}",
            amount_cents, config,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return JSONResponse(
        status_code=402,
        content=required,
        headers={"PAYMENT-REQUIRED": encode_payment_required(required)},
    )


class SettleRequest(BaseModel):
    payment: dict | None = Field(None, description="x402 v2 PaymentPayload (JSON body)")
    show_id: str = Field(..., description="episode/show id")
    message: str = Field("", max_length=140)
    target: str = Field("", description="character slug for tips")


def _required_for(action: str, target: str, db: AsyncSession | None = None) -> tuple[dict, NetworkConfig]:
    """Minimum-amount requirements for an action. Raises 404/400/501."""
    if action not in ACTIONS:
        raise HTTPException(404, f"unknown paid action: {action}")
    config = _network_config()
    if not config.pay_to:
        raise HTTPException(501, "pot escrow not deployed yet (POT_ESCROW_ADDRESS unset)")
    spec = ACTIONS[action]
    try:
        required = payment_required(
            action, f"freak-town:{action}:{target}",
            spec.min_cents, config,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return required, config


def _payment_required_response(required: dict) -> JSONResponse:
    return JSONResponse(
        status_code=402,
        content=required,
        headers={"PAYMENT-REQUIRED": encode_payment_required(required)},
    )


@router.post("/pay/{action}/settle")
async def pay_settle(
    action: str,
    req: SettleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """One endpoint for the full x402 flow (modal-compatible).

    - No payment attached (no body payment, no X-PAYMENT header) → 402
      with the PaymentRequired envelope (body + PAYMENT-REQUIRED header).
      This is what the modal hits first for price discovery.
    - X-PAYMENT header (base64 v2 PaymentPayload, the modal's transport)
      or JSON body payment → structural check → facilitator verify →
      execute → settle → 200 + x-payment-response receipt header.
    - Without FACILITATOR_URL: validates shape, returns 501 instead of
      pretending money moved.
    """
    required, _ = _required_for(action, req.target)

    raw_payment: dict | str | None = req.payment
    if raw_payment is None:
        raw_payment = request.headers.get(X_PAYMENT_HEADER)
    if raw_payment is None:
        raw_payment = request.headers.get("PAYMENT-SIGNATURE")
    if raw_payment is None:
        return _payment_required_response(required)

    try:
        parsed = parse_payment_payload(raw_payment)
    except ValueError as e:
        raise HTTPException(400, f"invalid payment: {e}")

    ok, reason = validate_payment_payload(
        parsed.model_dump(by_alias=True), required
    )
    if not ok:
        raise HTTPException(400, f"invalid payment: {reason}")

    facilitator = get_facilitator()
    if not facilitator:
        return JSONResponse(
            status_code=501,
            content={
                "status": "settlement_not_configured",
                "detail": "payload structurally valid; set FACILITATOR_URL to settle",
            },
        )

    from x402.schemas import PaymentRequirements as SDKRequirements

    sdk_required = SDKRequirements.model_validate(required["accepts"][0])
    try:
        verdict = await facilitator.verify(parsed, sdk_required)
    except Exception as e:
        raise HTTPException(502, f"facilitator verify failed: {e}")
    if not verdict.isValid:
        raise HTTPException(402, f"payment invalid: {verdict.invalidReason}")

    # Execute the action, then settle.
    receipt = await _execute_paid_action(db, action, req, parsed.model_dump(by_alias=True))
    try:
        result = await facilitator.settle(parsed, sdk_required)
    except Exception as e:
        raise HTTPException(502, f"facilitator settle failed: {e}")

    settlement = result.model_dump(by_alias=True, exclude_none=True)
    receipt_b64 = base64.b64encode(json.dumps(settlement).encode()).decode()
    return JSONResponse(
        status_code=200,
        content={"status": "settled", "receipt": receipt, "settlement": settlement},
        headers={X_PAYMENT_RESPONSE_HEADER: receipt_b64},
    )


async def _execute_paid_action(
    db: AsyncSession, action: str, req: SettleRequest, payment: dict
) -> dict:
    """Execute a verified-paid action and emit its canonical show event."""
    accepted = payment.get("accepted", {})
    inner = payment.get("payload", {})
    try:
        episode_id = uuid.UUID(req.show_id)
    except ValueError:
        raise HTTPException(400, "show_id must be a UUID")
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    if not ep_result.scalar_one_or_none():
        raise HTTPException(404, "show not found")

    if action == "pot":
        payload = {
            "amount_usdc": f"{int(accepted.get('amount', '0')) / 1_000_000:.2f}",
            "tx": (inner or {}).get("transaction", ""),
            "network": accepted.get("network", ""),
            "message": req.message,
            "source": "chain",
        }
        await emit_event(db, episode_id, POT_EVENT_TYPE, "chain", payload)
        await db.flush()
        return {"event": POT_EVENT_TYPE, "payload": payload}

    if action in ("message", "hype"):
        payload = {
            "kind": action,
            "message": req.message,
            "tx": (inner or {}).get("transaction", ""),
        }
        await emit_event(db, episode_id, "stage.flash", "chain", payload)
        await db.flush()
        return {"event": "stage.flash", "payload": payload}

    if action == "tip":
        payload = {
            "character_slug": req.target,
            "amount_usdc": f"{int(accepted.get('amount', '0')) / 1_000_000:.2f}",
            "tx": (inner or {}).get("transaction", ""),
            "message": req.message,
        }
        await emit_event(db, episode_id, "tip.received", "chain", payload)
        await db.flush()
        return {"event": "tip.received", "payload": payload}

    if action == "sponsor":
        raise HTTPException(400, "sponsor bids go through the auction, not direct settle")

    raise HTTPException(404, f"unknown paid action: {action}")


# ── Sponsor auction ──────────────────────────────────────────────────

_auctions: dict[str, SponsorAuction] = {}
AUCTION_CLOSE_OFFSET_SEC = 300  # closes at SHOW_START - 5 minutes


class BidRequest(BaseModel):
    bidder: str = Field(..., min_length=1, max_length=120)
    amount_cents: int = Field(..., gt=0)
    copy: str = Field(..., min_length=1, max_length=280)
    url: str = Field("", max_length=500)


def _get_auction(episode_id: str) -> SponsorAuction:
    auction = _auctions.get(episode_id)
    if not auction:
        raise HTTPException(404, "no auction for this episode")
    return auction


@router.post("/auctions/{episode_id}/open", status_code=201)
async def open_auction(
    episode_id: uuid.UUID,
    user: User = Depends(require_admin_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Admin: open the sponsor auction. Closes 5 min before show start."""
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "show not found")
    key = str(episode_id)
    if key in _auctions:
        raise HTTPException(409, "auction already open")
    start = episode.scheduled_at.timestamp() if episode.scheduled_at else time.time() + 3600
    _auctions[key] = SponsorAuction(key, close_at=start - AUCTION_CLOSE_OFFSET_SEC)
    return {"episode_id": key, "close_at": _auctions[key].close_at}


@router.post("/auctions/{episode_id}/bids", status_code=201)
async def place_bid(episode_id: str, req: BidRequest):
    """Place a sponsor bid. Intent only — no money moves until the winner pays."""
    auction = _get_auction(episode_id)
    try:
        bid = auction.place_bid(req.bidder, req.amount_cents, req.copy, req.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"bid_id": bid.bid_id, "moderation": bid.moderation}


@router.get("/auctions/{episode_id}")
async def auction_state(episode_id: str):
    """Public auction state: bids (copy visible), high bid, close time."""
    auction = _get_auction(episode_id)
    high = auction.highest_eligible()
    return {
        "episode_id": episode_id,
        "closed": auction.closed,
        "close_at": auction.close_at,
        "high_bid_cents": high.amount_cents if high else 0,
        "high_bidder": high.bidder if high else None,
        "bids": [
            {"bid_id": b.bid_id, "bidder": b.bidder, "amount_cents": b.amount_cents,
             "copy": b.copy, "moderation": b.moderation}
            for b in sorted(auction.bids.values(), key=lambda b: -b.amount_cents)
        ],
    }


class ModerateRequest(BaseModel):
    eligible: bool
    note: str = ""


@router.post("/auctions/{episode_id}/bids/{bid_id}/moderate")
async def moderate_bid(
    episode_id: str,
    bid_id: str,
    req: ModerateRequest,
    user: User = Depends(require_admin_from_api_key),
):
    """Admin: moderate ad copy. Money never buys immunity from moderation."""
    auction = _get_auction(episode_id)
    try:
        bid = auction.moderate(bid_id, req.eligible, req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"bid_id": bid.bid_id, "moderation": bid.moderation}


@router.post("/auctions/{episode_id}/close")
async def close_auction(
    episode_id: str,
    user: User = Depends(require_admin_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Admin: close the auction. Winner pays via x402; on settlement the
    amount enters the pot (source=sponsor)."""
    auction = _get_auction(episode_id)
    try:
        result = auction.close()
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        ep_uuid = uuid.UUID(episode_id)
    except ValueError:
        raise HTTPException(400, "episode_id must be a UUID")
    await emit_event(db, ep_uuid, "auction.closed", f"admin:{user.id}", {
        "winner_bid_id": result.winner_bid_id,
        "winner_bidder": result.winner_bidder,
        "winning_cents": result.winning_cents,
    })
    await db.flush()
    out = {
        "winner_bid_id": result.winner_bid_id,
        "winner_bidder": result.winner_bidder,
        "winning_cents": result.winning_cents,
    }
    if result.winner_bid_id:
        config = _network_config()
        if config.pay_to:
            out["pay"] = payment_required(
                "sponsor", f"freak-town:sponsor:{episode_id}",
                result.winning_cents, config,
            )
    return out


# ── FREAK TICKETs ────────────────────────────────────────────────────

@router.get("/tickets/balance")
async def ticket_balance(user: User = Depends(get_current_user_from_api_key)):
    return {"balance": ticket_wallet.balance(str(user.id))}


@router.post("/tickets/claim-weekly")
async def claim_weekly(user: User = Depends(get_current_user_from_api_key)):
    try:
        balance = ticket_wallet.claim_weekly(str(user.id))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"balance": balance}


class TicketGrantRequest(BaseModel):
    user_id: str
    source: str = "admin_grant"
    count: int = Field(1, gt=0, le=100)
    note: str = ""


@router.post("/tickets/grant")
async def grant_tickets(
    req: TicketGrantRequest,
    user: User = Depends(require_admin_from_api_key),
):
    try:
        balance = ticket_wallet.grant(req.user_id, req.source, req.count, req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"user_id": req.user_id, "balance": balance}


# ── Show finalize (deterministic payout plan) ────────────────────────

class FinalizeRequest(BaseModel):
    ella_wallet: str = Field(..., min_length=1)
    stream_wallet: str = Field("", description="empty = no Stream champion, 20% rolls to season")
    network: str = Field("eip155:84532")


@router.post("/shows/{episode_id}/finalize")
async def finalize_show(
    episode_id: uuid.UUID,
    req: FinalizeRequest,
    user: User = Depends(require_admin_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Admin: lock winners and emit the deterministic payout plan.

    Ella selects the official champion; Stream selects the People's
    Champion. 70/20/10 in integer atomic units, dust to season pot.
    The contract enforces this exact math on-chain; this endpoint is the
    off-chain record + claim instructions.
    """
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    if not ep_result.scalar_one_or_none():
        raise HTTPException(404, "show not found")

    ev_result = await db.execute(select(ShowEvent).where(ShowEvent.episode_id == episode_id))
    events = [
        {"type": e.type, "episode_id": str(e.episode_id), "payload": e.payload or {}}
        for e in ev_result.scalars().all()
    ]
    total_cents = pot_total(events)
    total_atomic = total_cents * 10_000  # cents → 6-decimal atomic

    payload = payout_event_payload(
        str(episode_id), req.ella_wallet, req.stream_wallet or None,
        total_atomic, req.network,
    )
    await emit_event(db, episode_id, "show.payout", f"admin:{user.id}", payload)
    await db.flush()
    return payload
