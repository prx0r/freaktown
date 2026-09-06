"""Sponsor campaign system.

Per vision.md:
  - OPENING_READ: 20-30 sec Ella read
  - TRANSITION: 5-10 sec visual
  - SPONSORED_CHALLENGE: "The Stripe 10-Word Challenge"
  - CHARACTER_SPONSOR: Brand backs a specific character

No self-serve auction initially. Manual campaigns first.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import Base


# ── Sponsor Models ─────────────────────────────────────────────────────

class SponsorCampaign(Base):
    """A sponsor campaign."""
    __tablename__ = "sponsor_campaigns_v2"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name = Column(String(200), nullable=False)
    placement = Column(String(50), nullable=False)  # OPENING_READ, TRANSITION, SPONSORED_CHALLENGE, CHARACTER_SPONSOR
    status = Column(String(20), nullable=False, default="draft")  # draft, approved, active, completed
    creative_json = Column(JSONB, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    budget_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SponsorCreative(Base):
    """Approved creative for a sponsor campaign."""
    __tablename__ = "sponsor_creatives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(50), nullable=False)  # "ella_read", "overlay", "challenge"
    content_json = Column(JSONB, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


# ── Sponsor Service ────────────────────────────────────────────────────

@dataclass
class SponsorPlacement:
    """A sponsor placement in an episode."""
    placement_type: str
    brand_name: str
    creative_type: str
    content: dict
    duration_ms: int


class SponsorService:
    """Manages sponsor campaigns."""

    PLACEMENTS = {
        "OPENING_READ": {"max_duration_ms": 30000, "description": "20-30 sec Ella read"},
        "TRANSITION": {"max_duration_ms": 10000, "description": "5-10 sec visual"},
        "SPONSORED_CHALLENGE": {"max_duration_ms": 60000, "description": "Sponsored challenge segment"},
        "CHARACTER_SPONSOR": {"max_duration_ms": 0, "description": "Brand backs a character"},
    }

    async def get_placements_for_episode(
        self,
        episode_id: str,
        db: AsyncSession,
    ) -> list[SponsorPlacement]:
        """Get all sponsor placements for an episode."""
        # In production, query from DB
        return []

    async def create_campaign(
        self,
        brand_name: str,
        placement: str,
        creative: dict,
        budget_usd: float | None = None,
        db: AsyncSession | None = None,
    ) -> dict:
        """Create a new sponsor campaign."""
        campaign_id = str(uuid.uuid4())

        return {
            "campaign_id": campaign_id,
            "brand_name": brand_name,
            "placement": placement,
            "status": "draft",
            "budget_usd": budget_usd,
        }

    async def approve_creative(
        self,
        campaign_id: str,
        creative_type: str,
        content: dict,
        db: AsyncSession | None = None,
    ) -> dict:
        """Approve creative for a campaign."""
        creative_id = str(uuid.uuid4())

        return {
            "creative_id": creative_id,
            "campaign_id": campaign_id,
            "type": creative_type,
            "status": "approved",
        }

    def generate_ella_read_prompt(
        self,
        brand_name: str,
        claims: list[str],
        required_phrase: str,
        cta: str,
        destination_url: str,
    ) -> str:
        """Generate a prompt for Ella's sponsor read."""
        return f"""You are Ella, host of Freak Town. Read this sponsor message in your voice.

Brand: {brand_name}
Key claims: {', '.join(claims)}
Required phrase: "{required_phrase}"
Call to action: {cta}
Link: {destination_url}

Rules:
- Sound like Ella, not a corporate ad
- Keep it under 30 seconds
- One mandatory mention of the required phrase
- End with the CTA
- Do not make claims not provided by the sponsor"""


# Singleton
sponsor_service = SponsorService()
