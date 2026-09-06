"""Privy wallet integration for creator tips.

Per vision.md:
  - 95% creator / 5% Freak Town
  - Non-custodial (direct transfer, no escrow)
  - Solana + USDC
  - Privy handles auth + embedded wallets
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from backend.config import settings


@dataclass
class WalletInfo:
    """Creator's wallet information."""
    user_id: str
    wallet_address: str
    chain: str  # "solana"
    isEmbedded: bool  # True if created by Privy


@dataclass
class TipRequest:
    """A tip request from an audience member."""
    tip_id: str
    sender_user_id: str
    recipient_comedian_id: str
    recipient_wallet: str
    amount_usdc: float
    message: str | None
    appearance_id: str | None
    episode_id: str | None


@dataclass
class TipResult:
    """Result of a tip transaction."""
    tip_id: str
    status: str  # "pending", "confirmed", "failed"
    tx_hash: str | None
    amount_creator: float
    amount_platform: float
    platform_fee_pct: float


# ── Fee Configuration ──────────────────────────────────────────────────

PLATFORM_FEE_PCT = 5.0  # 5% to Freak Town
CREATOR_PCT = 95.0  # 95% to creator

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"


# ── Privy Integration ──────────────────────────────────────────────────

class PrivyWalletService:
    """Manages wallets via Privy."""

    def __init__(self):
        self.app_id = settings.privy_app_id if hasattr(settings, 'privy_app_id') else ""
        self.app_secret = settings.privy_app_secret if hasattr(settings, 'privy_app_secret') else ""

    async def get_user_wallet(self, privy_user_id: str) -> WalletInfo | None:
        """Get the user's embedded Solana wallet from Privy."""
        if not self.app_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                # Get user from Privy
                response = await client.get(
                    f"https://auth.privy.io/api/v1/users/{privy_user_id}",
                    headers={
                        "Authorization": f"Bearer {self._get_auth_token()}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                user_data = response.json()

                # Extract Solana wallet
                for wallet in user_data.get("linked_accounts", []):
                    if wallet.get("type") == "wallet" and wallet.get("chain_type") == "solana":
                        return WalletInfo(
                            user_id=privy_user_id,
                            wallet_address=wallet["address"],
                            chain="solana",
                            isEmbedded=wallet.get("is_custom", False) == False,
                        )

        except Exception:
            pass

        return None

    async def create_wallet(self, privy_user_id: str) -> WalletInfo | None:
        """Create an embedded Solana wallet for a user via Privy."""
        if not self.app_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://auth.privy.io/api/v1/users/{privy_user_id}/wallets",
                    headers={
                        "Authorization": f"Bearer {self._get_auth_token()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "chain_type": "solana",
                    },
                )
                response.raise_for_status()
                wallet_data = response.json()

                return WalletInfo(
                    user_id=privy_user_id,
                    wallet_address=wallet_data["address"],
                    chain="solana",
                    isEmbedded=True,
                )

        except Exception:
            pass

        return None

    def _get_auth_token(self) -> str:
        """Generate Privy auth token."""
        import hashlib
        import hmac
        import time

        now = int(time.time())
        message = f"{self.app_id}:{now}"
        signature = hmac.new(
            self.app_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return f"{self.app_id}:{now}:{signature}"


# ── Tip Processing ─────────────────────────────────────────────────────

class TipService:
    """Processes tips between audience and creators."""

    def __init__(self):
        self.privy = PrivyWalletService()

    async def initiate_tip(
        self,
        sender_user_id: str,
        recipient_comedian_id: str,
        amount_usdc: float,
        message: str | None = None,
        appearance_id: str | None = None,
        episode_id: str | None = None,
        db=None,
    ) -> TipRequest:
        """Initiate a tip from audience member to creator."""

        # Get recipient's wallet
        # (In production, look up from users table via comedian.owner_user_id)

        tip_id = f"tip_{uuid.uuid4().hex[:12]}"

        return TipRequest(
            tip_id=tip_id,
            sender_user_id=sender_user_id,
            recipient_comedian_id=recipient_comedian_id,
            recipient_wallet="",  # looked up from DB
            amount_usdc=amount_usdc,
            message=message,
            appearance_id=appearance_id,
            episode_id=episode_id,
        )

    async def confirm_tip(
        self,
        tip_id: str,
        tx_hash: str,
        amount_usdc: float,
        db=None,
    ) -> TipResult:
        """Confirm a tip after blockchain verification."""

        amount_platform = amount_usdc * (PLATFORM_FEE_PCT / 100)
        amount_creator = amount_usdc - amount_platform

        return TipResult(
            tip_id=tip_id,
            status="confirmed",
            tx_hash=tx_hash,
            amount_creator=amount_creator,
            amount_platform=amount_platform,
            platform_fee_pct=PLATFORM_FEE_PCT,
        )

    async def get_creator_earnings(
        self,
        user_id: str,
        db=None,
    ) -> dict:
        """Get total earnings for a creator."""
        # Query from DB in production
        return {
            "user_id": user_id,
            "total_earned_usdc": 0.0,
            "total_tips": 0,
            "platform_fees_paid": 0.0,
        }


# Singleton
tip_service = TipService()
privy_wallet_service = PrivyWalletService()
