"""Admin control routes for episode lifecycle.

POST /v1/admin/episodes/{id}/pause
POST /v1/admin/episodes/{id}/resume
POST /v1/admin/episodes/{id}/skip
POST /v1/admin/episodes/{id}/end
POST /v1/admin/episodes/{id}/next-phase
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    Episode,
    EpisodeStatus,
    ShowEvent,
    ShowEventType,
    ShowPhase,
)
from backend.services.events import emit_event

router = APIRouter()


class PhaseTransition(BaseModel):
    phase: ShowPhase


# ── Phase ordering ─────────────────────────────────────────────────────

SHOW_PHASE_ORDER = [
    ShowPhase.PRE_SHOW,
    ShowPhase.INTRO,
    ShowPhase.LINEUP,
    ShowPhase.CONTESTANT_ENTER,
    ShowPhase.SET_ACTIVE,
    ShowPhase.POST_SET,
    ShowPhase.JUDGING,
    ShowPhase.ROAST,
    ShowPhase.TRANSITION,
    ShowPhase.LIVE_TEST,
    ShowPhase.MODEL_REVEAL,
    ShowPhase.ELIMINATION,
    ShowPhase.FINALE,
    ShowPhase.WINNER,
    ShowPhase.OUTRO,
    ShowPhase.ENDED,
]


async def _get_episode(episode_id: uuid.UUID, db: AsyncSession) -> Episode:
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    return episode


@router.post("/episodes/{episode_id}/next-phase")
async def next_phase(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Advance to the next show phase."""
    episode = await _get_episode(episode_id, db)
    if episode.status != EpisodeStatus.LIVE:
        raise HTTPException(400, "Episode is not live")

    current_idx = SHOW_PHASE_ORDER.index(episode.current_phase) if episode.current_phase else -1
    if current_idx >= len(SHOW_PHASE_ORDER) - 1:
        raise HTTPException(400, "Episode already ended")

    next_phase = SHOW_PHASE_ORDER[current_idx + 1]
    episode.current_phase = next_phase
    episode.version += 1

    await emit_event(db, episode_id, ShowEventType.SHOW_PHASE, "system", {
        "phase": next_phase.value,
        "previous": episode.current_phase.value if episode.current_phase else None,
    })

    return {"phase": next_phase.value, "version": episode.version}


@router.post("/episodes/{episode_id}/pause")
async def pause_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Pause the live show."""
    episode = await _get_episode(episode_id, db)
    if episode.status != EpisodeStatus.LIVE:
        raise HTTPException(400, "Episode is not live")

    await emit_event(db, episode_id, ShowEventType.SHOW_PAUSE, "admin", {})
    episode.version += 1

    return {"status": "paused", "version": episode.version}


@router.post("/episodes/{episode_id}/resume")
async def resume_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Resume a paused show."""
    episode = await _get_episode(episode_id, db)
    if episode.status != EpisodeStatus.LIVE:
        raise HTTPException(400, "Episode is not live")

    await emit_event(db, episode_id, ShowEventType.SHOW_RESUME, "admin", {})
    episode.version += 1

    return {"status": "resumed", "version": episode.version}


@router.post("/episodes/{episode_id}/skip")
async def skip_contestant(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Skip current contestant, move to next."""
    episode = await _get_episode(episode_id, db)
    if episode.status != EpisodeStatus.LIVE:
        raise HTTPException(400, "Episode is not live")

    await emit_event(db, episode_id, ShowEventType.SHOW_PHASE, "admin", {
        "phase": "skip",
        "current_phase": episode.current_phase.value if episode.current_phase else None,
    })
    episode.version += 1

    return {"status": "skipped", "version": episode.version}


@router.post("/episodes/{episode_id}/end")
async def end_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """End the live show."""
    episode = await _get_episode(episode_id, db)
    if episode.status != EpisodeStatus.LIVE:
        raise HTTPException(400, "Episode is not live")

    episode.status = EpisodeStatus.COMPLETED
    episode.current_phase = ShowPhase.ENDED
    episode.ended_at = datetime.now(timezone.utc)
    episode.version += 1

    await emit_event(db, episode_id, ShowEventType.SHOW_END, "admin", {
        "reason": "ended",
    })

    return {"status": "completed", "version": episode.version}
