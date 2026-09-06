"""MCP-compatible API endpoints for external agents.

Allows programmatic access to:
  - Create comedians
  - Create act versions
  - Submit to episodes
  - Query episode status
  - Get show events

All endpoints accept X-API-Key header for authentication.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_from_api_key, require_admin_from_api_key
from backend.db import get_db
from backend.models import (
    ActVersion,
    Authorship,
    BodyArchetype,
    Comedian,
    ComedianStatus,
    Episode,
    EpisodeStatus,
    InterviewController,
    ShowEvent,
    ShowEventType,
    ShowPhase,
    Submission,
    SubmissionStatus,
    User,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class MCPComedianCreate(BaseModel):
    """Create a comedian via MCP."""
    name: str = Field(..., min_length=1, max_length=120)
    body_archetype: BodyArchetype
    premise: str = Field(..., min_length=1, max_length=500)
    character_deal: str = Field(..., min_length=1, max_length=1000)
    minute_text: str = Field(..., min_length=1, max_length=2000)
    voice_profile: str = Field(default="default")
    minute_authorship: Authorship = Authorship.AI
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list)


class MCPActVersionCreate(BaseModel):
    """Create a new act version via MCP."""
    comedian_id: uuid.UUID
    character_deal: str = Field(..., min_length=1, max_length=1000)
    minute_text: str = Field(..., min_length=1, max_length=2000)
    voice_profile: str = Field(default="default")
    minute_authorship: Authorship = Authorship.AI
    interview_controller: InterviewController = InterviewController.FREAK_TOWN_AI
    character_facts: list[str] = Field(default_factory=list)


class MCPSubmissionCreate(BaseModel):
    """Submit to an episode via MCP."""
    episode_id: uuid.UUID
    comedian_id: uuid.UUID
    act_version_id: uuid.UUID | None = None  # uses latest if None


class MCPToolCall(BaseModel):
    """MCP tool call request."""
    tool: str
    arguments: dict


class MCPToolResult(BaseModel):
    """MCP tool call result."""
    content: list[dict]
    isError: bool = False


# ── Tool Registry ──────────────────────────────────────────────────────

MCP_TOOLS = {
    "create_comedian": {
        "description": "Create a new comedian character for Freak Town",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Character name"},
                "body_archetype": {"type": "string", "enum": ["human", "dog", "robot", "creature", "object", "monster", "animal", "mystery"]},
                "premise": {"type": "string", "description": "One sentence: who/what are they?"},
                "character_deal": {"type": "string", "description": "What's their deal?"},
                "minute_text": {"type": "string", "description": "Their 60-second minute"},
                "voice_profile": {"type": "string", "description": "Voice key from catalog"},
            },
            "required": ["name", "body_archetype", "premise", "character_deal", "minute_text"],
        },
    },
    "create_act_version": {
        "description": "Create a new immutable act version for an existing comedian",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comedian_id": {"type": "string", "format": "uuid"},
                "character_deal": {"type": "string"},
                "minute_text": {"type": "string"},
                "voice_profile": {"type": "string"},
            },
            "required": ["comedian_id", "character_deal", "minute_text"],
        },
    },
    "submit_to_episode": {
        "description": "Submit a comedian to an episode's lineup",
        "inputSchema": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "string", "format": "uuid"},
                "comedian_id": {"type": "string", "format": "uuid"},
                "act_version_id": {"type": "string", "format": "uuid"},
            },
            "required": ["episode_id", "comedian_id"],
        },
    },
    "list_episodes": {
        "description": "List available episodes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["draft", "open", "locked", "live", "completed"]},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    "get_episode": {
        "description": "Get episode details including submissions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "string", "format": "uuid"},
            },
            "required": ["episode_id"],
        },
    },
    "get_comedian": {
        "description": "Get comedian details including act versions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comedian_id": {"type": "string", "format": "uuid"},
            },
            "required": ["comedian_id"],
        },
    },
    "list_comedians": {
        "description": "List comedians in the pool",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "retired", "all"], "default": "active"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    "get_show_events": {
        "description": "Get show events for an episode",
        "inputSchema": {
            "type": "object",
            "properties": {
                "episode_id": {"type": "string", "format": "uuid"},
                "since_seq": {"type": "integer", "default": 0},
            },
            "required": ["episode_id"],
        },
    },
}


# ── MCP Discovery Endpoints ────────────────────────────────────────────

@router.get("/mcp/tools")
async def list_mcp_tools(user: User = Depends(get_current_user_from_api_key)):
    """List available MCP tools."""
    return {"tools": MCP_TOOLS}


@router.post("/mcp/tools/{tool_name}")
async def call_mcp_tool(
    tool_name: str,
    request: Request,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Execute an MCP tool call."""
    body = await request.json()
    args = body.get("arguments", {})

    if tool_name not in MCP_TOOLS:
        raise HTTPException(404, f"Unknown tool: {tool_name}")

    try:
        if tool_name == "create_comedian":
            return await _create_comedian(user, args, db)
        elif tool_name == "create_act_version":
            return await _create_act_version(user, args, db)
        elif tool_name == "submit_to_episode":
            return await _submit_to_episode(user, args, db)
        elif tool_name == "list_episodes":
            return await _list_episodes(args, db)
        elif tool_name == "get_episode":
            return await _get_episode(args, db)
        elif tool_name == "get_comedian":
            return await _get_comedian(args, db)
        elif tool_name == "list_comedians":
            return await _list_comedians(args, db)
        elif tool_name == "get_show_events":
            return await _get_show_events(args, db)
    except Exception as e:
        return MCPToolResult(
            content=[{"type": "text", "text": f"Error: {str(e)}"}],
            isError=True,
        )


# ── Tool Implementations ───────────────────────────────────────────────

async def _create_comedian(user: User, args: dict, db: AsyncSession) -> dict:
    """Create a comedian via MCP."""
    from backend.routes.comedians import slugify, compute_hash

    name = args["name"]
    slug = slugify(name)

    # Check uniqueness
    existing = await db.execute(select(Comedian).where(Comedian.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Comedian '{name}' already exists")

    existing_slug = await db.execute(select(Comedian).where(Comedian.slug == slug))
    if existing_slug.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    # Create comedian
    comedian = Comedian(
        name=name,
        slug=slug,
        body_archetype=args["body_archetype"],
        premise=args["premise"],
        owner_user_id=user.id,
    )
    db.add(comedian)
    await db.flush()

    # Create first act version
    content_hash = hashlib.sha256(json.dumps({
        "comedian_id": str(comedian.id),
        "revision": 1,
        "minute_text": args["minute_text"],
        "character_deal": args["character_deal"],
    }, sort_keys=True).encode()).hexdigest()

    manifest = {
        "schemaVersion": 1,
        "character": {
            "name": name,
            "deal": args["character_deal"],
            "facts": args.get("character_facts", []),
        },
        "body": {
            "family": args["body_archetype"],
            "variant": None,
            "outfit": None,
        },
        "voice": {
            "voiceId": args.get("voice_profile", "default"),
        },
        "minute": {
            "text": args["minute_text"],
            "authorship": args.get("minute_authorship", "ai"),
            "assistance": [],
        },
        "interview": {
            "controller": args.get("interview_controller", "freak_town_ai"),
            "facts": args.get("character_facts", []),
        },
    }

    act = ActVersion(
        comedian_id=comedian.id,
        revision=1,
        created_by_user_id=user.id,
        manifest=manifest,
        content_sha256=content_hash,
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(act)
    await db.flush()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "comedian_id": str(comedian.id),
                "act_version_id": str(act.id),
                "name": name,
                "slug": slug,
                "status": "created",
            }),
        }],
    }


async def _create_act_version(user: User, args: dict, db: AsyncSession) -> dict:
    """Create a new act version via MCP."""
    comedian_id = args["comedian_id"]

    # Verify ownership
    result = await db.execute(select(Comedian).where(Comedian.id == comedian_id))
    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")
    if comedian.owner_user_id != user.id:
        raise HTTPException(403, "Not your comedian")

    # Find latest revision
    versions_result = await db.execute(
        select(ActVersion)
        .where(ActVersion.comedian_id == comedian_id)
        .order_by(ActVersion.revision.desc())
        .limit(1)
    )
    latest = versions_result.scalar_one_or_none()
    next_revision = (latest.revision + 1) if latest else 1
    parent_id = latest.id if latest else None

    content_hash = hashlib.sha256(json.dumps({
        "comedian_id": str(comedian_id),
        "revision": next_revision,
        "minute_text": args["minute_text"],
        "character_deal": args["character_deal"],
    }, sort_keys=True).encode()).hexdigest()

    manifest = {
        "schemaVersion": 1,
        "character": {
            "name": comedian.name,
            "deal": args["character_deal"],
            "facts": args.get("character_facts", []),
        },
        "body": {
            "family": comedian.body_archetype.value,
            "variant": None,
            "outfit": None,
        },
        "voice": {
            "voiceId": args.get("voice_profile", "default"),
        },
        "minute": {
            "text": args["minute_text"],
            "authorship": args.get("minute_authorship", "ai"),
            "assistance": [],
        },
        "interview": {
            "controller": args.get("interview_controller", "freak_town_ai"),
            "facts": args.get("character_facts", []),
        },
    }

    act = ActVersion(
        comedian_id=comedian_id,
        revision=next_revision,
        parent_act_version_id=parent_id,
        created_by_user_id=user.id,
        manifest=manifest,
        content_sha256=content_hash,
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(act)
    await db.flush()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "act_version_id": str(act.id),
                "revision": next_revision,
                "status": "created",
            }),
        }],
    }


async def _submit_to_episode(user: User, args: dict, db: AsyncSession) -> dict:
    """Submit a comedian to an episode via MCP."""
    episode_id = args["episode_id"]
    comedian_id = args["comedian_id"]

    # Check episode is open
    ep_result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}, not open")

    # Check comedian ownership
    com_result = await db.execute(select(Comedian).where(Comedian.id == comedian_id))
    comedian = com_result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")
    if comedian.owner_user_id != user.id:
        raise HTTPException(403, "Not your comedian")

    # Get act version (latest if not specified)
    act_version_id = args.get("act_version_id")
    if act_version_id:
        av_result = await db.execute(
            select(ActVersion).where(ActVersion.id == act_version_id)
        )
    else:
        av_result = await db.execute(
            select(ActVersion)
            .where(ActVersion.comedian_id == comedian_id)
            .order_by(ActVersion.revision.desc())
            .limit(1)
        )
    act_version = av_result.scalar_one_or_none()
    if not act_version:
        raise HTTPException(404, "Act version not found")

    # Check not already submitted
    existing = await db.execute(
        select(Submission).where(
            Submission.episode_id == episode_id,
            Submission.comedian_id == comedian_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already submitted to this episode")

    submission = Submission(
        episode_id=episode_id,
        comedian_id=comedian_id,
        act_version_id=act_version.id,
        submitted_by_user_id=user.id,
        qualification_status=SubmissionStatus.SUBMITTED,
    )
    db.add(submission)
    await db.flush()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "submission_id": str(submission.id),
                "status": "submitted",
                "episode_id": str(episode_id),
                "comedian_name": comedian.name,
            }),
        }],
    }


async def _list_episodes(args: dict, db: AsyncSession) -> dict:
    """List episodes."""
    query = select(Episode).order_by(Episode.created_at.desc())
    status = args.get("status")
    if status:
        query = query.where(Episode.status == status)
    query = query.limit(args.get("limit", 10))

    result = await db.execute(query)
    episodes = result.scalars().all()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps([{
                "id": str(ep.id),
                "title": ep.title,
                "status": ep.status.value,
                "phase": ep.current_phase.value if ep.current_phase else None,
                "created_at": str(ep.created_at),
            } for ep in episodes]),
        }],
    }


async def _get_episode(args: dict, db: AsyncSession) -> dict:
    """Get episode details."""
    result = await db.execute(select(Episode).where(Episode.id == args["episode_id"]))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")

    # Count submissions
    sub_count = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.episode_id == episode.id)
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "id": str(episode.id),
                "title": episode.title,
                "status": episode.status.value,
                "phase": episode.current_phase.value if episode.current_phase else None,
                "max_appearances": episode.max_appearances,
                "submission_count": sub_count.scalar(),
                "scheduled_at": str(episode.scheduled_at) if episode.scheduled_at else None,
            }),
        }],
    }


async def _get_comedian(args: dict, db: AsyncSession) -> dict:
    """Get comedian details."""
    result = await db.execute(select(Comedian).where(Comedian.id == args["comedian_id"]))
    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Comedian not found")

    # Get versions
    versions_result = await db.execute(
        select(ActVersion)
        .where(ActVersion.comedian_id == comedian.id)
        .order_by(ActVersion.revision.desc())
    )
    versions = versions_result.scalars().all()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "id": str(comedian.id),
                "name": comedian.name,
                "slug": comedian.slug,
                "premise": comedian.premise,
                "body_archetype": comedian.body_archetype.value,
                "status": comedian.status.value,
                "versions": [{
                    "id": str(v.id),
                    "revision": v.revision,
                    "created_at": str(v.created_at),
                } for v in versions],
            }),
        }],
    }


async def _list_comedians(args: dict, db: AsyncSession) -> dict:
    """List comedians."""
    query = select(Comedian).order_by(Comedian.created_at.desc())
    status = args.get("status", "active")
    if status != "all":
        query = query.where(Comedian.status == status)
    query = query.limit(args.get("limit", 50))

    result = await db.execute(query)
    comedians = result.scalars().all()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps([{
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "premise": c.premise,
                "body_archetype": c.body_archetype.value,
            } for c in comedians]),
        }],
    }


async def _get_show_events(args: dict, db: AsyncSession) -> dict:
    """Get show events for an episode."""
    query = select(ShowEvent).where(ShowEvent.episode_id == args["episode_id"])
    since_seq = args.get("since_seq", 0)
    if since_seq > 0:
        query = query.where(ShowEvent.seq > since_seq)
    query = query.order_by(ShowEvent.seq).limit(100)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps([{
                "seq": e.seq,
                "type": e.type.value,
                "actor": e.actor,
                "payload": e.payload,
                "effective_at": str(e.effective_at) if e.effective_at else None,
            } for e in events]),
        }],
    }
