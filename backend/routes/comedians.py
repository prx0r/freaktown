"""Comedian creator API.

The 2-minute flow:
  POST /v1/comedians              → create comedian + first ActVersion
  GET  /v1/comedians/{slug}       → view comedian + versions
  POST /v1/comedians/{id}/acts    → submit a new act version
"""

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    Authorship,
    BodyArchetype,
    Comedian,
    ComedianStatus,
    InterviewController,
    ActVersion,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class ComedianCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    body_archetype: BodyArchetype
    premise: str = Field(..., min_length=1, max_length=500, description="One sentence: who/what are they?")

    # Act version fields (first act)
    character_deal: str = Field(..., min_length=1, max_length=1000, description="What's their deal?")
    voice_profile: str = Field(default="default", max_length=100)
    minute_text: str = Field(..., min_length=1, max_length=2000, description="Their 60-second minute")
    minute_authorship: Authorship = Authorship.HUMAN

    # Interview config
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list, description="Comedy hooks: obsessed with / wrong with / hate discovering")

    # Optional
    creator_id: str | None = None
    body_appearance: str | None = None
    outfit: str | None = None
    entrance: str | None = None


class ActVersionCreateRequest(BaseModel):
    character_deal: str = Field(..., min_length=1, max_length=1000)
    voice_profile: str = Field(default="default", max_length=100)
    minute_text: str = Field(..., min_length=1, max_length=2000)
    minute_authorship: Authorship = Authorship.HUMAN
    minute_ai_assistance: str | None = None
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list)
    body_appearance: str | None = None
    outfit: str | None = None
    entrance: str | None = None
    exit_animation: str | None = None
    idle_animation: str | None = None
    creator_note: str | None = None


class ActVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    character_name: str
    character_deal: str
    minute_text: str
    minute_authorship: str
    voice_profile: str
    interview_controller: str
    character_facts: list | None
    content_hash: str
    created_at: str

    model_config = {"from_attributes": True}


class ComedianResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    body_archetype: str
    premise: str
    status: str
    created_at: str
    versions: list[ActVersionResponse]

    model_config = {"from_attributes": True}


# ── Helpers ────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def compute_hash(data: dict) -> str:
    content = "|".join(f"{k}={v}" for k, v in sorted(data.items()))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("", response_model=ComedianResponse, status_code=201)
async def create_comedian(req: ComedianCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a comedian with their first act version. The 2-minute entry point."""

    # Check uniqueness
    existing = await db.execute(select(Comedian).where(Comedian.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Comedian '{req.name}' already exists")

    slug = slugify(req.name)
    existing_slug = await db.execute(select(Comedian).where(Comedian.slug == slug))
    if existing_slug.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    # Create comedian
    comedian = Comedian(
        name=req.name,
        slug=slug,
        body_archetype=req.body_archetype,
        premise=req.premise,
    )
    db.add(comedian)
    await db.flush()

    # Create first act version
    content_hash = compute_hash({
        "comedian_id": str(comedian.id),
        "version": 1,
        "minute_text": req.minute_text,
        "character_deal": req.character_deal,
    })

    act = ActVersion(
        comedian_id=comedian.id,
        version=1,
        character_name=req.name,
        character_deal=req.character_deal,
        voice_profile=req.voice_profile,
        minute_text=req.minute_text,
        minute_authorship=req.minute_authorship,
        interview_controller=req.interview_controller,
        character_facts=req.character_facts if req.character_facts else None,
        body_appearance=req.body_appearance,
        outfit=req.outfit,
        entrance=req.entrance,
        creator_id=req.creator_id,
        content_hash=content_hash,
    )
    db.add(act)
    await db.flush()

    # Reload with relationships
    await db.refresh(comedian, ["versions"])
    return comedian


@router.get("/{slug_or_id}", response_model=ComedianResponse)
async def get_comedian(slug_or_id: str, db: AsyncSession = Depends(get_db)):
    """Get a comedian by slug or ID, with all act versions."""

    # Try UUID first
    try:
        uid = uuid.UUID(slug_or_id)
        result = await db.execute(select(Comedian).where(Comedian.id == uid))
    except ValueError:
        result = await db.execute(select(Comedian).where(Comedian.slug == slug_or_id))

    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")

    await db.refresh(comedian, ["versions"])
    return comedian


@router.get("", response_model=list[ComedianResponse])
async def list_comedians(
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List comedians in the pool."""
    query = select(Comedian).order_by(Comedian.created_at.desc()).limit(limit).offset(offset)
    if status != "all":
        query = query.where(Comedian.status == status)
    result = await db.execute(query)
    comedians = list(result.scalars().all())
    for c in comedians:
        await db.refresh(c, ["versions"])
    return comedians


@router.post("/{comedian_id}/acts", response_model=ActVersionResponse, status_code=201)
async def create_act_version(
    comedian_id: uuid.UUID,
    req: ActVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a new act version for an existing comedian. Creates immutable snapshot."""

    result = await db.execute(select(Comedian).where(Comedian.id == comedian_id))
    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")

    # Find latest version
    versions_result = await db.execute(
        select(ActVersion)
        .where(ActVersion.comedian_id == comedian_id)
        .order_by(ActVersion.version.desc())
        .limit(1)
    )
    latest = versions_result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1
    parent_id = latest.id if latest else None

    content_hash = compute_hash({
        "comedian_id": str(comedian_id),
        "version": next_version,
        "minute_text": req.minute_text,
        "character_deal": req.character_deal,
    })

    act = ActVersion(
        comedian_id=comedian_id,
        version=next_version,
        parent_version_id=parent_id,
        character_name=comedian.name,
        character_deal=req.character_deal,
        voice_profile=req.voice_profile,
        minute_text=req.minute_text,
        minute_authorship=req.minute_authorship,
        minute_ai_assistance=req.minute_ai_assistance,
        interview_controller=req.interview_controller,
        character_facts=req.character_facts if req.character_facts else None,
        body_appearance=req.body_appearance,
        outfit=req.outfit,
        entrance=req.entrance,
        exit_animation=req.exit_animation,
        idle_animation=req.idle_animation,
        creator_note=req.creator_note,
        content_hash=content_hash,
    )
    db.add(act)
    await db.flush()

    return act
