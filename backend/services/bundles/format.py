"""Character bundle format — portable freak/ directory.

freaks/
  conspiracy-pigeon/
    character.json      # name, premise, voice config, walkout recipe
    avatar.glb          # three.ws rigged GLB
    voice_reference.wav # cloning reference (optional)
    walkout.mp3         # generated walkout sting (cached)
    success_sting.mp3
    bomb_sting.mp3
    system_prompt.md    # personality for LLM judge
    delivery.json       # freaktown.delivery.v1 (optional)

Drop folder → character can perform.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("freak_town.bundle")

BUNDLE_VERSION = "freaktown.bundle.v1"

REQUIRED_FILES = ["character.json"]
OPTIONAL_FILES = [
    "avatar.glb", "voice_reference.wav", "walkout.mp3",
    "success_sting.mp3", "bomb_sting.mp3",
    "system_prompt.md", "delivery.json",
]


@dataclass
class CharacterBundle:
    slug: str
    name: str
    premise: str
    voice_provider: str = "qwen3"
    voice_id: str = "default"
    body_class: str = "humanoid-v1"
    engine_preset: str = "confident"
    walkout: dict = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)  # name → path

    def to_dict(self) -> dict:
        return {
            "version": BUNDLE_VERSION,
            "slug": self.slug, "name": self.name, "premise": self.premise,
            "voice": {"provider": self.voice_provider, "voice_id": self.voice_id},
            "body_class": self.body_class, "engine_preset": self.engine_preset,
            "walkout": self.walkout, "files": self.files,
        }


def load_bundle(path: Path) -> CharacterBundle:
    """Load a character bundle from a freaks/<slug>/ directory."""
    char_path = path / "character.json"
    if not char_path.exists():
        raise ValueError(f"Bundle missing character.json: {path}")
    data = json.loads(char_path.read_text())

    voice = data.get("voice", {})
    files = {}
    for fname in REQUIRED_FILES + OPTIONAL_FILES:
        fpath = path / fname
        if fpath.exists():
            files[fname] = str(fpath)

    bundle = CharacterBundle(
        slug=data.get("slug", path.name),
        name=data.get("name", "Unknown"),
        premise=data.get("premise", ""),
        voice_provider=voice.get("provider", "qwen3"),
        voice_id=voice.get("voice_id", "default"),
        body_class=data.get("body_class", "humanoid-v1"),
        engine_preset=data.get("engine_preset", "confident"),
        walkout=data.get("walkout", {}),
        files=files,
    )
    return bundle


def save_bundle(bundle: CharacterBundle, root: Path) -> Path:
    """Save a character bundle to freaks/<slug>/."""
    dest = root / bundle.slug
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "character.json").write_text(json.dumps(
        {k: v for k, v in bundle.to_dict().items() if k != "files"}, indent=2))
    return dest


def list_bundles(root: Path) -> list[CharacterBundle]:
    """List all character bundles under a root directory."""
    bundles = []
    if not root.exists():
        return bundles
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "character.json").exists():
            try:
                bundles.append(load_bundle(child))
            except Exception as e:
                logger.warning(f"Skipping invalid bundle {child}: {e}")
    return bundles
