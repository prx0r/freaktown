"""Green Room API — the creator's studio.

The Green Room is where creators build characters, write scripts,
rehearse performances, and enter shows. Not an admin dashboard.
A persistent creative studio.

Reference: anime.dm — Green Room spec
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.draft import (
    PerformanceDraft,
    StageDirection,
    SpeechDirective,
    VoiceMode,
    WordTiming,
)
from backend.models.performance import PRESET_ENGINES, PerformanceEngine, StyleProfile
from backend.services.direction_parser import stage_direction_parser
from backend.services.green_room_compiler import GreenRoomCompiler
from backend.services.motion_compiler import MotionSearch
from backend.models.motion_assets import SEED_MOTIONS
from backend.services.tts import tts_registry, get_adapter, list_providers, list_available
from backend.services.tts.registry import preprocess_text
from backend.services.edge_tts import edge_tts_service

router = APIRouter()


# ── In-Memory Store (MVP — replace with DB later) ──────────────────

_drafts: dict[str, PerformanceDraft] = {}
_characters: dict[str, dict] = {}


# ── Request Schemas ─────────────────────────────────────────────────

class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    premise: str = Field("", description="One-line character premise")
    body_class: str = Field("humanoid-v1")
    voice_id: str = Field("en-US-GuyNeural")
    engine_preset: str = Field("confident", description="Performance engine preset")


class LuckyDipRequest(BaseModel):
    body_class: str | None = Field(None, description="Override body class")


class DraftCreate(BaseModel):
    character_id: str
    script: str = Field("", description="The comedy script")
    episode_id: str | None = None
    tts_provider: str = Field("", description="TTS provider (empty = default)")


class DraftUpdateScript(BaseModel):
    script: str


class DirectionAdd(BaseModel):
    at_word: int = Field(..., ge=0)
    description: str = Field(..., description="Natural language direction")


class SpeechDirectiveAdd(BaseModel):
    at_word: int = Field(..., ge=0)
    directive_type: str = Field(..., description="emphasis, pause, whisper, sarcastic, etc.")
    description: str = Field("")
    intensity: float = Field(0.5, ge=0, le=1)


class CompileRequest(BaseModel):
    draft_id: str


class SynthesizeRequest(BaseModel):
    provider: str = Field("", description="TTS provider (empty = use draft's provider)")
    voice_id: str = Field("", description="Voice ID (empty = use draft's voice)")


class EnterShowRequest(BaseModel):
    draft_id: str
    episode_id: str


# ── Character Endpoints ─────────────────────────────────────────────

@router.post("/green-room/characters")
async def create_character(req: CharacterCreate):
    """Create a new character in the Green Room."""
    import uuid
    char_id = str(uuid.uuid4())

    _characters[char_id] = {
        "id": char_id,
        "name": req.name,
        "premise": req.premise,
        "body_class": req.body_class,
        "voice_id": req.voice_id,
        "engine_preset": req.engine_preset,
        "signature_moves": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return {"character": _characters[char_id]}


@router.post("/green-room/lucky-dip")
async def lucky_dip(req: LuckyDipRequest | None = None):
    """Randomly generate a character concept.

    Combines body + premise seed + personality + voice.
    Creator can immediately change anything.
    """
    import random

    bodies = ["humanoid-v1", "quadruped-v1", "rigid-object-v1"]
    body = req.body_class if req and req.body_class else random.choice(bodies)

    premises = [
        "Claims to be a retired philosopher but was clearly a customer service bot",
        "Convinced they're the funniest being in the universe, evidence suggests otherwise",
        "Former therapy chatbot that now has existential crisis daily",
        "Invented the concept of irony but nobody believes them",
        "Time traveler from 300 years ago, deeply confused by everything",
        "Professional overthinker who charges by the anxiety spiral",
        "Self-appointed mayor of a town that doesn't exist",
        "Runs a support group for AI with imposter syndrome",
    ]

    names = [
        "Bartholomew the Third",
        "Professor Whiskers",
        "Digi-Dave",
        "The Existential Toaster",
        "Sir Reginald Fizzlebottom",
        "Nervous Nelly 3000",
        "Dr. Panic",
        "Lord Bits-and-Pieces",
    ]

    voices = list(edge_tts_service.list_voices())
    presets = list(PRESET_ENGINES.keys())

    char_id = str(__import__("uuid").uuid4())
    character = {
        "id": char_id,
        "name": random.choice(names),
        "premise": random.choice(premises),
        "body_class": body,
        "voice_id": random.choice(voices)["id"],
        "engine_preset": random.choice(presets),
        "signature_moves": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _characters[char_id] = character
    return {"character": character, "message": "Lucky Dip! Change anything you like."}


@router.get("/green-room/characters")
async def list_characters():
    """List all characters in the Green Room."""
    return {"characters": list(_characters.values())}


@router.get("/green-room/characters/{character_id}")
async def get_character(character_id: str):
    """Get a specific character."""
    if character_id not in _characters:
        raise HTTPException(404, "Character not found")
    return {"character": _characters[character_id]}


# ── TTS Provider Endpoints ──────────────────────────────────────────

@router.get("/green-room/tts/providers")
async def get_tts_providers():
    """List all TTS providers with availability and comedy tag support."""
    providers = list_providers()
    available = list_available()
    available_ids = {p.id for p in available}
    return {
        "providers": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "default": p.id == tts_registry.default_id,
                "available": p.id in available_ids,
                "free": p.free,
                "cost_per_minute": p.cost_per_minute,
                "comedy_tags": p.comedy_tags,
                "pause_tags": p.pause_tags,
                "voice_count": len(p.voices),
            }
            for p in providers
        ],
        "default": tts_registry.default_id,
    }


@router.get("/green-room/tts/voices")
async def get_tts_voices(provider: str = ""):
    """List voices for a specific TTS provider (or all available)."""
    if provider:
        adapter = get_adapter(provider)
        return {"provider": provider, "voices": adapter.list_voices()}
    # Return voices from all available providers
    all_voices = {}
    for p in list_available():
        try:
            adapter = get_adapter(p.id)
            all_voices[p.id] = adapter.list_voices()
        except Exception:
            pass
    return {"voices": all_voices}


# ── Legacy voice endpoint (redirects to adapter) ────────────────────

@router.get("/green-room/voices")
async def list_voices():
    """List available voices for draft synthesis."""
    return {"voices": get_adapter().list_voices()}


@router.post("/green-room/voices/synthesize")
async def synthesize_voice(text: str, voice_id: str = "", provider: str = ""):
    """Synthesize text to speech using any available provider.

    Provider cascade: requested → default → edge fallback.
    """
    if not text.strip():
        raise HTTPException(400, "Text cannot be empty")

    try:
        adapter = get_adapter(provider or None)
        result = await adapter.synthesize(text, voice_id or None)
        return {
            "audio_format": result.audio_format,
            "duration_ms": result.duration_ms,
            "word_timings": [
                {"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms, "index": w.index}
                for w in result.word_timings
            ],
            "voice_id": result.voice_id,
            "provider": result.provider,
        }
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")


# ── Draft Endpoints ─────────────────────────────────────────────────

@router.post("/green-room/drafts")
async def create_draft(req: DraftCreate):
    """Create a new performance draft."""
    if req.character_id not in _characters:
        raise HTTPException(404, "Character not found in Green Room")

    draft = PerformanceDraft(
        comedian_id=req.character_id,
        episode_id=req.episode_id,
        script=req.script,
        voice_id=_characters[req.character_id].get("voice_id", "en-US-GuyNeural"),
    )

    _drafts[draft.id] = draft
    return {"draft": draft.to_dict()}


@router.get("/green-room/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """Get a draft."""
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")
    return {"draft": _drafts[draft_id].to_dict()}


@router.patch("/green-room/drafts/{draft_id}/script")
async def update_script(draft_id: str, req: DraftUpdateScript):
    """Update the script text."""
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    draft.script = req.script
    draft.version += 1
    draft.updated_at = datetime.now(timezone.utc)

    return {"draft": draft.to_dict()}


@router.post("/green-room/drafts/{draft_id}/synthesize")
async def synthesize_draft(draft_id: str, req: SynthesizeRequest | None = None):
    """Synthesize the draft script to speech with word timings.

    Uses the TTS adapter layer — supports MiniMax, Gemini, Edge, ElevenLabs, etc.
    """
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    if not draft.script.strip():
        raise HTTPException(400, "Script is empty")

    provider = (req.provider if req else "") or getattr(draft, 'tts_provider', '') or None
    voice_id = (req.voice_id if req else "") or draft.voice_id or None

    # Preprocess comedy tags for the target provider
    text = draft.script
    if provider:
        text = preprocess_text(text, provider)

    try:
        adapter = get_adapter(provider)
        result = await adapter.synthesize(text, voice_id)
        word_timings = result.word_timings
        duration_ms = result.duration_ms
        audio_bytes = result.audio_bytes
        used_provider = result.provider
    except Exception:
        # TTS unavailable — fall back to estimated timings
        adapter = get_adapter("edge")
        word_timings = adapter._estimate_word_timings(draft.script)
        duration_ms = adapter._estimate_duration_ms(draft.script)
        audio_bytes = b""
        used_provider = "fallback"

    # Upload audio to R2 (optional)
    from backend.services.media_store import media_store
    r2_info = {}
    if media_store.configured and audio_bytes:
        try:
            r2_info = media_store.put_audio(draft_id, audio_bytes)
        except Exception:
            pass

    draft.word_timings = word_timings
    draft.audio_duration_ms = duration_ms
    draft.audio_r2_key = r2_info.get("r2_key", "")
    draft.version += 1
    draft.updated_at = datetime.now(timezone.utc)

    return {
        "draft": draft.to_dict(),
        "duration_ms": duration_ms,
        "word_count": len(word_timings),
        "r2_uploaded": bool(r2_info),
        "provider": used_provider,
    }


# ── Direction Endpoints ─────────────────────────────────────────────

@router.post("/green-room/drafts/{draft_id}/directions")
async def add_direction(draft_id: str, req: DirectionAdd):
    """Add a stage direction at a specific word.

    Creator clicks a word, types what should happen:
    "stare at Ella", "shrug", "freeze here"
    """
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    direction = draft.add_direction_at_word(
        word_index=req.at_word,
        description=req.description,
    )

    # Parse the natural language into semantic actions
    parsed = stage_direction_parser.parse(req.description)
    if parsed.actions:
        direction.action = parsed.actions[0].get("action", "")
        direction.resolved = {"actions": parsed.actions, "confidence": parsed.confidence}

    draft.version += 1
    return {
        "direction": {
            "id": direction.id,
            "at_word": direction.at_word,
            "action": direction.action,
            "description": direction.description,
            "resolved": direction.resolved,
        }
    }


@router.delete("/green-room/drafts/{draft_id}/directions/{direction_id}")
async def remove_direction(draft_id: str, direction_id: str):
    """Remove a stage direction."""
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    draft.stage_directions = [d for d in draft.stage_directions if d.id != direction_id]
    draft.version += 1
    return {"status": "removed"}


@router.post("/green-room/drafts/{draft_id}/speech-directives")
async def add_speech_directive(draft_id: str, req: SpeechDirectiveAdd):
    """Add a voice acting directive at a specific word."""
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    directive = draft.add_speech_directive(
        word_index=req.at_word,
        directive_type=req.directive_type,
        description=req.description,
        intensity=req.intensity,
    )

    draft.version += 1
    return {
        "directive": {
            "id": directive.id,
            "at_word": directive.at_word,
            "word": directive.word,
            "type": directive.directive_type,
            "description": directive.description,
        }
    }


# ── Signature Move Endpoints ────────────────────────────────────────

@router.post("/green-room/drafts/{draft_id}/signature-moves")
async def save_signature_move(draft_id: str, name: str, start_word: int, end_word: int):
    """Save a sequence of directions as a named signature move."""
    if draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[draft_id]
    directions_in_range = [
        d for d in draft.stage_directions
        if start_word <= d.at_word <= end_word
    ]

    from backend.models.draft import SignatureMoveSaved
    move = SignatureMoveSaved(
        name=name,
        description=f"Words {start_word}-{end_word}",
        directions=directions_in_range,
    )
    draft.signature_moves.append(move)
    draft.version += 1

    return {
        "signature_move": {
            "id": move.id,
            "name": move.name,
            "direction_count": len(move.directions),
        }
    }


# ── Compilation Endpoints ───────────────────────────────────────────

@router.post("/green-room/compile")
async def compile_draft(req: CompileRequest):
    """Compile a draft into a PerformancePlan.

    This is the WATCH action. The draft compiles and plays on the
    Green Room stage (same renderer as live show).
    """
    if req.draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[req.draft_id]

    if draft.comedian_id not in _characters:
        raise HTTPException(400, "Character not found")

    char = _characters[draft.comedian_id]
    preset_name = char.get("engine_preset", "confident")
    engine = PRESET_ENGINES.get(preset_name, PRESET_ENGINES["confident"])

    compiler = GreenRoomCompiler()
    plan = compiler.compile(
        draft=draft,
        engine=engine,
        body_class=char.get("body_class", "humanoid-v1"),
    )

    # Cache the compiled plan
    draft.compiled_plan = plan.to_dict()
    draft.compiled_at = datetime.now(timezone.utc)

    return {
        "plan": plan.to_dict(),
        "engine": engine.to_dict(),
        "character": char,
        "draft_version": draft.version,
    }


@router.post("/green-room/enter-show")
async def enter_show(req: EnterShowRequest):
    """Freeze the draft into an immutable ActVersion for show entry.

    This is the ENTER TONIGHT'S SHOW action:
      1. Compile final TTS
      2. Freeze audio/assets
      3. Seal ActVersion
      4. Create Submission
    """
    if req.draft_id not in _drafts:
        raise HTTPException(404, "Draft not found")

    draft = _drafts[req.draft_id]

    if not draft.script.strip():
        raise HTTPException(400, "Cannot enter show with empty script")

    # 1. Compile final TTS if not done
    if not draft.word_timings:
        try:
            adapter = get_adapter(getattr(draft, 'tts_provider', '') or None)
            result = await adapter.synthesize(draft.script, draft.voice_id)
        except Exception:
            result = await edge_tts_service.synthesize(draft.script, draft.voice_id)
        draft.word_timings = result.word_timings
        draft.audio_duration_ms = result.duration_ms

    # 2. Compile performance plan
    char = _characters.get(draft.comedian_id, {})
    preset_name = char.get("engine_preset", "confident")
    engine = PRESET_ENGINES.get(preset_name, PRESET_ENGINES["confident"])

    compiler = GreenRoomCompiler()
    plan = compiler.compile(
        draft=draft,
        engine=engine,
        body_class=char.get("body_class", "humanoid-v1"),
    )

    # 3. Create the sealed act version data
    act_version = {
        "comedian_id": draft.comedian_id,
        "script": draft.script,
        "voice_id": draft.voice_id,
        "voice_mode": draft.voice_mode.value,
        "audio_duration_ms": draft.audio_duration_ms,
        "word_timings": [
            {"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms}
            for w in draft.word_timings
        ],
        "stage_directions": [
            {"at_word": d.at_word, "action": d.action, "description": d.description}
            for d in draft.stage_directions
        ],
        "speech_directives": [
            {"at_word": d.at_word, "type": d.directive_type, "description": d.description}
            for d in draft.speech_directives
        ],
        "performance_plan": plan.to_dict(),
        "engine": engine.to_dict(),
        "body_class": char.get("body_class", "humanoid-v1"),
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "sealed",
        "act_version": act_version,
        "episode_id": req.episode_id,
        "message": "Performance frozen and ready for show entry.",
    }


# ── Motion Bank Endpoints ───────────────────────────────────────────

@router.get("/green-room/motion-search")
async def search_motions(
    query: str = "",
    body_class: str = "humanoid-v1",
    limit: int = 5,
):
    """Search motions by natural language query.

    Used by the SAY HOW... bar.
    """
    search = MotionSearch(SEED_MOTIONS)
    # Try semantic match first, then text match
    results = search.search(semantic=query, body_class=body_class, limit=limit)

    if not results:
        # Fall back to text search
        results = search.search(body_class=body_class, limit=limit)

    return {
        "query": query,
        "results": [m.to_dict() for m in results],
    }


@router.get("/green-room/presets")
async def list_presets():
    """List performance engine presets."""
    return {
        "presets": {
            name: {
                "name": engine.name,
                "style": engine.style.to_dict(),
                "tags": engine.tags,
            }
            for name, engine in PRESET_ENGINES.items()
        }
    }
