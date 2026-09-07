"""Sound Factory — constrained sound generation with Stable Audio Open Small.

Frontend never sends a prompt. It sends structured intent:
  {"type": "walkout", "genre": "funk", "mood": "absurd", "energy": "high", "duration": 9}

Backend owns the prompt compiler. Model: stable-audio-open-small (341M, 11s max).
License: Stability Community License (free commercial < $1M revenue).

Cache by recipe hash. AGAIN = mutate seed only, not prompt.
"""

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("freak_town.audio")

MODEL_ID = "stabilityai/stable-audio-open-small"
MAX_DURATION = 11.0


# ── Controlled vocabularies ──────────────────────────────────────────

GENRES = {
    "funk": {"instruments": "wah guitar, punchy electric bass, brass stabs", "bpm": 118, "character": "sleazy retro cop-show"},
    "rock": {"instruments": "distorted power chords, punchy live drums", "bpm": 138, "character": "stadium entrance"},
    "electronic": {"instruments": "driving synth bass, pulsing arps, neon pads", "bpm": 128, "character": "synthwave night drive"},
    "jazz": {"instruments": "walking upright bass, brushed drums, muted brass", "bpm": 108, "character": "cool nightclub"},
    "orchestral": {"instruments": "brass section, timpani, string swells", "bpm": 100, "character": "grand ceremonial fanfare"},
    "comedy": {"instruments": "tuba, plucked strings, slide whistle", "bpm": 100, "character": "quirky comedy entrance"},
    "hip-hop": {"instruments": "boom-bap drums, deep 808, soul sample chop", "bpm": 92, "character": "confident street strut"},
    "country": {"instruments": "twangy telecaster, pedal steel, train beat", "bpm": 120, "character": "honky-tonk entrance"},
    "metal": {"instruments": "double-kick drums, downtuned chugging guitars", "bpm": 150, "character": "aggressive arena stomp"},
    "disco": {"instruments": "four-on-floor kick, octave bass, string stabs", "bpm": 120, "character": "glittery dancefloor"},
    "punk": {"instruments": "buzzsaw power chords, driving drums", "bpm": 160, "character": "chaotic club riot"},
    "ambient": {"instruments": "soft pads, distant chimes, airy textures", "bpm": 70, "character": "dreamy ethereal float"},
}

MOODS = ["heroic", "confident", "absurd", "menacing", "chill", "chaotic", "sleazy", "mysterious", "melancholic", "triumphant"]
ENERGIES = ["low", "medium", "high", "unhinged"]

SHAPES = {
    "hit": "immediate strong opening, no slow intro, front-loaded impact",
    "groove": "continuous tight groove, loop-like structure, no long intro",
    "build": "rapid build in intensity over several seconds, decisive final hit",
    "fanfare": "short ceremonial fanfare phrase, clear beginning and ending",
    "weird": "quirky characterful production, unusual sonic detail, comedic",
}

FLAVORS = ["retro", "cheap-casino", "corporate", "medieval", "space-age", "cartoon", "western", "horror", "sports-arena", "public-access-TV", "circus", "detective-show", "video-game"]

SFX_DEFS = {
    "rimshot": {"duration": 2.5, "source": "snare drum, kick drum and crash cymbal", "action": "classic ba-dum-tss comedy rimshot", "production": "tight dry studio recording, immediate attack, fast decay"},
    "bomb": {"duration": 3.0, "source": "solo trombone", "action": "three exaggerated descending wah-wah notes", "production": "dry cartoon comedy sting, fast decay"},
    "success": {"duration": 3.0, "source": "bright brass ensemble and cymbal", "action": "short triumphant fanfare", "production": "punchy game-show victory sting, hard ending"},
    "boo": {"duration": 2.0, "source": "arena crowd", "action": "crowd booing, disapproval", "production": "live room ambience, natural decay"},
    "laugh": {"duration": 2.0, "source": "studio audience", "action": "warm sitcom laughter", "production": "close-miked crowd, natural decay"},
    "drum_hit": {"duration": 1.0, "source": "snare drum", "action": "single sharp comedy punctuation hit", "production": "dry studio, immediate attack"},
    # ── Imported from freaktown sound_bank.py (Black Room band/crowd) ──
    # Prompts preserved verbatim as the action; durations match theirs.
    "rimshot_long": {"duration": 3.0, "source": "drum kit and crash cymbal", "action": "Extended comedy rimshot, ba-dum-tss-crash, triumphant drum sting", "production": "tight studio recording, decisive ending"},
    "ba_dum_tss": {"duration": 2.0, "source": "snare, kick and cymbal", "action": "Classic ba-dum-tss comedy drums, two hits and a cymbal", "production": "dry studio recording, immediate attack"},
    "sting": {"duration": 2.0, "source": "orchestra hit", "action": "Dramatic orchestral sting, tension hit, surprise reveal sound", "production": "wide cinematic production, fast decay"},
    "laugh_big": {"duration": 4.0, "source": "large club audience", "action": "Large audience roaring with laughter, comedy club crowd going wild, 4 seconds", "production": "live room ambience, natural decay"},
    "clap": {"duration": 3.0, "source": "theater audience", "action": "Audience applause, clapping, appreciation, 3 seconds", "production": "live room ambience, natural decay"},
    "crickets": {"duration": 3.0, "source": "night field recording", "action": "Crickets chirping, awkward silence, comedy failure sound, 3 seconds", "production": "dry minimal production, fades out"},
    "gasp": {"duration": 2.0, "source": "studio audience", "action": "Audience gasping, shocked reaction, collective surprise, 2 seconds", "production": "close-miked crowd, natural decay"},
    "ohhhh": {"duration": 2.0, "source": "comedy club crowd", "action": "Audience saying ohhhh, shocked disapproval, comedy club reaction, 2 seconds", "production": "live room ambience, natural decay"},
    "fanfare": {"duration": 3.0, "source": "bright brass section", "action": "Triumphant fanfare, victory sting, celebration, bright brass, 3 seconds", "production": "punchy production, hard ending"},
    "sad_trombone": {"duration": 3.0, "source": "solo trombone", "action": "Comedy failure sound, sad trombone, wah-wah-wah, deflating, 3 seconds", "production": "dry cartoon production, descending pitch"},
    "suspense": {"duration": 3.0, "source": "low strings and pulse", "action": "Suspenseful build, tension rising, dramatic pause music, 3 seconds", "production": "tense minimal production, builds throughout"},
}

# ── Character walkouts, imported from freaktown sound_bank.py ──────────
# Full prompts (too specific for the genre/mood recipe grid). Used when
# a walkout recipe has genre == "character"; flavor selects the entry.
CHARACTER_WALKOUTS = {
    "conspiracy-pigeon": "Paranoid military snare drum with pigeon coos, nervous energy, absurdly heroic",
    "corporate-robot": "Horrible corporate hold music that drops into heavy bass, robot entrance",
    "oldest-roomba": "Grand orchestral entrance that ends with vacuum cleaner noise, absurdly epic",
    "medieval-linkedin": "Gregorian chant that transitions into motivational EDM, medieval knight entrance",
    "no-nose-nolan": "Sleazy detective show theme, police dog entrance, bouncy bass, confident",
}


# ── Recipe & Asset ───────────────────────────────────────────────────

@dataclass
class SoundRecipe:
    """Immutable recipe for a generated sound."""
    type: str  # walkout | sfx
    genre: str = ""
    mood: str = ""
    energy: str = ""
    shape: str = ""
    flavor: str = ""
    duration: float = 8.0
    seed: int = 0
    prompt_version: int = 1
    sfx_name: str = ""

    def to_dict(self) -> dict:
        return {
            "model": MODEL_ID,
            "type": self.type,
            "genre": self.genre, "mood": self.mood,
            "energy": self.energy, "shape": self.shape,
            "flavor": self.flavor,
            "duration": self.duration, "seed": self.seed,
            "prompt_version": self.prompt_version,
            "sfx_name": self.sfx_name,
        }

    @property
    def asset_id(self) -> str:
        # Legacy key (no provider). Prefer asset_id_for(provider).
        return self.asset_id_for("stable-audio")

    def asset_id_for(self, provider: str) -> str:
        """Cache key covering provider + model + prompt_version + recipe
        + seed (handoff contract). A prompt-compiler change (prompt_version
        bump) or a different backend must NEVER serve stale audio."""
        canonical = json.dumps({"provider": provider, **self.to_dict()},
                               sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def build_walkout_prompt(recipe: SoundRecipe) -> str:
    """Compile structured intent → Stable Audio prompt."""
    # Character walkouts bypass the recipe grid: their prompts are
    # hand-written per freak (imported from freaktown sound_bank.py).
    if recipe.genre == "character":
        base = CHARACTER_WALKOUTS.get(recipe.flavor, "")
        if base:
            return f"TrackType: Music, {base}, instrumental only, clean decisive ending"
    g = GENRES.get(recipe.genre, GENRES["funk"])
    shape_text = SHAPES.get(recipe.shape, SHAPES["hit"])
    parts = [
        "TrackType: Music,",
        f"Genre: {recipe.genre},",
        f"{g['character']} instrumental walk-on sting,",
        f"{g['instruments']},",
        f"{recipe.mood}, {recipe.energy} energy,",
        f"{g['bpm']} BPM,",
    ]
    if recipe.flavor:
        parts.append(f"{recipe.flavor} production,")
    parts.append(shape_text + ",")
    parts.append("instrumental only, clean decisive ending")
    return " ".join(parts)


def build_sfx_prompt(sfx_name: str) -> tuple[str, float]:
    """Compile SFX name → prompt + duration."""
    s = SFX_DEFS.get(sfx_name, SFX_DEFS["rimshot"])
    prompt = f"TrackType: SFX, {s['source']}, {s['action']}, {s['production']}"
    return prompt, s["duration"]


# ── Provider abstraction ─────────────────────────────────────────────

@dataclass
class AudioAsset:
    asset_id: str
    audio_bytes: bytes
    duration: float
    recipe: dict
    prompt: str
    cached: bool = False


class AudioProvider:
    """Abstract audio generation provider."""

    async def generate(self, recipe: SoundRecipe) -> AudioAsset:
        raise NotImplementedError


class StableAudioOpenSmall(AudioProvider):
    """Stable Audio Open Small — 341M params, 11s max, 8 steps."""

    def __init__(self):
        self._model = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import torch
            if not torch.cuda.is_available():
                self._available = False
                return False
            self._available = True
        except ImportError:
            self._available = False
            logger.info("Stable Audio not installed. Generation handled by remote worker.")
        return self._available

    async def generate(self, recipe: SoundRecipe) -> AudioAsset:
        if not self.is_available():
            raise RuntimeError("Stable Audio requires CUDA GPU. Use remote audio worker.")
        try:
            import torch
            import torchaudio
            from einops import rearrange
            from stable_audio_tools import get_pretrained_model
            from stable_audio_tools.inference.generation import generate_diffusion_cond
        except ImportError as e:
            raise RuntimeError(f"stable-audio-tools not installed: {e}")

        if recipe.type == "walkout":
            prompt = build_walkout_prompt(recipe)
            duration = min(recipe.duration, MAX_DURATION)
        else:
            prompt, duration = build_sfx_prompt(recipe.sfx_name)

        if self._model is None:
            model, config = get_pretrained_model(MODEL_ID)
            device = "cuda"
            self._model = model.to(device)
            self._config = config
        else:
            device = "cuda"

        seed = recipe.seed if recipe.seed >= 0 else random.randint(0, 2**31 - 1)
        output = generate_diffusion_cond(
            self._model,
            steps=8, cfg_scale=1.0,
            conditioning=[{"prompt": prompt, "seconds_total": duration}],
            sample_size=self._config["sample_size"],
            sampler_type="pingpong", seed=seed, device=device,
        )
        output = rearrange(output, "b d n -> d (b n)")
        sr = self._config["sample_rate"]
        samples = int(duration * sr)
        output = output[:, :samples]
        output = output.float().div(torch.max(torch.abs(output))).clamp(-1, 1)

        import io
        buf = io.BytesIO()
        torchaudio.save(buf, output.cpu(), sr, format="wav")
        return AudioAsset(asset_id=recipe.asset_id, audio_bytes=buf.getvalue(),
                          duration=duration, recipe=recipe.to_dict(), prompt=prompt)


class RemoteAudioWorker(AudioProvider):
    """Proxy to a remote GPU audio worker over HTTP."""

    def __init__(self):
        self.url = os.getenv("AUDIO_WORKER_URL", "")

    def is_available(self) -> bool:
        return bool(self.url)

    async def generate(self, recipe: SoundRecipe) -> AudioAsset:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.url}/generate", json=recipe.to_dict())
            r.raise_for_status()
            data = r.json()
            import base64
            return AudioAsset(
                asset_id=recipe.asset_id,
                audio_bytes=base64.b64decode(data["audio_b64"]),
                duration=recipe.duration,
                recipe=recipe.to_dict(),
                prompt=data.get("prompt", ""),
            )


# ── Cached factory ───────────────────────────────────────────────────

class SoundFactory:
    """Generate + permanently cache sounds by recipe hash."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path("assets/generated")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.local = StableAudioOpenSmall()
        self.remote = RemoteAudioWorker()
        from backend.services.audio.procedural import ProceduralProvider
        self.procedural = ProceduralProvider()

    def cached(self, recipe: SoundRecipe) -> AudioAsset | None:
        path = self.cache_dir / f"{recipe.asset_id}.wav"
        meta = self.cache_dir / f"{recipe.asset_id}.json"
        if path.exists() and meta.exists():
            return AudioAsset(asset_id=recipe.asset_id, audio_bytes=path.read_bytes(),
                              duration=recipe.duration, recipe=recipe.to_dict(),
                              prompt=json.loads(meta.read_text()).get("prompt", ""), cached=True)
        return None

    def _store(self, asset: AudioAsset):
        (self.cache_dir / f"{asset.asset_id}.wav").write_bytes(asset.audio_bytes)
        (self.cache_dir / f"{asset.asset_id}.json").write_text(
            json.dumps({"asset_id": asset.asset_id, "recipe": asset.recipe,
                        "prompt": asset.prompt, "duration": asset.duration}, indent=2))

    async def generate(self, recipe: SoundRecipe) -> AudioAsset:
        hit = self.cached(recipe)
        if hit:
            return hit
        # Chain: remote worker → local GPU → procedural instant synth.
        # Procedural covers walkouts (always available: rolling a Freak
        # immediately hears *something*). One-shot SFX still need a model
        # backend and 503 honestly without one.
        if self.remote.is_available():
            provider: AudioProvider = self.remote
        elif self.local.is_available():
            provider = self.local
        elif recipe.type == "walkout":
            provider = self.procedural
        else:
            raise RuntimeError(
                "SFX generation needs Stable Audio (CUDA) or AUDIO_WORKER_URL; "
                "procedural synth covers walkouts only."
            )
        asset = await provider.generate(recipe)
        self._store(asset)
        return asset

    async def again(self, recipe: SoundRecipe) -> AudioAsset:
        """Reroll: same prompt, new seed."""
        recipe.seed = random.randint(0, 2**31 - 1)
        return await self.generate(recipe)


sound_factory = SoundFactory()
