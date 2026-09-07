"""On-chain POT — x402 payments in, USDC escrow, deterministic payouts.

Architecture: x402 is the payment interface, the contract is the money.

  actions.py  — x402 v2 PaymentRequired builder for the 5 paid actions
  escrow.py   — PotEscrow interface + LocalPotEscrow (contract mirror)
  payouts.py  — 70/20/10 deterministic split (ella/stream/season)
  auction.py  — sponsor auction (intents → moderation → close → pay)
  tickets.py  — FREAK TICKET submission credits (not crypto, not tradeable)

$FREAK policy: no token until a real utility emerges. Entry is free;
tickets are credits, not assets.
"""

from backend.services.potchain.actions import (
    X402_VERSION,
    SCHEME_EXACT,
    BASE_MAINNET,
    BASE_SEPOLIA,
    USDC_BASE_MAINNET,
    USDC_BASE_SEPOLIA,
    USDC_DECIMALS,
    ACTION_PRICES_CENTS,
    MAX_TIMEOUT_SECONDS,
    PAYMENT_REQUIRED_HEADER,
    PAYMENT_SIGNATURE_HEADER,
    X_PAYMENT_HEADER,
    X_PAYMENT_RESPONSE_HEADER,
    PaidAction,
    ACTIONS,
    NetworkConfig,
    usd_cents_to_atomic,
    atomic_to_usd_cents,
    payment_required,
    encode_payment_required,
    decode_payment_required,
    parse_payment_payload,
    validate_payment_payload,
    get_facilitator,
)
from backend.services.potchain.escrow import (
    Contribution,
    PotView,
    PotEscrow,
    LocalPotEscrow,
)
from backend.services.potchain.payouts import (
    ELLA_BPS,
    STREAM_BPS,
    SEASON_BPS,
    split_pot,
    payout_event_payload,
)
from backend.services.potchain.auction import (
    Bid,
    AuctionResult,
    SponsorAuction,
)
from backend.services.potchain.tickets import (
    VALID_SOURCES,
    TicketGrant,
    TicketWallet,
    ticket_wallet,
)

__all__ = [
    "X402_VERSION", "SCHEME_EXACT",
    "BASE_MAINNET", "BASE_SEPOLIA",
    "USDC_BASE_MAINNET", "USDC_BASE_SEPOLIA", "USDC_DECIMALS",
    "ACTION_PRICES_CENTS", "MAX_TIMEOUT_SECONDS",
    "PAYMENT_REQUIRED_HEADER", "PAYMENT_SIGNATURE_HEADER",
    "X_PAYMENT_HEADER", "X_PAYMENT_RESPONSE_HEADER",
    "PaidAction", "ACTIONS", "NetworkConfig",
    "usd_cents_to_atomic", "atomic_to_usd_cents",
    "payment_required", "encode_payment_required", "decode_payment_required",
    "parse_payment_payload", "validate_payment_payload", "get_facilitator",
    "Contribution", "PotView", "PotEscrow", "LocalPotEscrow",
    "ELLA_BPS", "STREAM_BPS", "SEASON_BPS",
    "split_pot", "payout_event_payload",
    "Bid", "AuctionResult", "SponsorAuction",
    "VALID_SOURCES", "TicketGrant", "TicketWallet", "ticket_wallet",
]
