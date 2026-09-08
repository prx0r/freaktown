"""Audience routes and WebSocket handlers.

POST /v1/episodes/{id}/audience/join   → join audience session (HTTP, canonical)
WS   /v1/episodes/{id}/audience        → audience WebSocket — LEGACY, DO NOT USE FOR NEW CODE

LEGACY NOTICE
-------------
The canonical LIVE runtime is the Cloudflare EpisodeRoom Durable Object
(`apps/web/worker/episode-room.ts`, served at `/live/:episodeId/ws`).
FastAPI is the control plane / generation / database / ML layer — HTTP only.

This WebSocket is retained temporarily for backward compatibility and will
be removed once the Worker path is deployed to production.

KNOWN DEFECTS (will not be fixed — migrate to EpisodeRoom instead):
- Crowd events are written to a hardcoded timestamp bucket (always zero),
  destroying ML timing data.
- The active performer is inferred from highest draw position rather than
  actual live-stage state.
- In-memory connection sets do not survive process restarts.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import async_session
from backend.models import (
    AudienceSession,
    CrowdBucket,
    Episode,
    Appearance,
    ShowEvent,
)
from backend.routes.stage import broadcast_stage, stage_connections

logger = logging.getLogger("freak_town.legacy")

router = APIRouter()


# ── Audience REST ──────────────────────────────────────────────────────

@router.post("/episodes/{episode_id}/audience/join")
async def join_audience(episode_id: uuid.UUID):
    """Create an anonymous audience session."""
    session_id = uuid.uuid4()
    async with async_session() as db:
        result = await db.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one_or_none()
        if not episode:
            return {"error": "Episode not found"}, 404

        session = AudienceSession(id=session_id, episode_id=episode_id)
        db.add(session)
        await db.commit()

    return {"session_id": str(session_id), "episode_id": str(episode_id)}


# ── Crowd aggregation in-memory store ─────────────────────────────────

# In production this would be Redis. For MVP, in-memory per episode.
crowd_store: dict[str, dict[str, dict[int, dict]]] = {}

# Active audience connections per episode
audience_connections: dict[str, set[WebSocket]] = {}


def _bucket_key(seconds: int) -> int:
    """Round to 1-second buckets."""
    return seconds


async def _broadcast_audience(episode_id: str, message: dict):
    """Send to all audience WebSockets."""
    connections = audience_connections.get(episode_id, set())
    dead = set()
    payload = json.dumps(message)
    for ws in connections:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connections -= dead


# ── Audience WebSocket ─────────────────────────────────────────────────

@router.websocket("/episodes/{episode_id}/audience")
async def audience_ws(websocket: WebSocket, episode_id: uuid.UUID):
    """
    Audience WebSocket — LEGACY.

    Canonical path: EpisodeRoom Durable Object at `/live/:episodeId/ws`.
    This handler is frozen: bug fixes go to the Worker, not here.

    Client sends:
      {"type": "laugh", "intensity": 3}
      {"type": "clap"}
      {"type": "boo"}
      {"type": "tip", "appearance_id": "...", "amount": 5.0}
      {"type": "vote", "appearance_id": "...", "vote": "yes"}

    Server sends:
      {"type": "crowd.aggregate", "data": {...}}
      {"type": "tip.received", "data": {...}}
      {"type": "timer", "data": {...}}
      {"type": "phase", "data": {...}}
    """
    logger.warning("LEGACY audience_ws connection for episode %s — migrate to EpisodeRoom", episode_id)
    await websocket.accept()
    ep_id = str(episode_id)

    # Track connection
    if ep_id not in audience_connections:
        audience_connections[ep_id] = set()
    audience_connections[ep_id].add(websocket)

    # Send current state snapshot
    async with async_session() as db:
        result = await db.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one_or_none()
        if episode:
            await websocket.send_text(json.dumps({
                "type": "snapshot",
                "data": {
                    "episode_id": ep_id,
                    "status": episode.status,
                    "phase": episode.current_phase,
                },
            }))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "laugh":
                intensity = msg.get("intensity", 1)
                now = datetime.now(timezone.utc)

                async with async_session() as db:
                    # Get current active appearance (latest draw position)
                    ap_result = await db.execute(
                        select(Appearance).where(
                            Appearance.episode_id == episode_id,
                        ).order_by(Appearance.draw_position.desc()).limit(1)
                    )
                    ap = ap_result.scalar_one_or_none()
                    if ap:
                        bucket = _bucket_key(0)
                        bucket_result = await db.execute(
                            select(CrowdBucket).where(
                                CrowdBucket.episode_id == episode_id,
                                CrowdBucket.appearance_id == ap.id,
                                CrowdBucket.bucket_start == bucket,
                            )
                        )
                        cb = bucket_result.scalar_one_or_none()
                        if cb:
                            cb.laugh_events += intensity
                            cb.unique_laughers = max(cb.unique_laughers, 1)
                        else:
                            cb = CrowdBucket(
                                episode_id=episode_id,
                                appearance_id=ap.id,
                                bucket_start=bucket,
                                laugh_events=intensity,
                                unique_laughers=1,
                                active_viewers=len(audience_connections.get(ep_id, set())),
                            )
                            db.add(cb)
                        await db.commit()

                # Broadcast aggregate to all audience
                await _broadcast_audience(ep_id, {
                    "type": "crowd.update",
                    "data": {"laugh": True, "intensity": intensity},
                })

                # Also broadcast to stage
                await broadcast_stage(ep_id, {
                    "type": "crowd.update",
                    "data": {"laugh": True, "intensity": intensity},
                })

            elif msg_type == "tip":
                tip_data = {
                    "type": "tip.received",
                    "data": {
                        "appearance_id": msg.get("appearance_id"),
                        "amount": msg.get("amount", 0),
                        "sender": msg.get("sender", "anonymous"),
                        "message": msg.get("message", ""),
                    },
                }
                await _broadcast_audience(ep_id, tip_data)
                await broadcast_stage(ep_id, tip_data)

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        audience_connections.get(ep_id, set()).discard(websocket)
