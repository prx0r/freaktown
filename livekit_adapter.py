#!/usr/bin/env python3
"""LiveKit media plane: everybody who's present, nothing else.

The event runtime (party rooms, formats, receipts) stays authoritative
for state. LiveKit carries voice/video/data + participant lifecycle.
No server configured → every call degrades to a clear answer, never
an exception. The game never imports this; seats resolve here.

Roles: human (mic+camera+data), agent (mic+data, programmatic),
phone (mic only — SIP trunk attaches server-side later).
"""

import os

ROLE_GRANTS = {
    # publish sources per role (None = cannot publish at all)
    "human": ["MICROPHONE", "CAMERA"],
    "agent": ["MICROPHONE"],
    "phone": ["MICROPHONE"],
    "spectator": [],
}


def configured() -> bool:
    return bool(os.getenv("LIVEKIT_URL") and os.getenv("LIVEKIT_API_KEY")
                and os.getenv("LIVEKIT_API_SECRET"))


def room_name(event_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-"
                   for c in str(event_id or "lobby"))[:48].strip("-") or "lobby"
    return f"freaktown-{safe}"


def mint_token(identity: str, room: str, role: str = "human",
               ttl_seconds: int = 3600) -> dict:
    """Local JWT mint (no server round-trip). Raises RuntimeError unconfigured."""
    if not configured():
        raise RuntimeError("livekit not configured (LIVEKIT_URL/KEY/SECRET)")
    if role not in ROLE_GRANTS:
        raise ValueError(f"unknown role: {role}")
    from datetime import timedelta
    from livekit import api
    sources = ROLE_GRANTS[role]
    token = (api.AccessToken(os.getenv("LIVEKIT_API_KEY"),
                             os.getenv("LIVEKIT_API_SECRET"))
             .with_identity(str(identity)[:64])
             .with_name(str(identity)[:64])
             .with_grants(api.VideoGrants(
                 room_join=True, room=room,
                 can_publish=bool(sources),
                 can_publish_sources=sources or None,
                 can_publish_data=True,
                 can_subscribe=True))
             .with_ttl(timedelta(seconds=ttl_seconds)))
    return {"token": token.to_jwt(), "url": os.getenv("LIVEKIT_URL"),
            "room": room, "identity": identity, "role": role}


async def ensure_room(room: str) -> dict:
    """Create the room server-side if missing. Needs a live server."""
    if not configured():
        return {"ok": False, "error": "livekit not configured"}
    from livekit import api
    try:
        async with api.LiveKitAPI(
                os.getenv("LIVEKIT_URL"), os.getenv("LIVEKIT_API_KEY"),
                os.getenv("LIVEKIT_API_SECRET")) as lk:
            await lk.room.create_room(api.CreateRoomRequest(name=room))
        return {"ok": True, "room": room, "created": True}
    except Exception as e:
        if "already exists" in str(e).lower():
            return {"ok": True, "room": room, "created": False}
        return {"ok": False, "error": str(e)[:160]}


def agent_dispatch(room: str, agent_name: str, identity: str = "") -> dict:
    """Metadata for dispatching a programmatic participant later.
    No-op descriptor until an agent worker exists — never called by games."""
    return {"room": room, "agent": agent_name,
            "identity": identity or f"agent-{agent_name}", "dispatched": False,
            "note": "dispatch when agent worker exists"}
