"""Sound Factory package."""

from backend.services.audio.factory import (
    SoundFactory, SoundRecipe, AudioAsset, AudioProvider,
    StableAudioOpenSmall, RemoteAudioWorker,
    build_walkout_prompt, build_sfx_prompt,
    GENRES, MOODS, ENERGIES, SHAPES, FLAVORS, SFX_DEFS,
    CHARACTER_WALKOUTS,
    sound_factory, MODEL_ID,
)
from backend.services.audio.procedural import (
    ProceduralProvider, generate_wav, recipe_id, resolve_genre,
)

__all__ = [
    "SoundFactory", "SoundRecipe", "AudioAsset", "AudioProvider",
    "StableAudioOpenSmall", "RemoteAudioWorker", "ProceduralProvider",
    "build_walkout_prompt", "build_sfx_prompt",
    "generate_wav", "recipe_id", "resolve_genre",
    "GENRES", "MOODS", "ENERGIES", "SHAPES", "FLAVORS", "SFX_DEFS",
    "CHARACTER_WALKOUTS",
    "sound_factory", "MODEL_ID",
]
