"""Stage routes — stage WebSocket for browser renderer — LEGACY.

WS /v1/ws/episodes/{id}/stage → delivers all ShowEvents — LEGACY, DO NOT USE FOR NEW CODE

LEGACY NOTICE
-------------
The canonical LIVE runtime is the Cloudflare EpisodeRoom Durable Object
(`apps/web/worker/episode-room.ts`, served at `/live/:episodeId/ws`).
FastAPI is the control plane / generation / database / ML layer — HTTP only.

This WebSocket is retained temporarily for backward compatibility and will
be removed once the Worker path is deployed to production.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.db import async_session
from backend.models import Episode, Appearance, ShowEvent

logger = logging.getLogger("freak_town.legacy")

router = APIRouter()

# Active stage connections per episode (shared with audience module)
stage_connections: dict[str, set[WebSocket]] = {}


async def broadcast_stage(episode_id: str, message: dict):
    """Send to all stage WebSockets. Called from audience module for crowd events."""
    connections = stage_connections.get(episode_id, set())
    dead = set()
    payload = json.dumps(message)
    for ws in connections:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connections -= dead


@router.websocket("/episodes/{episode_id}/stage")
async def stage_ws(websocket: WebSocket, episode_id: uuid.UUID):
    """
    Stage WebSocket — LEGACY.

    Canonical path: EpisodeRoom Durable Object at `/live/:episodeId/ws`.
    This handler is frozen: bug fixes go to the Worker, not here.

    Client sends:
      {"type": "ready", "last_seq": 0}
      {"type": "ack", "event_id": "..."}
      {"type": "heartbeat"}

    Server sends:
      {"type": "show.snapshot", "data": {...}}
      All canonical ShowEvents in order
    """
    logger.warning("LEGACY stage_ws connection for episode %s — migrate to EpisodeRoom", episode_id)
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
                last_seq = msg.get("last_seq", 0)

                async with async_session() as db:
                    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
                    episode = ep_result.scalar_one_or_none()

                    events_result = await db.execute(
                        select(ShowEvent).where(
                            ShowEvent.episode_id == episode_id,
                            ShowEvent.seq > last_seq,
                        ).order_by(ShowEvent.seq)
                    )
                    events = events_result.scalars().all()

                    ec_result = await db.execute(
                        select(Appearance).where(Appearance.episode_id == episode_id)
                        .order_by(Appearance.draw_position)
                    )
                    contestants = ec_result.scalars().all()

                    snapshot = {
                        "type": "show.snapshot",
                        "data": {
                            "episode_id": ep_id,
                            "status": episode.status if episode else "unknown",
                            "phase": episode.current_phase if episode else None,
                            "contestants": [
                                {
                                    "id": str(c.id),
                                    "draw_position": c.draw_position,
                                }
                                for c in contestants
                            ],
                            "events": [
                                {
                                    "seq": e.seq,
                                    "type": e.type,
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
