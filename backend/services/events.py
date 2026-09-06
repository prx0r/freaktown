"""Event sequencing helpers — ensures no duplicate or hardcoded seq values."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ShowEvent


async def get_next_seq(db: AsyncSession, episode_id: uuid.UUID) -> int:
    """Get the next sequence number for an episode's events.

    Uses SELECT MAX(seq) + 1 to guarantee no duplicates.
    Never hardcode seq values.
    """
    result = await db.execute(
        select(func.coalesce(func.max(ShowEvent.seq), 0)).where(ShowEvent.episode_id == episode_id)
    )
    return result.scalar() + 1


async def emit_event(
    db: AsyncSession,
    episode_id: uuid.UUID,
    event_type,
    actor: str,
    payload: dict,
    effective_at=None,
) -> ShowEvent:
    """Emit a show event with auto-assigned sequence number.

    Never call with a hardcoded seq. Always use this helper.
    """
    seq = await get_next_seq(db, episode_id)
    event = ShowEvent(
        episode_id=episode_id,
        seq=seq,
        type=event_type,
        actor=actor,
        payload=payload,
        effective_at=effective_at,
    )
    db.add(event)
    return event
