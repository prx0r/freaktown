"""Episode management — LEGACY Python implementation.

DO NOT ADD NEW FEATURES HERE.
Canonical implementation lives in: apps/web/worker/api/index.ts
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_from_api_key
from backend.db import get_db
from backend.models import (
    ActVersion,
    Appearance,
    Comedian,
    Episode,
    EpisodeStatus,
    ShowPhase,
    Submission,
    User,
)
from backend.services.events import emit_event

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class EpisodeCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    max_appearances: int = Field(default=5, ge=3, le=12)
    scheduled_at: datetime | None = None


class SubmitRequest(BaseModel):
    comedian_id: uuid.UUID
    act_version_id: uuid.UUID | None = None


class EpisodeResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    current_phase: str | None
    max_appearances: int
    submission_count: int
    created_at: str

    model_config = {"from_attributes": True}


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    req: EpisodeCreateRequest,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create episode. Admin only."""
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")

    episode = Episode(
        title=req.title,
        status=EpisodeStatus.OPEN,
        current_phase=ShowPhase.PRE_SHOW,
        max_appearances=req.max_appearances,
        scheduled_at=req.scheduled_at,
    )
    db.add(episode)
    await db.flush()
    await db.refresh(episode)
    return {
        "id": episode.id,
        "title": episode.title,
        "status": episode.status.value,
        "current_phase": episode.current_phase.value if episode.current_phase else None,
        "max_appearances": episode.max_appearances,
        "submission_count": 0,
        "created_at": str(episode.created_at),
    }


@router.get("/live")
async def get_live_episode(db: AsyncSession = Depends(get_db)):
    """Get current live episode."""
    result = await db.execute(
        select(Episode).where(Episode.status.in_([
            EpisodeStatus.LIVE, EpisodeStatus.READY, EpisodeStatus.OPEN
        ])).order_by(Episode.created_at.desc()).limit(1)
    )
    episode = result.scalar_one_or_none()
    if not episode:
        return {"episode": None}
    return {
        "episode": {
            "id": str(episode.id),
            "title": episode.title,
            "status": episode.status.value,
            "phase": episode.current_phase.value if episode.current_phase else None,
        }
    }


@router.get("/{episode_id}")
async def get_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get episode details."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")

    # Count submissions (not appearances!)
    sub_count = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.episode_id == episode_id)
    )

    return {
        "id": str(episode.id),
        "title": episode.title,
        "status": episode.status.value,
        "phase": episode.current_phase.value if episode.current_phase else None,
        "max_appearances": episode.max_appearances,
        "submission_count": sub_count.scalar(),
    }


@router.post("/{episode_id}/submit")
async def submit_to_episode(
    episode_id: uuid.UUID,
    req: SubmitRequest,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Submit a comedian to The Line. Creates Submission, NOT Appearance."""

    # Verify episode is open
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}, not open")

    # Verify comedian ownership
    com_result = await db.execute(select(Comedian).where(Comedian.id == req.comedian_id))
    comedian = com_result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")
    if comedian.owner_user_id != user.id:
        raise HTTPException(403, "Not your comedian")

    # Get act version (latest if not specified)
    if req.act_version_id:
        av_result = await db.execute(
            select(ActVersion).where(
                ActVersion.id == req.act_version_id,
                ActVersion.comedian_id == req.comedian_id,
            )
        )
    else:
        av_result = await db.execute(
            select(ActVersion)
            .where(ActVersion.comedian_id == req.comedian_id)
            .order_by(ActVersion.revision.desc())
            .limit(1)
        )
    act_version = av_result.scalar_one_or_none()
    if not act_version:
        raise HTTPException(404, "Act version not found")
    if not act_version.sealed_at:
        raise HTTPException(400, "Act version must be sealed before submission")

    # Check not already submitted
    existing = await db.execute(
        select(Submission).where(
            Submission.episode_id == episode_id,
            Submission.comedian_id == req.comedian_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already submitted to this episode")

    # Create Submission (NOT Appearance)
    submission = Submission(
        episode_id=episode_id,
        comedian_id=req.comedian_id,
        act_version_id=act_version.id,
        submitted_by_user_id=user.id,
    )
    db.add(submission)
    await db.flush()

    return {
        "submission_id": str(submission.id),
        "status": "submitted",
        "episode_id": str(episode_id),
        "comedian_name": comedian.name,
    }


@router.post("/{episode_id}/draw")
async def draw_contestants(
    episode_id: uuid.UUID,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Deterministic draw. Creates Appearances from selected Submissions."""

    if user.role != "admin":
        raise HTTPException(403, "Admin access required")

    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status not in (EpisodeStatus.OPEN, EpisodeStatus.LOCKED):
        raise HTTPException(400, "Episode not in drawable state")

    # Get all eligible submissions
    eligible_result = await db.execute(
        select(Submission).where(Submission.episode_id == episode_id)
    )
    submissions = list(eligible_result.scalars().all())

    if not submissions:
        raise HTTPException(400, "No eligible submissions")

    # Use deterministic draw (not random.shuffle!)
    from backend.services.draw import generate_seed, execute_draw, commit_seed

    seed, seed_hex = generate_seed()
    submission_ids = [str(s.id) for s in submissions]

    draw_result = execute_draw(
        eligible_ids=submission_ids,
        seed=seed,
        random_slots=episode.max_appearances - 1,
        resident_slots=1,
        resident_ids=[submission_ids[0]] if submission_ids else [],
    )

    # Create Appearances from selected submissions
    appearances = []
    for i, sub_id in enumerate(draw_result.selected_ids):
        submission = next((s for s in submissions if str(s.id) == sub_id), None)
        if not submission:
            continue

        appearance = Appearance(
            episode_id=episode_id,
            submission_id=submission.id,
            draw_position=i + 1,
        )
        db.add(appearance)
        appearances.append(appearance)

    # Store draw verification data
    episode.eligible_set_hash = draw_result.eligible_set_hash
    episode.seed_commitment = draw_result.seed_commitment
    episode.seed_revealed = seed_hex
    episode.draw_result_json = {
        "algorithm": draw_result.algorithm,
        "selected_ids": draw_result.selected_ids,
        "resident_ids": draw_result.resident_ids,
    }

    await emit_event(
        db, episode_id,
        "show.phase", "system",
        {"phase": "draw", "drawn": draw_result.selected_ids},
    )

    await db.flush()

    return {
        "drawn": len(appearances),
        "algorithm": draw_result.algorithm,
        "seed_commitment": draw_result.seed_commitment,
    }


@router.post("/{episode_id}/lock")
async def lock_episode(
    episode_id: uuid.UUID,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Lock the lineup."""
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")

    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}")

    episode.status = EpisodeStatus.LOCKED
    episode.version += 1

    await emit_event(db, episode_id, "show.phase", "system", {"phase": "locked"})
    await db.flush()

    return {"status": "locked", "version": episode.version}


@router.post("/{episode_id}/start")
async def start_episode(
    episode_id: uuid.UUID,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Start the live show."""
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")

    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status not in (EpisodeStatus.LOCKED, EpisodeStatus.READY):
        raise HTTPException(400, f"Episode is {episode.status.value}")

    episode.status = EpisodeStatus.LIVE
    episode.current_phase = ShowPhase.INTRO
    episode.started_at = datetime.now(timezone.utc)
    episode.version += 1

    await emit_event(
        db, episode_id, "show.phase", "system",
        {"phase": "intro", "title": episode.title},
        effective_at=datetime.now(timezone.utc),
    )
    await db.flush()

    return {"status": "live", "phase": "intro", "version": episode.version}
