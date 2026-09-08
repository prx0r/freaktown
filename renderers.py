#!/usr/bin/env python3
"""Renderer plug-ins: the game never knows what a Runway is.

A Character is identity + renderer bindings. `perform()` asks for an
outcome ({audio, renderer: auto, quality}) and the router picks the
cheapest capable renderer. Cloud providers are registered stubs until
keys exist — the routing logic is real and tested regardless.

Tiers (USD/min, public pricing at time of writing):
  FREE       glb / vrm / basic / portrait — client-side, ~$0
  STANDARD   bithuman essence             — ~$0.006-0.012
  EXPRESSIVE bithuman expression          — ~$0.012-0.024
  PREMIUM    heygen / simli / anam        — ~$0.08-0.16
  CINEMATIC  runway gwm-1                 — ~$0.20

Rendered MP4s cache permanently by content hash: sending to 100 friends
never re-renders. The Freak doesn't change; only the manifestation does.
"""

from __future__ import annotations

import hashlib
import json

TIERS = ["free", "standard", "expressive", "premium", "cinematic"]

# $/min upper bounds. Local renderers cost compute/CDN only.
COST_PER_MIN = {
    "basic": 0.0, "glb": 0.0, "vrm": 0.0, "portrait": 0.0, "lam": 0.0,
    "bithuman-essence": 0.012, "bithuman-expression": 0.024,
    "heygen": 0.10, "simli": 0.10, "anam": 0.16, "tavus": 0.10,
    "runway": 0.20,
}

TIER_OF = {
    "basic": "free", "glb": "free", "vrm": "free", "portrait": "free",
    "lam": "free", "bithuman-essence": "standard",
    "bithuman-expression": "expressive", "heygen": "premium",
    "simli": "premium", "anam": "premium", "tavus": "premium",
    "runway": "cinematic",
}

# What each renderer needs in the character manifest to be usable.
REQUIRES = {
    "basic": [],
    "glb": ["avatars.glb"],
    "vrm": ["avatars.vrm"],
    "portrait": ["identity.portrait"],
    "lam": ["avatars.lam.asset"],
    "bithuman-essence": ["avatars.bithuman.avatar_id"],
    "bithuman-expression": ["avatars.bithuman.avatar_id"],
    "heygen": ["avatars.heygen.avatar_id"],
    "simli": ["avatars.simli.face_id"],
    "anam": ["avatars.anam.persona_id"],
    "tavus": ["avatars.tavus.replica_id"],
    "runway": ["avatars.runway.avatar_id"],
}


class UnavailableError(Exception):
    """No configured renderer can take this performance."""


def _lookup(manifest: dict, dotted: str):
    cur = manifest
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur or None


def capable(manifest: dict) -> list[str]:
    """Renderers this character can actually use right now."""
    out = ["basic", "portrait"]  # always true: procedural + 2D fallback
    char = manifest if isinstance(manifest, dict) else {}
    for name, needs in REQUIRES.items():
        if name in ("basic", "portrait"):
            continue
        if all(_lookup(char, need) for need in needs):
            out.append(name)
    return out


def estimate(renderer: str, seconds: float) -> float:
    """Upper-bound USD for a performance. Used before spending anything."""
    return round(COST_PER_MIN.get(renderer, 0.0) * seconds / 60, 4)


def choose(manifest: dict, quality: str = "standard",
           allow_paid: bool = False) -> str:
    """Cheapest capable renderer at or below the requested tier.
    Paid tiers require explicit opt-in (the user pays for upgrades,
    never for having a character)."""
    want = TIERS.index(quality) if quality in TIERS else 1
    if not allow_paid:
        want = min(want, TIERS.index("free"))
    have = capable(manifest)
    options = [r for r in have if TIERS.index(TIER_OF[r]) <= want]
    if not options:
        raise UnavailableError("no capable renderer at this tier")
    # best affordable tier first (quality asks are budgets, not floors),
    # then cheapest within tier; prefer real bodies over fallbacks tied.
    pref = {"glb": 0, "vrm": 0, "basic": 1, "lam": 2, "portrait": 9}
    options.sort(key=lambda r: (-TIERS.index(TIER_OF[r]),
                                COST_PER_MIN.get(r, 0.0),
                                pref.get(r, 5)))
    return options[0]


def cache_key(renderer: str, asset: str, audio_sha: str,
              duration_ms: int) -> str:
    """Permanent MP4 cache identity: same inputs, same key, never re-render."""
    return "mp4_" + hashlib.sha256("|".join(
        [renderer, asset, audio_sha, str(duration_ms)]).encode()).hexdigest()[:16]


def perform(character: dict, audio_sha: str, duration_ms: int,
            quality: str = "standard", allow_paid: bool = False) -> dict:
    """Route one performance. Returns the render plan — the game treats
    every renderer as an identical black box from here on."""
    seconds = duration_ms / 1000
    renderer = choose(character, quality, allow_paid)
    asset = ""
    if renderer in ("glb", "vrm", "lam"):
        asset = _lookup(character, f"avatars.{renderer}") or ""
        if isinstance(asset, dict):
            asset = asset.get("asset", "")
    elif renderer == "portrait":
        asset = _lookup(character, "identity.portrait") or ""
    return {
        "renderer": renderer,
        "tier": TIER_OF[renderer],
        "asset": asset,
        "audio_sha": audio_sha,
        "duration_ms": duration_ms,
        "cost_usd": estimate(renderer, seconds),
        "cache_key": cache_key(renderer, asset, audio_sha, duration_ms),
    }


def manifest_template() -> dict:
    """The portable Character: identity + per-provider renderer bindings.
    New providers add a key under avatars/ — nothing else changes."""
    return {
        "schema": "freak.character/v1",
        "id": "",
        "identity": {"portrait": "", "canonical_prompt": "", "lore": "",
                     "personality": ""},
        "voice": {"provider": "qwen", "voice_id": ""},
        "music": {"walkout": "", "victory": ""},
        "avatars": {"portrait": "", "glb": "", "vrm": "",
                    "bithuman": {}, "runway": {}, "lam": {}},
        "socials": {},
    }
