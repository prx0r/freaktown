"""Sound + Delivery routes — Sound Factory and delivery sequencer API.

POST /v1/sound/generate    → generate walkout/SFX from structured intent
GET  /v1/sound/vocab       → genre/mood/energy/shape/flavor vocabularies
POST /v1/delivery/arrange  → flat text → freaktown.delivery.v1 beats
POST /v1/delivery/compose  → DeliveryScore → final WAV with exact timing
"""

import base64
import random
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.services.audio.factory import (
    SoundFactory, SoundRecipe, sound_factory,
    GENRES, MOODS, ENERGIES, SHAPES, FLAVORS, SFX_DEFS,
)
from backend.services.delivery.sequencer import (
    DeliveryScore, arrange, compose, SCHEMA_VERSION,
)

router = APIRouter()


# ── Sound Factory ────────────────────────────────────────────────────

class SoundRequest(BaseModel):
    type: str = Field(..., description="walkout | sfx")
    genre: str = Field("funk")
    mood: str = Field("absurd")
    energy: str = Field("high")
    shape: str = Field("hit")
    flavor: str = Field("")
    duration: float = Field(8.0, ge=1, le=11)
    seed: int = Field(-1, description="-1 = random")
    sfx_name: str = Field("", description="rimshot | bomb | success | boo | laugh | drum_hit")


@router.get("/sound/vocab")
async def sound_vocab():
    """Controlled vocabularies for the Sound Factory UI."""
    return {
        "genres": list(GENRES.keys()),
        "moods": MOODS,
        "energies": ENERGIES,
        "shapes": list(SHAPES.keys()),
        "flavors": FLAVORS,
        "sfx": list(SFX_DEFS.keys()),
    }


@router.post("/sound/generate")
async def generate_sound(req: SoundRequest):
    """Generate a sound from structured intent. Returns base64 WAV + recipe."""
    if req.type not in ("walkout", "sfx"):
        raise HTTPException(400, "type must be walkout or sfx")
    seed = req.seed if req.seed >= 0 else random.randint(0, 2**31 - 1)
    recipe = SoundRecipe(
        type=req.type, genre=req.genre, mood=req.mood,
        energy=req.energy, shape=req.shape, flavor=req.flavor,
        duration=req.duration, seed=seed, sfx_name=req.sfx_name,
    )
    try:
        asset = await sound_factory.generate(recipe)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {
        "asset_id": asset.asset_id,
        "audio_b64": base64.b64encode(asset.audio_bytes).decode(),
        "duration": asset.duration,
        "prompt": asset.prompt,
        "recipe": asset.recipe,
        "cached": asset.cached,
    }


@router.post("/sound/again")
async def regenerate_sound(req: SoundRequest):
    """Reroll: same prompt, new seed."""
    req.seed = -1
    return await generate_sound(req)


# ── Delivery Sequencer ───────────────────────────────────────────────

class ArrangeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    provider: str = Field("qwen3")
    voice_id: str = Field("default")


@router.post("/delivery/arrange")
async def arrange_delivery(req: ArrangeRequest):
    """Flat text → freaktown.delivery.v1 beats with conservative timing."""
    score = arrange(req.text)
    score.provider = req.provider
    score.voice_id = req.voice_id
    return {"delivery": score.to_dict(), "schema": SCHEMA_VERSION}


class ComposeRequest(BaseModel):
    delivery: dict = Field(..., description="freaktown.delivery.v1 object")


@router.post("/delivery/compose")
async def compose_delivery(req: ComposeRequest):
    """DeliveryScore → final WAV with exact silence. Returns base64 audio."""
    try:
        score = DeliveryScore.from_dict(req.delivery)
    except Exception as e:
        raise HTTPException(400, f"Invalid delivery object: {e}")
    wav = await compose(score)
    return Response(
        content=wav, media_type="audio/wav",
        headers={"X-Delivery-Schema": SCHEMA_VERSION, "X-Beats": str(len(score.beats))},
    )
