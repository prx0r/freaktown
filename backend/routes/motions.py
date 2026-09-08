"""Motion Search API — search the semantic motion bank.

REST endpoints for querying available motions by semantic action,
style, body class, or free-text description.
"""

from fastapi import APIRouter, Query

from backend.models.motion import BODY_MANIFESTS, SEMANTIC_ACTIONS
from backend.models.motion_assets import SEED_MOTIONS
from backend.services.motion_compiler import MotionSearch

router = APIRouter()


@router.get("/motions/search")
async def search_motions(
    semantic: str | None = Query(None, description="Semantic action (e.g. gesture.beat, reaction.dead_stare)"),
    style: str | None = Query(None, description="Comma-separated style tags (e.g. deadpan,restrained)"),
    body_class: str = Query("humanoid-v1", description="Body class filter"),
    max_energy: float | None = Query(None, ge=0, le=1),
    min_energy: float | None = Query(None, ge=0, le=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Search the motion bank for clips matching criteria."""
    style_tags = [s.strip() for s in style.split(",")] if style else None

    search = MotionSearch(SEED_MOTIONS)
    results = search.search(
        semantic=semantic,
        style=style_tags,
        body_class=body_class,
        max_energy=max_energy,
        min_energy=min_energy,
        limit=limit,
    )

    return {
        "query": {
            "semantic": semantic,
            "style": style_tags,
            "body_class": body_class,
        },
        "results": [m.to_dict() for m in results],
        "total": len(results),
    }


@router.get("/motions/semantic-actions")
async def list_semantic_actions():
    """List all available semantic actions in the Killella Motion Language."""
    by_category = {}
    for action, description in SEMANTIC_ACTIONS.items():
        category = action.split(".")[0]
        by_category.setdefault(category, []).append({
            "action": action,
            "description": description,
        })

    return {
        "categories": by_category,
        "total_actions": len(SEMANTIC_ACTIONS),
    }


@router.get("/motions/body-manifests")
async def list_body_manifests():
    """List all body capability manifests."""
    return {
        "manifests": {
            name: {
                "body_class": manifest.body_class,
                "capabilities": manifest.capabilities,
                "fallbacks": manifest.fallbacks,
                "supports_additive": manifest.supports_additive,
                "supports_face_expressions": manifest.supports_face_expressions,
                "capability_count": len(manifest.capabilities),
            }
            for name, manifest in BODY_MANIFESTS.items()
        }
    }


@router.get("/motions/stats")
async def motion_stats():
    """Get motion bank statistics."""
    by_source = {}
    by_body = {}
    by_category = {}

    for m in SEED_MOTIONS:
        by_source.setdefault(m.source, []).append(m.name)
        by_body.setdefault(m.body_class, []).append(m.name)
        for s in m.semantic:
            cat = s.split(".")[0]
            by_category.setdefault(cat, []).append(m.name)

    return {
        "total_motions": len(SEED_MOTIONS),
        "by_source": {k: len(v) for k, v in by_source.items()},
        "by_body_class": {k: len(v) for k, v in by_body.items()},
        "by_category": {k: len(v) for k, v in by_category.items()},
    }
