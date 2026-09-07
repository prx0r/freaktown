"""Comedian creator API — LEGACY Python implementation.

DO NOT ADD NEW FEATURES HERE.
This is retained temporarily during migration to TypeScript/Cloudflare.
Per peer review: "Never implement the same domain mutation independently in Python and TypeScript."

Canonical implementation lives in: apps/web/worker/api/index.ts
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_from_api_key
from backend.db import get_db
from backend.models import (
    Authorship,
    BodyArchetype,
    Comedian,
    ComedianStatus,
    InterviewController,
    ActVersion,
    User,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class ComedianCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    body_archetype: BodyArchetype
    premise: str = Field(..., min_length=1, max_length=500)
    character_deal: str = Field(..., min_length=1, max_length=1000)
    voice_profile: str = Field(default="default")
    minute_text: str = Field(..., min_length=1, max_length=2000)
    minute_authorship: Authorship = Authorship.HUMAN
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list)

    # SECURITY: These fields must NOT be accepted from the browser
    # owner_user_id is derived from auth token only
    # No creator_id, owner_user_id, or role fields allowed


class ActVersionCreateRequest(BaseModel):
    comedian_id: uuid.UUID
    character_deal: str = Field(..., min_length=1, max_length=1000)
    minute_text: str = Field(..., min_length=1, max_length=2000)
    voice_profile: str = Field(default="default")
    minute_authorship: Authorship = Authorship.HUMAN
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list)


class ActVersionResponse(BaseModel):
    id: uuid.UUID
    revision: int
    content_sha256: str
    sealed_at: str | None
    created_at: str

    model_config = {"from_attributes": True}


class ComedianResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    premise: str
    body_archetype: str
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


def canonicalize_manifest(manifest: dict) -> str:
    """Canonical JSON serialization. Recursively sorts object keys, preserves array order."""
    return json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def compute_hash(manifest: dict) -> str:
    """Compute full SHA-256 of canonical manifest. 64 hex chars. Never truncate."""
    canonical = canonicalize_manifest(manifest)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("", response_model=ComedianResponse, status_code=201)
async def create_comedian(
    req: ComedianCreateRequest,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create a comedian with first ActVersion. Owner derived from auth only."""

    # SECURITY: Owner comes from auth, NOT from request body
    owner_user_id = user.id

    # Slug: names NOT globally unique, only slugs must be unique
    slug = slugify(req.name)
    existing_slug = await db.execute(select(Comedian).where(Comedian.slug == slug))
    if existing_slug.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    # Create comedian
    comedian = Comedian(
        owner_user_id=owner_user_id,
        name=req.name,
        slug=slug,
        premise=req.premise,
        body_archetype=req.body_archetype,
    )
    db.add(comedian)
    await db.flush()

    # Build canonical manifest
    manifest = {
        "schemaVersion": 1,
        "character": {
            "name": req.name,
            "deal": req.character_deal,
            "facts": req.character_facts,
        },
        "body": {
            "family": req.body_archetype.value,
            "variant": None,
            "outfit": None,
        },
        "voice": {
            "voiceId": req.voice_profile,
        },
        "minute": {
            "text": req.minute_text,
            "authorship": req.minute_authorship.value,
            "assistance": [],
        },
        "interview": {
            "controller": req.interview_controller.value,
            "facts": req.character_facts,
        },
    }

    content_sha256 = compute_hash(manifest)

    # Create first ActVersion
    act = ActVersion(
        comedian_id=comedian.id,
        revision=1,
        created_by_user_id=owner_user_id,
        manifest=manifest,
        content_sha256=content_sha256,
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(act)
    await db.flush()

    await db.refresh(comedian, ["versions"])
    return comedian


@router.post("/{comedian_id}/acts", response_model=ActVersionResponse, status_code=201)
async def create_act_version(
    comedian_id: uuid.UUID,
    req: ActVersionCreateRequest,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create new immutable ActVersion. Owner derived from auth."""

    # Verify ownership
    result = await db.execute(select(Comedian).where(Comedian.id == comedian_id))
    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")
    if comedian.owner_user_id != user.id:
        raise HTTPException(403, "Not your comedian")

    # Find latest revision with row lock to prevent races
    from sqlalchemy import select, func
    latest_result = await db.execute(
        select(ActVersion)
        .where(ActVersion.comedian_id == comedian_id)
        .with_for_update()
        .order_by(ActVersion.revision.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    next_revision = (latest.revision + 1) if latest else 1
    parent_id = latest.id if latest else None

    # Build manifest
    manifest = {
        "schemaVersion": 1,
        "character": {
            "name": comedian.name,
            "deal": req.character_deal,
            "facts": req.character_facts,
        },
        "body": {
            "family": comedian.body_archetype.value,
            "variant": None,
            "outfit": None,
        },
        "voice": {
            "voiceId": req.voice_profile,
        },
        "minute": {
            "text": req.minute_text,
            "authorship": req.minute_authorship.value,
            "assistance": [],
        },
        "interview": {
            "controller": req.interview_controller.value,
            "facts": req.character_facts,
        },
    }

    content_sha256 = compute_hash(manifest)

    act = ActVersion(
        comedian_id=comedian_id,
        revision=next_revision,
        parent_act_version_id=parent_id,
        created_by_user_id=user.id,
        manifest=manifest,
        content_sha256=content_sha256,
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(act)

    try:
        await db.flush()
    except Exception as e:
        if "uq_act_version" in str(e):
            raise HTTPException(409, "Concurrent revision creation, retry")
        raise

    return act


@router.get("/{slug_or_id}", response_model=ComedianResponse)
async def get_comedian(slug_or_id: str, db: AsyncSession = Depends(get_db)):
    """Get comedian by slug or ID."""
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
    """List comedians."""
    query = select(Comedian).order_by(Comedian.created_at.desc()).limit(limit).offset(offset)
    if status != "all":
        query = query.where(Comedian.status == status)
    result = await db.execute(query)
    comedians = list(result.scalars().all())
    for c in comedians:
        await db.refresh(c, ["versions"])
    return comedians
