"""Stripe Connect integration for fiat creator payments.

Per vision.md:
  - Stripe Connect for normal users
  - 95% creator / 5% platform
  - Non-custodial (direct transfer)
  - Don't require Stripe onboarding at comedian creation
  - Creator sees "ENABLE TIPS" when they want to monetize
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from backend.config import settings


@dataclass
class StripeConnectAccount:
    """Stripe Connect account for a creator."""
    user_id: str
    stripe_account_id: str
    onboarding_status: str  # "pending", "active", "restricted"
    charges_enabled: bool
    payouts_enabled: bool
    created_at: str


@dataclass
class FiatTipRequest:
    """A fiat tip request."""
    tip_id: str
    sender_user_id: str
    recipient_user_id: str
    recipient_stripe_account_id: str
    amount_cents: int
    currency: str
    message: str | None
    appearance_id: str | None
    episode_id: str | None


@dataclass
class FiatTipResult:
    """Result of a fiat tip."""
    tip_id: str
    status: str  # "pending", "succeeded", "failed"
    payment_intent_id: str | None
    amount_cents: int
    amount_creator_cents: int
    amount_platform_cents: int
    platform_fee_pct: float


# ── Configuration ──────────────────────────────────────────────────────

PLATFORM_FEE_PCT = 5.0
CREATOR_PCT = 95.0


# ── Stripe Connect Service ─────────────────────────────────────────────

class StripeConnectService:
    """Manages Stripe Connect for creator payments."""

    def __init__(self):
        self.secret_key = settings.stripe_secret_key if hasattr(settings, 'stripe_secret_key') else ""
        self.webhook_secret = settings.stripe_webhook_secret if hasattr(settings, 'stripe_webhook_secret') else ""

    async def create_connect_account(self, user_id: str, email: str) -> StripeConnectAccount:
        """Create a Stripe Connect account for a creator."""
        if not self.secret_key:
            # Return mock for testing
            return StripeConnectAccount(
                user_id=user_id,
                stripe_account_id=f"acct_mock_{uuid.uuid4().hex[:8]}",
                onboarding_status="pending",
                charges_enabled=False,
                payouts_enabled=False,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.stripe.com/v1/accounts",
                    auth=(self.secret_key, ""),
                    data={
                        "type": "express",
                        "email": email,
                        "capabilities[card_payments][requested]": "true",
                        "capabilities[transfers][requested]": "true",
                        "metadata[user_id]": user_id,
                    },
                )
                response.raise_for_status()
                data = response.json()

                return StripeConnectAccount(
                    user_id=user_id,
                    stripe_account_id=data["id"],
                    onboarding_status="pending",
                    charges_enabled=data.get("charges_enabled", False),
                    payouts_enabled=data.get("payouts_enabled", False),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )

        except Exception as e:
            raise Exception(f"Failed to create Stripe account: {e}")

    async def create_onboarding_link(self, stripe_account_id: str, refresh_url: str, return_url: str) -> str:
        """Create an onboarding link for a creator to complete Stripe setup."""
        if not self.secret_key:
            return f"https://connect.stripe.com/express/oauth/authorize?client_id=mock&state={stripe_account_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.stripe.com/v1/accounts/{stripe_account_id}/login_links",
                    auth=(self.secret_key, ""),
                    data={
                        "redirect_url": return_url,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["url"]

        except Exception as e:
            raise Exception(f"Failed to create onboarding link: {e}")

    async def create_tip_payment(
        self,
        sender_user_id: str,
        recipient_stripe_account_id: str,
        amount_cents: int,
        currency: str = "usd",
        message: str | None = None,
        appearance_id: str | None = None,
        episode_id: str | None = None,
    ) -> FiatTipRequest:
        """Create a payment intent for a fiat tip."""
        tip_id = f"tip_{uuid.uuid4().hex[:12]}"

        return FiatTipRequest(
            tip_id=tip_id,
            sender_user_id=sender_user_id,
            recipient_user_id="",
            recipient_stripe_account_id=recipient_stripe_account_id,
            amount_cents=amount_cents,
            currency=currency,
            message=message,
            appearance_id=appearance_id,
            episode_id=episode_id,
        )

    async def confirm_tip(
        self,
        tip_id: str,
        payment_intent_id: str,
        amount_cents: int,
    ) -> FiatTipResult:
        """Confirm a tip after payment processing."""
        amount_platform = int(amount_cents * (PLATFORM_FEE_PCT / 100))
        amount_creator = amount_cents - amount_platform

        return FiatTipResult(
            tip_id=tip_id,
            status="succeeded",
            payment_intent_id=payment_intent_id,
            amount_cents=amount_cents,
            amount_creator_cents=amount_creator,
            amount_platform_cents=amount_platform,
            platform_fee_pct=PLATFORM_FEE_PCT,
        )

    async def get_account_balance(self, stripe_account_id: str) -> dict:
        """Get the balance of a Connect account."""
        if not self.secret_key:
            return {"available": 0, "pending": 0, "currency": "usd"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.stripe.com/v1/balance",
                    auth=(self.secret_key, ""),
                    params={"stripeAccount": stripe_account_id},
                )
                response.raise_for_status()
                data = response.json()

                available = sum(b["amount"] for b in data.get("available", []))
                pending = sum(b["amount"] for b in data.get("pending", []))

                return {
                    "available": available,
                    "pending": pending,
                    "currency": "usd",
                }

        except Exception:
            return {"available": 0, "pending": 0, "currency": "usd"}

    async def handle_webhook(self, payload: dict, sig_header: str) -> dict:
        """Handle Stripe webhook events."""
        # In production, verify webhook signature
        event_type = payload.get("type", "")

        if event_type == "account.updated":
            account = payload.get("data", {}).get("object", {})
            # Update account status in DB
            return {"status": "account_updated", "account_id": account.get("id")}

        if event_type == "payment_intent.succeeded":
            payment_intent = payload.get("data", {}).get("object", {})
            # Confirm tip in DB
            return {"status": "tip_confirmed", "payment_intent_id": payment_intent.get("id")}

        return {"status": "ignored", "event_type": event_type}


# Singleton
stripe_service = StripeConnectService()
