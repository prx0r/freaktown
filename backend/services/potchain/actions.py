"""Paid actions — x402 v2 payment requirements for Freak Town.

x402 is the payment interface. The smart contract is the money.

Five funny endpoints, all settled in USDC (Base by default, testnet
unless configured for mainnet):

  pot      $1+  → contribute to tonight's pot
  message  $2   → flash your message on screen
  hype     $5   → ridiculous animation/SFX
  sponsor  bid  → compete for the sponsor slot (auction)
  tip      $1+  → direct character tip

Flow per x402 v2 (exact scheme, EIP-3009 authorization):
  1. client requests the action
  2. server responds 402 + base64 PAYMENT-REQUIRED header
  3. client returns signed payment authorization (PAYMENT-SIGNATURE)
  4. server verifies via facilitator, executes, settles

Every settled payment becomes a canonical show event (pot.contribution,
tip.received, etc.) with tx + amount + set_time_ms — payment enters the
show timeline. That's content.

Networks (CAIP-2): eip155:8453 Base mainnet, eip155:84532 Base Sepolia.
Amounts are atomic USDC units (6 decimals) as strings, per spec.
"""

import base64
import json
import os
from dataclasses import dataclass, field

from x402.http.constants import (
    PAYMENT_REQUIRED_HEADER,
    PAYMENT_SIGNATURE_HEADER,
    X_PAYMENT_HEADER,
    X_PAYMENT_RESPONSE_HEADER,
)
from x402.schemas import PaymentPayload, PaymentRequired, ResourceInfo
from x402.schemas import PaymentRequirements as SDKRequirements

X402_VERSION = 2
SCHEME_EXACT = "exact"

# CAIP-2 network ids
BASE_MAINNET = "eip155:8453"
BASE_SEPOLIA = "eip155:84532"

# USDC (EIP-3009) on each network.
# Canonical native USDC, verified against Circle docs + the official x402
# SDK's DEFAULT_ASSETS (test_ asset constants below assert equality so any
# drift fails loudly — a wrong token address loses real money).
USDC_BASE_MAINNET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

# Solana USDC mints, canonical per the official x402 SDK (svm constants).
USDC_SOLANA_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_SOLANA_DEVNET = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"

SOLANA_MAINNET = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
SOLANA_DEVNET = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"

USDC_DECIMALS = 6

# Fixed-price actions in USD cents. Sponsor is a dynamic bid (auction).
ACTION_PRICES_CENTS: dict[str, int] = {
    "pot": 100,      # $1+ minimum; client may pay more (upto handled later)
    "message": 200,  # $2
    "hype": 500,     # $5
    "tip": 100,      # $1+ minimum
}

MAX_TIMEOUT_SECONDS = 300


def usd_cents_to_atomic(cents: int, decimals: int = USDC_DECIMALS) -> str:
    """$1.00 (100 cents) → 1000000 atomic USDC units, as spec string."""
    if not isinstance(cents, int) or cents <= 0:
        raise ValueError("cents must be a positive integer")
    if decimals < 2:
        raise ValueError("decimals must be >= 2 for cent pricing")
    return str(cents * 10 ** (decimals - 2))


def atomic_to_usd_cents(atomic: str | int) -> int:
    units = int(atomic)
    if units <= 0:
        raise ValueError("atomic amount must be positive")
    if units % 10 ** (USDC_DECIMALS - 2) != 0:
        raise ValueError("atomic amount is not whole-cent representable")
    return units // 10 ** (USDC_DECIMALS - 2)


@dataclass
class PaidAction:
    """One monetized show action."""
    name: str  # pot | message | hype | sponsor | tip
    description: str
    min_cents: int
    variable_amount: bool = False  # True when the payer chooses >= min
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "min_cents": self.min_cents,
            "variable_amount": self.variable_amount,
            "extra": self.extra,
        }


ACTIONS: dict[str, PaidAction] = {
    "pot": PaidAction(
        name="pot", min_cents=100, variable_amount=True,
        description="Contribute $1+ to tonight's pot. The number goes up live.",
    ),
    "message": PaidAction(
        name="message", min_cents=200,
        description="Flash your message on screen for a few seconds.",
    ),
    "hype": PaidAction(
        name="hype", min_cents=500,
        description="Trigger a ridiculous animation + SFX on stage.",
    ),
    "sponsor": PaidAction(
        name="sponsor", min_cents=100, variable_amount=True,
        description="Bid for the next show ad read. Highest eligible bid wins; Ella reads it.",
    ),
    "tip": PaidAction(
        name="tip", min_cents=100, variable_amount=True,
        description="Direct character tip. 95% creator / 5% Freak Town.",
    ),
}


@dataclass
class PaymentOption:
    """One way to pay: a network + asset + recipient.

    The accepts[] array is what makes the endpoint multichain — the
    client (wallet, modal, agent) picks whichever option it can sign for.
    USDC is 6 decimals on every supported chain, so amounts translate 1:1.
    """
    network: str
    asset: str
    pay_to: str
    decimals: int = 6
    label: str = ""


@dataclass
class NetworkConfig:
    """Multichain endpoint config: one PaymentOption per accepted chain."""

    options: list[PaymentOption] = field(default_factory=list)
    mainnet: bool = False

    @classmethod
    def sepolia(cls, pay_to: str = "") -> "NetworkConfig":
        return cls(options=[PaymentOption(
            network=BASE_SEPOLIA, asset=USDC_BASE_SEPOLIA,
            pay_to=pay_to, label="Base Sepolia",
        )])

    @classmethod
    def mainnet(cls, pay_to: str) -> "NetworkConfig":
        return cls(options=[PaymentOption(
            network=BASE_MAINNET, asset=USDC_BASE_MAINNET,
            pay_to=pay_to, label="Base",
        )], mainnet=True)

    @classmethod
    def multichain(cls, evm_pay_to: str = "", svm_pay_to: str = "",
                   networks: list[str] | None = None) -> "NetworkConfig":
        """Build options for any subset of known chains.

        Unknown network ids raise ValueError — offering a chain we have
        no asset/recipient for would strand user funds.
        """
        known: dict[str, PaymentOption] = {
            BASE_SEPOLIA: PaymentOption(BASE_SEPOLIA, USDC_BASE_SEPOLIA, evm_pay_to, label="Base Sepolia"),
            BASE_MAINNET: PaymentOption(BASE_MAINNET, USDC_BASE_MAINNET, evm_pay_to, label="Base"),
            SOLANA_DEVNET: PaymentOption(SOLANA_DEVNET, USDC_SOLANA_DEVNET, svm_pay_to, label="Solana Devnet"),
            SOLANA_MAINNET: PaymentOption(SOLANA_MAINNET, USDC_SOLANA_MAINNET, svm_pay_to, label="Solana"),
        }
        networks = networks if networks is not None else [BASE_SEPOLIA]
        options = []
        for net in networks:
            net = net.strip()
            if net not in known:
                raise ValueError(f"unknown x402 network: {net}")
            opt = known[net]
            if not opt.pay_to:
                continue  # no recipient on this chain → don't offer it
            options.append(opt)
        mainnet = any(n in (BASE_MAINNET, SOLANA_MAINNET) for n in networks)
        return cls(options=options, mainnet=mainnet)

    # Back-compat: single-chain view (first option) for legacy callers.
    @property
    def network(self) -> str:
        return self.options[0].network if self.options else ""

    @property
    def usdc(self) -> str:
        return self.options[0].asset if self.options else ""

    @property
    def pay_to(self) -> str:
        return self.options[0].pay_to if self.options else ""


def payment_required(
    action: str,
    resource_url: str,
    amount_cents: int,
    config: NetworkConfig,
    service_name: str = "Freak Town",
) -> dict:
    """Build a spec-conformant x402 v2 PaymentRequired object.

    Built on the official x402 SDK pydantic models (single source of
    truth for the wire shape), with Freak Town's action catalog supplying
    amounts and descriptions.

    Raises ValueError for unknown actions or amounts below the minimum.
    The caller is responsible for the 402 + PAYMENT-REQUIRED transport.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown paid action: {action}")
    spec = ACTIONS[action]
    if amount_cents < spec.min_cents:
        raise ValueError(f"{action} requires at least ${spec.min_cents / 100:.2f}")
    # Chains without a recipient are never offered (never strand funds).
    options = [o for o in config.options if o.pay_to]
    if not options:
        raise ValueError("no pot escrow address configured (set pay_to)")

    accepts = [
        SDKRequirements(
            scheme=SCHEME_EXACT,
            network=opt.network,  # type: ignore[arg-type]
            amount=usd_cents_to_atomic(amount_cents, opt.decimals),
            asset=opt.asset,
            pay_to=opt.pay_to,
            max_timeout_seconds=MAX_TIMEOUT_SECONDS,
            extra={"name": "USDC", "version": "2"},
        )
        for opt in options
    ]

    required = PaymentRequired(
        x402_version=X402_VERSION,
        error="PAYMENT-SIGNATURE header is required",
        resource=ResourceInfo(
            url=resource_url,
            description=spec.description,
            mime_type="application/json",
            service_name=service_name[:32],
            tags=["freak-town", action],
        ),
        accepts=accepts,
        extensions={},
    )
    return required.model_dump(by_alias=True, exclude_none=True)


def encode_payment_required(obj: dict) -> str:
    """Base64 value for the PAYMENT-REQUIRED response header."""
    return base64.b64encode(json.dumps(obj).encode()).decode()


def decode_payment_required(header: str) -> dict:
    return json.loads(base64.b64decode(header).decode())


def parse_payment_payload(data: dict | str) -> PaymentPayload:
    """Parse a client payment submission into an SDK v2 PaymentPayload.

    Accepts a dict (JSON body) or base64 (X-PAYMENT header — the transport
    the three.ws modal uses). Raises ValueError with an x402 error code
    for anything else, including v1 payloads (not accepted; clients must
    speak v2).
    """
    if isinstance(data, str):
        try:
            data = json.loads(base64.b64decode(data).decode())
        except Exception:
            raise ValueError("invalid_payload")
    if not isinstance(data, dict):
        raise ValueError("invalid_payload")
    if data.get("x402Version") == 1:
        raise ValueError("invalid_x402_version: v1 payloads not accepted, send v2")
    try:
        return PaymentPayload.model_validate(data)
    except Exception:
        raise ValueError("invalid_payload")


def match_accepted(payload: dict, required: dict) -> dict | None:
    """Find the accepts[] entry the client's payload satisfies.

    The client picks whichever chain it can sign for; the server must
    honor any offered option, not just the first. Returns the matched
    requirements entry, or None.
    """
    try:
        parsed = parse_payment_payload(payload)
    except ValueError:
        return None
    accepted = parsed.accepted.model_dump(by_alias=True)
    for want in required.get("accepts", []):
        if not isinstance(want, dict):
            continue
        if any(accepted.get(k) != want.get(k) for k in ("scheme", "network", "asset", "payTo")):
            continue
        try:
            if int(accepted.get("amount", "0")) < int(want["amount"]):
                continue
        except (ValueError, TypeError):
            continue
        return want
    return None


def validate_payment_payload(payload: dict, required: dict) -> tuple[bool, str]:
    """Structural pre-check of a client payload against requirements.

    Parses via the SDK models and checks the accepted terms cover the
    requirement. Cryptographic verification and settlement happen via
    the facilitator — this only rejects obvious junk before we get there.
    Returns (ok, reason).
    """
    try:
        parsed = parse_payment_payload(payload)
    except ValueError as e:
        return False, str(e)
    if not parsed.payload.get("signature") or not parsed.payload.get("authorization"):
        return False, "invalid_payload"
    if match_accepted(payload, required) is None:
        # Distinguish wrong-chain/asset/recipient from underpayment.
        accepted = parsed.accepted.model_dump(by_alias=True)
        want = (required.get("accepts") or [{}])[0]
        for key in ("scheme", "network", "asset", "payTo"):
            if accepted.get(key) != want.get(key):
                return False, "invalid_payment_requirements"
        return False, "invalid_exact_evm_payload_authorization_value_mismatch"
    return True, ""


def get_facilitator():
    """HTTPFacilitatorClient from FACILITATOR_URL, or None if unset."""
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient

    url = os.getenv("FACILITATOR_URL", "")
    if not url:
        return None
    return HTTPFacilitatorClient(FacilitatorConfig(url=url))
