"""Episode management and random draw engine.

  POST /v1/episodes                → create episode (admin)
  POST /v1/episodes/{id}/enter     → enter comedian into episode
  POST /v1/episodes/{id}/draw      → random draw from eligible pool
  POST /v1/episodes/{id}/lock      → lock lineup
  POST /v1/episodes/{id}/start     → start live show
  GET  /v1/episodes/live           → get current live episode
  GET  /v1/episodes/{id}           → get episode detail
"""

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    SubmissionStatus,
    ActVersion,
    Comedian,
    Episode,
    Appearance,
    EpisodeStatus,
    ShowEvent,
    ShowEventType,
    ShowPhase,
)
from backend.services.events import emit_event, get_next_seq

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class EpisodeCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    max_contestants: int = Field(default=5, ge=3, le=12)
    scheduled_at: datetime | None = None


class EnterContestantRequest(BaseModel):
    comedian_id: uuid.UUID
    act_version_id: uuid.UUID | None = None  # if None, use latest


class DrawResult(BaseModel):
    contestant_id: uuid.UUID
    comedian_name: str
    draw_position: int
    act_version: int
    is_resident: bool


class EpisodeResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    current_phase: str | None
    max_contestants: int
    scheduled_at: str | None
    started_at: str | None
    ended_at: str | None
    contestant_count: int
    created_at: str

    model_config = {"from_attributes": True}


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("", response_model=EpisodeResponse, status_code=201)
async def create_episode(req: EpisodeCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new episode. Opens for registration."""
    episode = Episode(
        title=req.title,
        status=EpisodeStatus.OPEN,
        current_phase=ShowPhase.PRE_SHOW,
        max_contestants=req.max_contestants,
        scheduled_at=req.scheduled_at,
    )
    db.add(episode)
    await db.flush()
    await db.refresh(episode)
    episode_dict = {
        "id": episode.id,
        "title": episode.title,
        "status": episode.status.value,
        "current_phase": episode.current_phase.value if episode.current_phase else None,
        "max_contestants": episode.max_contestants,
        "scheduled_at": str(episode.scheduled_at) if episode.scheduled_at else None,
        "started_at": str(episode.started_at) if episode.started_at else None,
        "ended_at": str(episode.ended_at) if episode.ended_at else None,
        "contestant_count": 0,
        "created_at": str(episode.created_at),
    }
    return episode_dict


@router.get("/live")
async def get_live_episode(db: AsyncSession = Depends(get_db)):
    """Get the current live episode, if any."""
    result = await db.execute(
        select(Episode).where(Episode.status.in_([EpisodeStatus.LIVE, EpisodeStatus.READY, EpisodeStatus.OPEN]))
        .order_by(Episode.created_at.desc())
        .limit(1)
    )
    episode = result.scalar_one_or_none()
    if not episode:
        return {"episode": None}

    await db.refresh(episode, ["contestants"])
    return {
        "episode": {
            "id": str(episode.id),
            "title": episode.title,
            "status": episode.status.value,
            "current_phase": episode.current_phase.value if episode.current_phase else None,
            "contestant_count": len(episode.contestants),
        }
    }


@router.get("/{episode_id}")
async def get_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get episode detail with contestants."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")

    await db.refresh(episode, ["contestants"])
    contestants = []
    for c in episode.contestants:
        await db.refresh(c, ["comedian", "act_version"])
        contestants.append({
            "id": str(c.id),
            "comedian_name": c.comedian.name if c.comedian else "?",
            "draw_position": c.draw_position,
            "is_resident": c.is_resident,
            "status": c.qualification_status.value,
            "act_version": c.act_version.version if c.act_version else 0,
            "peak_laugh_share": c.peak_laugh_share,
            "ella_verdict": c.ella_verdict,
            "model_revealed": c.model_revealed,
        })

    return {
        "id": str(episode.id),
        "title": episode.title,
        "status": episode.status.value,
        "current_phase": episode.current_phase.value if episode.current_phase else None,
        "max_contestants": episode.max_contestants,
        "contestants": contestants,
        "created_at": str(episode.created_at),
    }


@router.post("/{episode_id}/enter")
async def enter_contestant(
    episode_id: uuid.UUID,
    req: EnterContestantRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enter a comedian into an episode's eligible pool."""
    # Check episode exists and is open
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}, not open for entries")

    # Check comedian exists
    com_result = await db.execute(select(Comedian).where(Comedian.id == req.comedian_id))
    comedian = com_result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")

    # Check not already entered
    existing = await db.execute(
        select(Appearance).where(
            Appearance.episode_id == episode_id,
            Appearance.comedian_id == req.comedian_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Comedian already entered in this episode")

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

    # Check capacity
    count_result = await db.execute(
        select(func.count()).select_from(Appearance).where(Appearance.episode_id == episode_id)
    )
    count = count_result.scalar()
    if count >= episode.max_contestants:
        raise HTTPException(400, f"Episode full ({episode.max_contestants} max)")

    link = Appearance(
        episode_id=episode_id,
        comedian_id=req.comedian_id,
        act_version_id=act_version.id,
    )
    db.add(link)
    await db.flush()

    return {"status": "entered", "contestant_id": str(link.id)}


@router.post("/{episode_id}/draw", response_model=list[DrawResult])
async def draw_contestants(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Random draw from eligible pool. Assigns draw positions."""
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status not in (EpisodeStatus.OPEN, EpisodeStatus.LOCKED):
        raise HTTPException(400, "Episode not in a drawable state")

    # Get all eligible
    eligible_result = await db.execute(
        select(Appearance).where(
            Appearance.episode_id == episode_id,
        )
    )
    eligible = list(eligible_result.scalars().all())

    if not eligible:
        raise HTTPException(400, "No eligible contestants to draw")

    # Random shuffle
    random.shuffle(eligible)

    results = []
    for i, contestant in enumerate(eligible):
        contestant.draw_position = i + 1
        db.add(contestant)

        await db.refresh(contestant, ["comedian", "act_version"])
        results.append(DrawResult(
            contestant_id=contestant.id,
            comedian_name=contestant.comedian.name,
            draw_position=i + 1,
            act_version=contestant.act_version.revision,
            is_resident=contestant.draw_position == 1,  # first position is resident
        ))

    # Emit draw event with auto-assigned seq
    await emit_event(
        db, episode_id,
        ShowEventType.SHOW_PHASE,
        "system",
        {"phase": "draw", "drawn": [str(r.contestant_id) for r in results]},
    )

    await db.flush()
    return results


@router.post("/{episode_id}/lock")
async def lock_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Lock the lineup. No more entries or draws."""
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}")

    episode.status = EpisodeStatus.LOCKED
    episode.version += 1

    await emit_event(
        db, episode_id,
        ShowEventType.SHOW_PHASE,
        "system",
        {"phase": "locked"},
    )

    await db.flush()

    return {"status": "locked", "version": episode.version}


@router.post("/{episode_id}/start")
async def start_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Start the live show."""
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

    # Emit show start event with auto-assigned seq
    await emit_event(
        db, episode_id,
        ShowEventType.SHOW_PHASE,
        "system",
        {"phase": "intro", "title": episode.title},
        effective_at=datetime.now(timezone.utc),
    )

    await db.flush()

    return {"status": "live", "phase": "intro", "version": episode.version}
