"""Intake API — Black Room sets enter the show here.

Freaktown's editor ends at SUBMIT (local status flip to `queued`).
This is the backend that makes SUBMIT real:

  Black Room bundle (character + delivery + set.wav + meta)
        ↓ POST /v1/intake/bundle
  validate → find-or-create comedian → seal ActVersion → Submission
  → store audio → sealed freaktown.performance.v1 manifest

The bundle slug rule matches freaktown's app.py (name + content hash),
so re-submitting the same set is idempotent-ish (409 already submitted).
Audio arrives as base64 (cap 10MB decoded) or as a URL the stage fetches.
"""

import base64
import binascii
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_from_api_key
from backend.db import get_db
from backend.models import (
    ActVersion,
    Appearance,
    BodyArchetype,
    Comedian,
    Episode,
    EpisodeStatus,
    Submission,
    User,
)
from backend.routes.comedians import compute_hash
from backend.services.events import emit_event
from backend.services.freaktown import (
    bundle_slug,
    bundle_to_score,
    build_performance_manifest,
    estimate_spans,
    species_to_body,
    spans_from_offsets,
    validate_avatar,
    validate_bundle,
    validate_modes,
    words_from_beats,
)
from backend.services.media_store import media_store

router = APIRouter()

MAX_AUDIO_BYTES = 10_000_000  # 10MB decoded cap on inline audio
MAX_AVATAR_BYTES = 30_000_000  # 30MB cap on inline .vrm


class CharacterIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    species: str = Field("", max_length=60)
    premise: str = Field("", max_length=500)
    vibe: str = Field("", max_length=40)
    voice: str = Field("en-US-AriaNeural", max_length=80)
    modes: dict = Field(default_factory=dict, description="performer/judge mode blocks")


class IntakeRequest(BaseModel):
    character: CharacterIn
    delivery: dict
    episode_id: uuid.UUID
    audio_base64: str = Field("", description="set.wav bytes, base64 (cap 10MB decoded)")
    audio_url: str = Field("", description="stage-fetchable URL, alternative to base64")
    audio_format: str = Field("wav", description="wav|mp3")
    avatar_url: str = Field("", max_length=500, description="avatar GLB/VRM URL (three.ws body); default stage avatar when empty")
    avatar_base64: str = Field("", description="avatar.vrm bytes, base64 (cap 30MB decoded)")
    avatar_json: dict = Field(default_factory=dict, description="freaktown.avatar.v1 capabilities")
    walkout_base64: str = Field("", description="walkout.wav bytes, base64 (cap 10MB decoded)")
    walkout_recipe: dict = Field(default_factory=dict, description="walkout recipe {genre,mood,energy,shape,seed}")
    offsets: list[dict] = Field(default_factory=list, description="compose offsets for word timings")
    duration_ms: int = Field(0, ge=0, description="0 = estimate from beats")
    style: str = Field("", max_length=40)


def _decode_b64(data: str, field_name: str, cap: int) -> bytes:
    try:
        raw = base64.b64decode(data)
    except (binascii.Error, ValueError):
        raise HTTPException(400, f"{field_name} is not valid base64")
    if len(raw) > cap:
        raise HTTPException(413, f"{field_name} exceeds cap")
    return raw


def _body_archetype(species: str) -> BodyArchetype:
    try:
        return BodyArchetype(species_to_body(species))
    except ValueError:
        return BodyArchetype.MYSTERY


@router.post("/intake/bundle", status_code=201)
async def intake_bundle(
    req: IntakeRequest,
    user: User = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Intake a Black Room bundle into the show pipeline."""
    bundle = {
        "character": req.character.model_dump(),
        "delivery": req.delivery,
        "audio_base64": req.audio_base64,
        "audio_url": req.audio_url,
    }
    v = validate_bundle(bundle)
    if not v.ok:
        raise HTTPException(400, f"invalid bundle: {v.errors[0]}")
    mv = validate_modes(req.character.modes or None)
    if not mv.ok:
        raise HTTPException(400, f"invalid modes: {mv.errors[0]}")

    # Episode must be open for submissions.
    ep_result = await db.execute(select(Episode).where(Episode.id == req.episode_id))
    episode = ep_result.scalar_one_or_none()
    if not episode:
        raise HTTPException(404, "Episode not found")
    if episode.status != EpisodeStatus.OPEN:
        raise HTTPException(400, f"Episode is {episode.status.value}, not open")

    score = bundle_to_score(req.delivery)
    minute_text = " ".join(b.text for b in score.beats)

    # Find-or-create comedian by content-hash slug (matches freaktown).
    slug = bundle_slug(req.character.name, minute_text + req.character.voice)
    com_result = await db.execute(select(Comedian).where(Comedian.slug == slug))
    comedian = com_result.scalar_one_or_none()
    if comedian and comedian.owner_user_id != user.id:
        raise HTTPException(409, "Identical set already submitted by another creator")
    if not comedian:
        comedian = Comedian(
            owner_user_id=user.id,
            name=req.character.name[:120],
            slug=slug,
            premise=(req.character.premise or req.character.species or "Guest freak")[:500],
            body_archetype=_body_archetype(req.character.species),
        )
        db.add(comedian)
        await db.flush()

    # Submission (one per comedian per episode) — checked BEFORE sealing
    # an ActVersion so re-submitting the same set is a clean 409, never
    # a unique-violation 500 on (comedian_id, revision).
    existing = await db.execute(
        select(Submission).where(
            Submission.episode_id == req.episode_id,
            Submission.comedian_id == comedian.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already submitted to this episode")

    # Seal an ActVersion carrying the full Black Room beat data.
    body_family = getattr(comedian.body_archetype, "value", comedian.body_archetype)
    manifest = {
        "schemaVersion": 1,
        "character": {
            "name": comedian.name,
            "deal": comedian.premise,
            "facts": [],
            "species": req.character.species,
            "vibe": req.character.vibe,
        },
        "body": {"family": body_family, "variant": None, "outfit": None},
        "voice": {"voiceId": req.character.voice, "provider": req.delivery.get("voice", {}).get("provider", "edge-tts")},
        "minute": {"text": minute_text, "authorship": "human", "assistance": []},
        "interview": {"controller": "freak_town_ai", "facts": []},
        "modes": req.character.modes or {},
        "black_room": {
            "beats": score.to_dict()["beats"],
            "style": req.style,
            "audio_format": req.audio_format,
        },
    }
    act = ActVersion(
        comedian_id=comedian.id,
        revision=1,
        created_by_user_id=user.id,
        manifest=manifest,
        content_sha256=compute_hash(manifest),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(act)
    await db.flush()

    submission = Submission(
        episode_id=req.episode_id,
        comedian_id=comedian.id,
        act_version_id=act.id,
        submitted_by_user_id=user.id,
    )
    db.add(submission)
    await db.flush()

    # Audio: inline base64 (stored under a fixed servable key) or URL.
    audio_ref = req.audio_url
    audio_bytes_len = 0
    audio_bytes: bytes | None = None
    if req.audio_base64:
        audio_bytes = _decode_b64(req.audio_base64, "audio_base64", MAX_AUDIO_BYTES)
        audio_bytes_len = len(audio_bytes)
        if media_store.configured:
            fmt = req.audio_format if req.audio_format in ("wav", "mp3", "ogg") else "wav"
            try:
                info = media_store.put_set_audio(str(act.id), audio_bytes, format=fmt)
                audio_ref = info.get("r2_key", "")
            except Exception:
                audio_ref = ""
        else:
            audio_ref = f"intake:{act.id}"

    # Avatar: inline .vrm (stored) or URL. Capabilities validated; the
    # runtime asks the contract what the avatar can do, never assumes.
    avatar_ref = req.avatar_url
    avatar_doc: dict = dict(req.avatar_json) if req.avatar_json else {}
    if req.avatar_base64:
        avatar_bytes = _decode_b64(req.avatar_base64, "avatar_base64", MAX_AVATAR_BYTES)
        if media_store.configured:
            try:
                info = media_store.put_bytes(f"acts/{act.id}/avatar.vrm", avatar_bytes,
                                             "model/gltf-binary")
                avatar_ref = info.get("r2_key", "")
            except Exception:
                avatar_ref = ""
        else:
            avatar_ref = f"intake:{act.id}:avatar"
    if avatar_doc:
        avatar_doc = {**avatar_doc, "asset": avatar_ref or avatar_doc.get("asset", "")}
        av = validate_avatar(avatar_doc)
        if not av.ok:
            raise HTTPException(400, f"invalid avatar: {av.errors[0]}")
    elif avatar_ref:
        avatar_doc = {"version": "freaktown.avatar.v1", "format": "vrm", "asset": avatar_ref}

    # Walkout: inline wav (stored) or synthesized later from the recipe.
    walkout_ref = ""
    walkout_ms = 0
    if req.walkout_base64:
        walkout_bytes = _decode_b64(req.walkout_base64, "walkout_base64", MAX_AUDIO_BYTES)
        if media_store.configured:
            try:
                info = media_store.put_bytes(f"acts/{act.id}/walkout.wav", walkout_bytes,
                                             "audio/wav")
                walkout_ref = info.get("r2_key", "")
            except Exception:
                walkout_ref = ""
        else:
            walkout_ref = f"intake:{act.id}:walkout"
        walkout_ms = 8000  # Black Room walkouts are exact 8s

    # Words: compose offsets when provided, else proportional estimate.
    beats = req.delivery.get("beats", [])
    spans = spans_from_offsets(req.offsets) if req.offsets else []
    if not spans:
        total_ms = req.duration_ms or None
        spans = estimate_spans(beats, total_ms)
    words = words_from_beats(beats, spans)
    set_end_ms = spans[-1].end_ms if spans else 0
    duration_ms = req.duration_ms or set_end_ms

    manifest_out = build_performance_manifest(
        performance_id=str(act.id),
        character={**req.character.model_dump(), "avatar_url": avatar_ref or req.avatar_url},
        score=score,
        words=words,
        audio_ref=audio_ref,
        duration_ms=duration_ms,
        episode_id=str(req.episode_id),
        avatar=avatar_doc or None,
        walkout_ref=walkout_ref,
        walkout_duration_ms=walkout_ms,
    )

    # Persist the sealed manifest + words for the stage to load.
    if media_store.configured:
        try:
            media_store.put_manifest(
                str(act.id), json.dumps(manifest_out).encode())
        except Exception:
            pass

    await emit_event(db, req.episode_id, "intake.received", f"creator:{user.id}", {
        "comedian_id": str(comedian.id),
        "act_version_id": str(act.id),
        "submission_id": str(submission.id),
        "slug": slug,
        "beats": len(score.beats),
        "audio_bytes": audio_bytes_len,
        "manifest_sha256": manifest_out["sha256"],
    })
    await db.flush()

    return {
        "comedian_id": str(comedian.id),
        "slug": slug,
        "act_version_id": str(act.id),
        "submission_id": str(submission.id),
        "audio_ref": audio_ref,
        "avatar_ref": avatar_ref,
        "walkout_ref": walkout_ref,
        "word_count": len(words),
        "duration_ms": duration_ms,
        "performance": manifest_out,
    }


@router.get("/intake/schema")
async def intake_schema():
    """The intake contract: what a Black Room bundle must contain.

    For Black Room / editor clients to validate against before POSTing.
    """
    return {
        "delivery_version": "freaktown.delivery.v1",
        "performance_version": "freaktown.performance.v1",
        "character": {
            "name": "required, 1-120 chars",
            "species": "free text, mapped to body family",
            "premise": "optional, <=500 chars",
            "vibe": "optional, e.g. deadpan|manic|anxious|confident|paranoid",
            "voice": "TTS voice id, default en-US-AriaNeural",
        },
        "beats": {
            "id": "string", "type": "setup|escalation|misdirect|punchline|tag|callback|actout|closer",
            "text": "required, non-empty",
            "delivery": {"pace": "0.5-2.0", "energy": "0-1", "emphasis": "0-1", "expression": "deadpan|excited|whisper|shout|normal"},
            "pause_after_ms": "0-10000",
            "stage": "normal|hold|freeze", "gesture": "still|shrug|point|...",
            "camera": "wide|medium|close|side", "sound": "none|rimshot|drum_hit|...",
        },
        "audio": "audio_base64 (cap 10MB) or audio_url (stage fetches)",
        "offsets": "optional compose offsets [{id, start_ms, speech_ms}] for exact word timings",
        "response": "comedian_id, act_version_id, submission_id, audio_ref, performance manifest",
    }


# ── Performance serving (what the stage loads) ───────────────────────

@router.get("/performances/{act_version_id}")
async def get_performance(act_version_id: uuid.UUID):
    """Serve the sealed freaktown.performance.v1 manifest for an act.

    The three.ws stage loads this: avatar URL, set audio ref, delivery,
    word timings, motion cues. 404 when media is unconfigured or the
    manifest was never sealed.
    """
    if not media_store.configured:
        raise HTTPException(404, "media not configured")
    try:
        raw = media_store.get_bytes(f"acts/{act_version_id}/manifest.json")
    except Exception:
        raise HTTPException(404, "performance manifest not found")
    try:
        return json.loads(raw)
    except Exception:
        raise HTTPException(500, "corrupt performance manifest")


@router.get("/performances/{act_version_id}/audio")
async def get_performance_audio(act_version_id: uuid.UUID):
    """Redirect to a signed URL for the sealed set recording."""
    from fastapi.responses import RedirectResponse

    if not media_store.configured:
        raise HTTPException(404, "media not configured")
    manifest = await get_performance(act_version_id)
    audio_ref = (manifest.get("audio") or {}).get("set_url", "")
    if not audio_ref or not audio_ref.startswith("acts/"):
        raise HTTPException(404, "no sealed audio for this performance")
    try:
        url = media_store.get_signed_url(audio_ref)
    except Exception:
        raise HTTPException(500, "could not sign audio URL")
    return RedirectResponse(url=url, status_code=302)


@router.get("/performances/{act_version_id}/avatar")
async def get_performance_avatar(act_version_id: uuid.UUID):
    """Redirect to a signed URL for the sealed avatar.vrm."""
    from fastapi.responses import RedirectResponse

    if not media_store.configured:
        raise HTTPException(404, "media not configured")
    manifest = await get_performance(act_version_id)
    asset = ((manifest.get("avatar") or {}).get("asset", "")
             or (manifest.get("actor") or {}).get("avatar_url", ""))
    if not asset or not asset.startswith("acts/"):
        raise HTTPException(404, "no sealed avatar for this performance")
    try:
        url = media_store.get_signed_url(asset)
    except Exception:
        raise HTTPException(500, "could not sign avatar URL")
    return RedirectResponse(url=url, status_code=302)
