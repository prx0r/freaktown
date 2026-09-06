"""Audience routes and WebSocket handlers.

POST /v1/episodes/{id}/audience/join   → join audience session
WS   /v1/ws/episodes/{id}/audience     → audience WebSocket (laugh, chat, tips)
WS   /v1/ws/episodes/{id}/stage        → stage WebSocket (show events)
"""

import json
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
    EpisodeContestant,
    EpisodeStatus,
    ShowEvent,
)

router = APIRouter()


# ── Audience REST ──────────────────────────────────────────────────────

@router.post("/episodes/{episode_id}/audience/join")
async def join_audience(episode_id: uuid.UUID):
    """Create an anonymous audience session."""
    session_id = uuid.uuid4()
    async with async_session() as db:
        # Verify episode exists
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
# key = episode_id, value = { contestant_id: { bucket_start: { ... } } }
crowd_store: dict[str, dict[str, dict[int, dict]]] = {}

# Active audience connections per episode
audience_connections: dict[str, set[WebSocket]] = {}

# Active stage connections per episode
stage_connections: dict[str, set[WebSocket]] = {}


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


async def _broadcast_stage(episode_id: str, message: dict):
    """Send to all stage WebSockets."""
    connections = stage_connections.get(episode_id, set())
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
    Audience WebSocket.

    Client sends:
      {"type": "laugh", "intensity": 3}
      {"type": "clap"}
      {"type": "boo"}
      {"type": "tip", "contestant_id": "...", "amount": 5.0}
      {"type": "vote", "contestant_id": "...", "vote": "yes"}

    Server sends:
      {"type": "crowd.aggregate", "data": {...}}
      {"type": "tip.received", "data": {...}}
      {"type": "timer", "data": {...}}
      {"type": "phase", "data": {...}}
    """
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
                    "status": episode.status.value,
                    "phase": episode.current_phase.value if episode.current_phase else None,
                },
            }))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "laugh":
                # Record laugh event
                intensity = msg.get("intensity", 1)
                now = datetime.now(timezone.utc)

                async with async_session() as db:
                    # Get current contestant
                    ec_result = await db.execute(
                        select(EpisodeContestant).where(
                            EpisodeContestant.episode_id == episode_id,
                            EpisodeContestant.linkage_status == "performed",
                        ).order_by(EpisodeContestant.draw_position.desc()).limit(1)
                    )
                    ec = ec_result.scalar_one_or_none()
                    if ec:
                        bucket = _bucket_key(0)  # simplified — would use performance elapsed time
                        bucket_result = await db.execute(
                            select(CrowdBucket).where(
                                CrowdBucket.episode_id == episode_id,
                                CrowdBucket.contestant_id == ec.id,
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
                                contestant_id=ec.id,
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
                await _broadcast_stage(ep_id, {
                    "type": "crowd.update",
                    "data": {"laugh": True, "intensity": intensity},
                })

            elif msg_type == "tip":
                # Broadcast tip to everyone
                tip_data = {
                    "type": "tip.received",
                    "data": {
                        "contestant_id": msg.get("contestant_id"),
                        "amount": msg.get("amount", 0),
                        "sender": msg.get("sender", "anonymous"),
                        "message": msg.get("message", ""),
                    },
                }
                await _broadcast_audience(ep_id, tip_data)
                await _broadcast_stage(ep_id, tip_data)

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        audience_connections.get(ep_id, set()).discard(websocket)


# ── Stage WebSocket ────────────────────────────────────────────────────

@router.websocket("/episodes/{episode_id}/stage")
async def stage_ws(websocket: WebSocket, episode_id: uuid.UUID):
    """
    Stage WebSocket — delivers all ShowEvents to the browser renderer.

    Client sends:
      {"type": "ready", "last_seq": 0}
      {"type": "ack", "event_id": "..."}
      {"type": "heartbeat"}

    Server sends:
      {"type": "show.snapshot", "data": {...}}
      All canonical ShowEvents in order
    """
    await websocket.accept()
    ep_id = str(episode_id)

    if ep_id not in stage_connections:
        stage_connections[ep_id] = set()
    stage_connections[ep_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "ready":
                # Client is ready — send full snapshot
                last_seq = msg.get("last_seq", 0)

                async with async_session() as db:
                    # Episode state
                    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
                    episode = ep_result.scalar_one_or_none()

                    # All events since last_seq
                    events_result = await db.execute(
                        select(ShowEvent).where(
                            ShowEvent.episode_id == episode_id,
                            ShowEvent.seq > last_seq,
                        ).order_by(ShowEvent.seq)
                    )
                    events = events_result.scalars().all()

                    # Current contestants
                    ec_result = await db.execute(
                        select(EpisodeContestant).where(EpisodeContestant.episode_id == episode_id)
                        .order_by(EpisodeContestant.draw_position)
                    )
                    contestants = ec_result.scalars().all()

                    snapshot = {
                        "type": "show.snapshot",
                        "data": {
                            "episode_id": ep_id,
                            "status": episode.status.value if episode else "unknown",
                            "phase": episode.current_phase.value if episode and episode.current_phase else None,
                            "contestants": [
                                {
                                    "id": str(c.id),
                                    "draw_position": c.draw_position,
                                    "is_resident": c.is_resident,
                                }
                                for c in contestants
                            ],
                            "events": [
                                {
                                    "seq": e.seq,
                                    "type": e.type.value,
                                    "actor": e.actor,
                                    "payload": e.payload,
                                    "effective_at": str(e.effective_at) if e.effective_at else None,
                                }
                                for e in events
                            ],
                        },
                    }
                    await websocket.send_text(json.dumps(snapshot))

            elif msg_type == "heartbeat":
                await websocket.send_text(json.dumps({"type": "heartbeat.ack"}))

    except WebSocketDisconnect:
        stage_connections.get(ep_id, set()).discard(websocket)
