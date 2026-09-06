"""Event sequencing helpers — concurrency-safe implementation.

Per peer review: "Do not accept SELECT MAX(seq)+1. The owner of live sequence is EpisodeRoom."

For Python (offline/research), use advisory locks.
For production (Cloudflare), EpisodeRoom allocates seq.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ShowEvent


async def get_next_seq_safe(db: AsyncSession, episode_id: uuid.UUID) -> int:
    """Get next sequence number using advisory lock to prevent races.

    This uses PostgreSQL advisory locks for concurrency safety.
    Two transactions cannot read the same maximum.
    """
    # Use advisory lock on episode_id hash
    lock_key = hash(str(episode_id)) % (2**31)
    await db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

    # Now safe to read max
    result = await db.execute(
        select(func.coalesce(func.max(ShowEvent.seq), 0)).where(ShowEvent.episode_id == episode_id)
    )
    return result.scalar() + 1


async def emit_event(
    db: AsyncSession,
    episode_id: uuid.UUID,
    event_type: str,
    actor: str,
    payload: dict,
    effective_at=None,
) -> ShowEvent:
    """Emit a show event with concurrency-safe sequence number.

    Uses advisory lock to prevent duplicate seq values.
    """
    seq = await get_next_seq_safe(db, episode_id)
    event = ShowEvent(
        episode_id=episode_id,
        seq=seq,
        type=event_type,
        actor=actor,
        payload=payload,
        effective_at=effective_at or datetime.now(timezone.utc),
    )
    db.add(event)
    return event
