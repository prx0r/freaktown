"""Dressing Room API — natural language → PerformancePlan.

This is the creator-facing API. A creator describes how their character
should perform, and the system compiles it into a concrete motion plan.

Reference: anime.dm — Dressing Room section
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.performance import PRESET_ENGINES, PerformanceEngine, StyleProfile, SignatureMove
from backend.services.motion_compiler import MotionCompiler

router = APIRouter()


# ── Request/Response Schemas ────────────────────────────────────────

class StyleInput(BaseModel):
    """Style parameters for the dressing room."""
    energy: float | None = Field(None, ge=0, le=1, description="Movement energy (0=statue, 1=manic)")
    stillness: float | None = Field(None, ge=0, le=1, description="How still the character is (0=never, 1=frozen)")
    gesture_density: float | None = Field(None, ge=0, le=1, description="How often they gesture")
    gesture_amplitude: float | None = Field(None, ge=0, le=1, description="How big the gestures are")
    eye_contact: float | None = Field(None, ge=0, le=1, description="How much they look at audience/Ella")
    pacing: float | None = Field(None, ge=0, le=1, description="How much they move around")
    punchline_hold_ms: int | None = Field(None, ge=0, le=5000, description="Freeze duration after punchline")


class SignatureMoveInput(BaseModel):
    name: str
    action: str = Field(..., description="Semantic action (e.g. reaction.dead_stare)")
    intensity: float = Field(0.5, ge=0, le=1)
    trigger: str = Field("", description="When to trigger (e.g. after_big_punchline)")
    duration_ms: int = Field(0, description="0 = use motion default")


class DressingRoomRequest(BaseModel):
    """Full dressing room request."""
    body_class: str = Field("humanoid-v1", description="humanoid-v1, quadruped-v1, rigid-object-v1")
    preset: str | None = Field(None, description="Start from a preset: deadpan, nervous, confident, chaotic, awkward, low_energy")
    description: str | None = Field(None, description="Natural language description of how the character should perform")
    style: StyleInput | None = None
    signature_moves: list[SignatureMoveInput] | None = None
    duration_ms: int = Field(60000, ge=1000, le=300000, description="Performance duration in ms")
    appearance_id: str = Field("", description="Appearance ID")


class DressingRoomResponse(BaseModel):
    """Compiled performance plan."""
    engine: dict
    plan: dict
    recommendations: list[str] = []


# ── Natural Language Parser ─────────────────────────────────────────

def parse_description(description: str) -> dict:
    """Parse natural language description into style parameters.

    In production this would use an LLM. For now, keyword-based.
    """
    desc_lower = description.lower()
    style = {}
    tags = []

    # Energy
    if any(w in desc_lower for w in ["manic", "hyper", "wild", "crazy", "energetic"]):
        style["energy"] = 0.9
        tags.append("high-energy")
    elif any(w in desc_lower for w in ["low energy", "tired", "exhausted", "barely moving"]):
        style["energy"] = 0.15
        tags.append("low-energy")
    elif any(w in desc_lower for w in ["calm", "composed", "steady"]):
        style["energy"] = 0.4
        tags.append("calm")

    # Stillness
    if any(w in desc_lower for w in ["frozen", "still", "barely moves", "statue"]):
        style["stillness"] = 0.9
        tags.append("still")
    elif any(w in desc_lower for w in ["never stops", "constant movement", "restless"]):
        style["stillness"] = 0.1
        tags.append("restless")

    # Gestures
    if any(w in desc_lower for w in ["no gestures", "doesn't gesture", "arms at sides"]):
        style["gesture_density"] = 0.05
    elif any(w in desc_lower for w in ["big gestures", "expressive", "animated"]):
        style["gesture_amplitude"] = 0.8
        style["gesture_density"] = 0.7
    elif any(w in desc_lower for w in ["subtle", "minimal", "small movements"]):
        style["gesture_amplitude"] = 0.2
        style["gesture_density"] = 0.2

    # Eye contact
    if any(w in desc_lower for w in ["never looks", "avoids eye contact", "looks away"]):
        style["eye_contact"] = 0.1
    elif any(w in desc_lower for w in ["stares", "intense eye contact", "locked on"]):
        style["eye_contact"] = 0.95

    # Punchline hold
    if any(w in desc_lower for w in ["long pause", "dramatic pause", "lets it land"]):
        style["punchline_hold_ms"] = 1500
    elif any(w in desc_lower for w in ["quick", "fast-paced", "no pause"]):
        style["punchline_hold_ms"] = 300

    # Signature moves
    signature_moves = []
    if any(w in desc_lower for w in ["dead stare", "blank stare", "stares blankly"]):
        signature_moves.append({"name": "Signature Stare", "action": "reaction.dead_stare",
                               "intensity": 0.9, "trigger": "after_big_punchline"})
    if any(w in desc_lower for w in ["head tilt", "tilts head"]):
        signature_moves.append({"name": "Head Tilt", "action": "reaction.confused",
                               "intensity": 0.6, "trigger": "on_ella_question"})

    return {"style": style, "tags": tags, "signature_moves": signature_moves}


# ── Dressing Room Endpoint ──────────────────────────────────────────

@router.post("/dressing-room/compile", response_model=DressingRoomResponse)
async def compile_performance(req: DressingRoomRequest):
    """Compile a performance from dressing room inputs.

    Accepts a preset + optional overrides + natural language description.
    Returns a compiled PerformancePlan with timestamped motion cues.
    """
    # Start from preset or default
    if req.preset and req.preset in PRESET_ENGINES:
        engine = PerformanceEngine(
            style=StyleProfile(**PRESET_ENGINES[req.preset].style.__dict__),
            signature_moves=list(PRESET_ENGINES[req.preset].signature_moves),
            tags=list(PRESET_ENGINES[req.preset].tags),
        )
    else:
        engine = PerformanceEngine()

    # Parse natural language description
    recommendations = []
    if req.description:
        parsed = parse_description(req.description)

        # Apply parsed style
        for k, v in parsed["style"].items():
            setattr(engine.style, k, v)

        # Add tags
        engine.tags.extend(parsed["tags"])

        # Add parsed signature moves
        for sm in parsed["signature_moves"]:
            engine.signature_moves.append(SignatureMove(**sm))

        recommendations.append(f"Parsed description: applied {len(parsed['style'])} style parameters, {len(parsed['signature_moves'])} signature moves")

    # Apply explicit style overrides
    if req.style:
        if req.style.energy is not None:
            engine.style.energy = req.style.energy
        if req.style.stillness is not None:
            engine.style.stillness = req.style.stillness
        if req.style.gesture_density is not None:
            engine.style.gesture_density = req.style.gesture_density
        if req.style.gesture_amplitude is not None:
            engine.style.gesture_amplitude = req.style.gesture_amplitude
        if req.style.eye_contact is not None:
            engine.style.eye_contact = req.style.eye_contact
        if req.style.pacing is not None:
            engine.style.pacing = req.style.pacing
        if req.style.punchline_hold_ms is not None:
            engine.style.punchline_hold_ms = req.style.punchline_hold_ms
        recommendations.append("Applied explicit style overrides")

    # Apply signature moves
    if req.signature_moves:
        for sm in req.signature_moves:
            engine.signature_moves.append(SignatureMove(
                name=sm.name, action=sm.action, intensity=sm.intensity,
                trigger=sm.trigger, duration_ms=sm.duration_ms,
            ))
        recommendations.append(f"Added {len(req.signature_moves)} custom signature moves")

    # Compile
    compiler = MotionCompiler()
    plan = compiler.compile(
        engine=engine,
        body_class=req.body_class,
        duration_ms=req.duration_ms,
        appearance_id=req.appearance_id,
    )

    recommendations.append(f"Compiled {len(plan.all_cues())} motion cues for {req.duration_ms/1000:.0f}s performance")

    return DressingRoomResponse(
        engine=engine.to_dict(),
        plan=plan.to_dict(),
        recommendations=recommendations,
    )


# ── Preset Browser ──────────────────────────────────────────────────

@router.get("/dressing-room/presets")
async def list_presets():
    """List all available performance presets with descriptions."""
    return {
        "presets": {
            name: {
                "name": engine.name,
                "style": engine.style.to_dict(),
                "tags": engine.tags,
                "signature_moves": [
                    {"name": m.name, "action": m.action, "trigger": m.trigger}
                    for m in engine.signature_moves
                ],
                "description": _preset_description(name),
            }
            for name, engine in PRESET_ENGINES.items()
        }
    }


def _preset_description(name: str) -> str:
    """Human-readable description of a preset."""
    descriptions = {
        "deadpan": "Minimal movement, long freezes, intense stares. Think Steven Wright or Mitch Hedberg.",
        "nervous": "Constant fidgeting, avoided eye contact, quick gestures. Think early Andy Kaufman.",
        "confident": "Strong eye contact, deliberate gestures, commanding presence. Think Dave Chappelle.",
        "chaotic": "Maximum energy, wild gestures, unpredictable movement. Think Sam Kinison.",
        "awkward": "Long pauses, looked-away glances, minimal gestures. Think cringe comedy.",
        "low_energy": "Barely moving, soft voice territory, almost asleep. Think Stephen Wright on sedatives.",
    }
    return descriptions.get(name, "A performance style preset.")
