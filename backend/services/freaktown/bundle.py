"""Black Room adapter — freaktown artifacts in, killella performances out.

Freaktown (Blue Room / Black Room) is the creator UX: chatbar writer,
beat boxes, DAW editing, tempo templates, YOUR SETS library, three.ws
avatar stage. Killella is the show runtime. This module is the bridge —
read-only with respect to freaktown (we never edit that repo):

  bundle validation  — character.json + delivery.json + set.wav + meta.json
  beats → score      — freaktown.delivery.v1 dicts → DeliveryScore,
                       preserving every performance-intent field
  words from offsets — beat-level compose offsets → word timings for
                       captions (proportional split within each beat)
  species → body     — free-text species → BodyArchetype
  performance manifest — freaktown.performance.v1 for the stage

Schema authority stays freaktown.delivery.v1 (their schemas/delivery_v1.json).
Killella accepts the full schema and carries unknown-safe defaults.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field

from backend.services.clips import Word
from backend.services.delivery.sequencer import DeliveryScore

SCHEMA_VERSION = "freaktown.delivery.v1"
PERFORMANCE_SCHEMA_VERSION = "freaktown.performance.v1"
AVATAR_SCHEMA_VERSION = "freaktown.avatar.v1"

BEAT_TYPES = {"setup", "escalation", "misdirect", "punchline", "tag", "callback", "actout", "closer"}

# Free-text species (freaktown character.species) → killella body family.
SPECIES_MAP = {
    "human": "human",
    "person": "human",
    "man": "human",
    "woman": "human",
    "knight": "human",
    "dog": "dog",
    "puppy": "dog",
    "robot": "robot",
    "android": "robot",
    "machine": "robot",
    "roomba": "object",
    "vacuum": "object",
    "toaster": "object",
    "object": "object",
    "chair": "object",
    "pigeon": "animal",
    "bird": "animal",
    "cat": "animal",
    "animal": "animal",
    "monster": "monster",
    "goblin": "monster",
    "alien": "creature",
    "creature": "creature",
    "ghost": "creature",
    "moth": "creature",
    "lamp": "creature",  # Martin Lämp and friends
}


def species_to_body(species: str) -> str:
    """Map freaktown species text to a killella BodyArchetype value."""
    s = (species or "").lower()
    for key, body in SPECIES_MAP.items():
        if key in s:
            return body
    return "mystery"


def bundle_slug(name: str, text: str) -> str:
    """Same slug rule as freaktown app.py: name-hash + 6-hex digest."""
    base = re.sub(r"[^a-z0-9]+", "-", (name or "freak").lower()).strip("-")[:32] or "freak"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


@dataclass
class BundleValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_delivery(delivery: dict) -> BundleValidation:
    """Validate a freaktown.delivery.v1 dict. Collects all errors."""
    errors: list[str] = []
    if not isinstance(delivery, dict):
        return BundleValidation(False, ["delivery must be an object"])
    if delivery.get("version") != SCHEMA_VERSION:
        errors.append(f"version must be {SCHEMA_VERSION}")
    beats = delivery.get("beats")
    if not isinstance(beats, list) or not beats:
        errors.append("beats must be a non-empty array")
        return BundleValidation(False, errors)
    for i, b in enumerate(beats):
        if not isinstance(b, dict):
            errors.append(f"beats[{i}] must be an object")
            continue
        if not b.get("text", "").strip():
            errors.append(f"beats[{i}] has empty text")
        if b.get("type", "setup") not in BEAT_TYPES:
            errors.append(f"beats[{i}] has unknown type {b.get('type')!r}")
        pause = b.get("pause_after_ms", 300)
        if not isinstance(pause, int) or pause < 0 or pause > 10_000:
            errors.append(f"beats[{i}] pause_after_ms out of range 0-10000")
    voice = delivery.get("voice", {})
    if not isinstance(voice, dict) or not voice.get("voice_id"):
        errors.append("voice.voice_id required")
    return BundleValidation(not errors, errors)


def validate_bundle(bundle: dict) -> BundleValidation:
    """Validate an intake bundle: character + delivery (+ optional audio/meta)."""
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return BundleValidation(False, ["bundle must be an object"])
    character = bundle.get("character")
    if not isinstance(character, dict) or not (character.get("name") or "").strip():
        errors.append("character.name required")
    delivery = bundle.get("delivery")
    if not isinstance(delivery, dict):
        errors.append("delivery required")
    else:
        dv = validate_delivery(delivery)
        errors.extend(dv.errors)
    audio = bundle.get("audio_base64", "") or bundle.get("audio_url", "")
    if audio is not None and not isinstance(audio, str):
        errors.append("audio must be base64 string or url string")
    return BundleValidation(not errors, errors)


def bundle_to_score(delivery: dict) -> DeliveryScore:
    """Freaktown delivery dict → killella DeliveryScore.

    Raises ValueError on invalid input. Every performance-intent field
    (expression, gesture, camera, sound, stage, pauses) is preserved —
    the stage directs from these, so dropping them would mute the act.
    """
    v = validate_delivery(delivery)
    if not v.ok:
        raise ValueError(f"invalid delivery: {v.errors[0]}")
    return DeliveryScore.from_dict(delivery)


@dataclass
class BeatSpan:
    beat_id: str
    start_ms: int
    speech_ms: int
    pause_ms: int = 0

    @property
    def end_ms(self) -> int:
        """End of the beat including its post-hold pause (matches WAV)."""
        return self.start_ms + self.speech_ms + self.pause_ms


def spans_from_offsets(offsets: list[dict]) -> list[BeatSpan]:
    """Freaktown /api/compose offsets → beat spans.

    Offsets look like [{id, start_ms, speech_ms, pause_ms}].
    """
    spans = []
    for o in offsets:
        if not isinstance(o, dict) or "id" not in o:
            continue
        spans.append(BeatSpan(
            beat_id=str(o["id"]),
            start_ms=int(o.get("start_ms", 0)),
            speech_ms=int(o.get("speech_ms", 0)),
            pause_ms=int(o.get("pause_ms", 0)),
        ))
    return spans


def estimate_spans(beats: list[dict], total_ms: int | None = None,
                   ms_per_word: int = 400) -> list[BeatSpan]:
    """Fallback spans when the bundle has no compose offsets.

    Speech time is distributed proportionally by word count (same 400ms
    word assumption as the TTS fallback), pauses appended per beat.
    """
    spans: list[BeatSpan] = []
    cursor = 0
    counts = [max(1, len((b.get("text") or "").split())) for b in beats]
    if total_ms is not None:
        total_words = sum(counts)
        total_pause = sum(int(b.get("pause_after_ms", 300)) for b in beats)
        speech_budget = max(0, total_ms - total_pause)
        speech_ms_list = [int(speech_budget * c / total_words) for c in counts]
    else:
        speech_ms_list = [c * ms_per_word for c in counts]
    for b, speech_ms in zip(beats, speech_ms_list):
        pause = int(b.get("pause_after_ms", 300))
        spans.append(BeatSpan(beat_id=str(b.get("id")), start_ms=cursor,
                              speech_ms=speech_ms, pause_ms=pause))
        cursor += speech_ms + pause
    return spans


def words_from_beats(beats: list[dict], spans: list[BeatSpan]) -> list[Word]:
    """Beat texts + spans → word timings for captions.

    Words split each beat's speech window proportionally. Last word of a
    beat ends at speech end (pause belongs to the beat, not the word).
    """
    by_id = {s.beat_id: s for s in spans}
    words: list[Word] = []
    for b in beats:
        text = (b.get("text") or "").split()
        if not text:
            continue
        span = by_id.get(str(b.get("id")))
        if span is None or span.speech_ms <= 0:
            continue
        per_word = span.speech_ms / len(text)
        for i, w in enumerate(text):
            start = int(span.start_ms + i * per_word)
            end = int(span.start_ms + (i + 1) * per_word)
            words.append(Word(word=w, start_ms=start, end_ms=end))
    return words


# ── Avatar contract (freaktown.avatar.v1) ────────────────────────────
# VRM is the canonical performer format. The runtime asks what the
# avatar CAN do instead of assuming: a floating toaster with one viseme
# still performs. three.ws is a creation/import/fallback path — assets
# enter only when they satisfy this contract.

VRM_VISEMES = ["aa", "ih", "ou", "ee", "oh"]

VROID_DEFAULT_CAPABILITIES = {
    "humanoid": True,
    "blink": True,
    "visemes": list(VRM_VISEMES),
    "look_at": True,
    "expressions": ["happy", "angry", "sad", "surprised"],
}


def validate_avatar(avatar: dict) -> BundleValidation:
    """Validate a freaktown.avatar.v1 dict. Collects all errors."""
    errors: list[str] = []
    if not isinstance(avatar, dict):
        return BundleValidation(False, ["avatar must be an object"])
    if avatar.get("version", AVATAR_SCHEMA_VERSION) != AVATAR_SCHEMA_VERSION:
        errors.append(f"avatar version must be {AVATAR_SCHEMA_VERSION}")
    if avatar.get("format") not in ("vrm", "glb"):
        errors.append("avatar format must be vrm or glb (both accepted as-is, never converted)")
    if not (avatar.get("asset") or "").strip():
        errors.append("avatar asset required (key, URL, or inline ref)")
    caps = avatar.get("capabilities", {})
    if not isinstance(caps, dict):
        errors.append("avatar capabilities must be an object")
    else:
        for key in ("humanoid", "blink", "look_at"):
            if key in caps and not isinstance(caps[key], bool):
                errors.append(f"avatar capabilities.{key} must be boolean")
        for key in ("visemes", "expressions"):
            if key in caps and (
                not isinstance(caps[key], list)
                or not all(isinstance(v, str) for v in caps[key])
            ):
                errors.append(f"avatar capabilities.{key} must be string list")
    return BundleValidation(not errors, errors)


def avatar_capabilities(avatar: dict | None) -> dict:
    """Effective capabilities: declared avatar.json merged over VRoid
    defaults (declared keys win, including False). Absent avatar.json
    assumes a standard VRoid VRM — three-vrm still probes at runtime."""
    caps = dict(VROID_DEFAULT_CAPABILITIES)
    caps["visemes"] = list(VRM_VISEMES)
    caps["expressions"] = list(VROID_DEFAULT_CAPABILITIES["expressions"])
    if isinstance(avatar, dict) and isinstance(avatar.get("capabilities"), dict):
        for key, value in avatar["capabilities"].items():
            if key in caps:
                caps[key] = value
    return caps


def can_viseme(avatar: dict | None, viseme: str) -> bool:
    return viseme in avatar_capabilities(avatar).get("visemes", [])


def translate_capabilities(body_caps: dict) -> dict:
    """freak.character/v1 capabilities → freaktown.avatar.v1 capabilities.
    Declared-only: unknown means False (never assume a mouth)."""
    body_caps = body_caps if isinstance(body_caps, dict) else {}
    expressions = (body_caps.get("face_profile", {}) or {}).get("morph_names", [])
    if not expressions and body_caps.get("facial_animation"):
        expressions = ["happy", "angry", "sad", "surprised"]
    visemes = [m for m in expressions
               if m in ("jawOpen", "jaw", "mouthOpen", "aa", "ih", "ou",
                        "ee", "oh") or m.startswith("viseme_")]
    return {
        "humanoid": bool(body_caps.get("skeletal_animation", False)),
        "blink": False,
        "look_at": bool(body_caps.get("eye_gaze", False)),
        "visemes": visemes,
        "expressions": (["happy", "angry", "sad", "surprised"]
                        if body_caps.get("facial_animation") else []),
    }


def performance_avatar(body_manifest: dict | None) -> dict | None:
    """Compatibility adapter: product-side freak.character/v1 manifest →
    bridge-side freaktown.avatar.v1 block. ONE place where the two
    realities meet — no other code translates between them."""
    if not isinstance(body_manifest, dict):
        return None
    rt = ((body_manifest.get("appearance") or {}).get("runtime") or {})
    uri = rt.get("uri") or ""
    if not uri:
        return None
    fmt = rt.get("format", "glb")
    return {
        "version": AVATAR_SCHEMA_VERSION,
        "format": fmt if fmt in ("vrm", "glb") else "glb",
        "asset": uri,
        "capabilities": translate_capabilities({
            **(body_manifest.get("capabilities") or {}),
            "face_profile": body_manifest.get("face_profile", {}),
        }),
    }


# Default stage avatar: always available, never black. Known limitation:
# michelle.glb ships zero morph targets, so fallback performances move
# but don't lipsync (the three.ws forge pipeline is the real fix —
# generated avatars carry ARKit blendshapes).
DEFAULT_STAGE_AVATAR = "https://three.ws/avatars/michelle.glb"


def resolve_avatar(manifest: dict) -> tuple[str, str]:
    """Sealed manifest → (url_or_ref, source). Never empty.

    source is "sealed" (R2 ref, caller must sign), "provided" (absolute
    http URL, redirect directly), "local" (same-origin bundle asset,
    fetchable as-is), or "default" (stage fallback).
    """
    m = manifest if isinstance(manifest, dict) else {}
    asset = ((m.get("avatar") or {}).get("asset", "")
             or (m.get("actor") or {}).get("avatar_url", "")).strip()
    if asset.startswith("acts/"):
        return asset, "sealed"
    if asset.startswith("http://") or asset.startswith("https://"):
        return asset, "provided"
    if asset.startswith("/freaks/"):
        return asset, "local"
    return DEFAULT_STAGE_AVATAR, "default"


# ── Judge mode (character pack extension) ────────────────────────────
# One pack, two modes: performer stance vs judge seat. Judge mode is
# stance + framing + chrome + prompts + authority — never a separate
# character system. ANY character can eventually become a judge, which
# is what makes winning meaningful beyond one night.

PANEL_SEATS = ("stream-left", "ella-center", "chatgpt-right")
JUDGE_AUTHORITIES = ("full", "commentary", "none")


def validate_modes(modes: dict | None) -> BundleValidation:
    """Validate a character modes block. None/absent is valid (performer)."""
    if modes is None:
        return BundleValidation(True)
    if not isinstance(modes, dict):
        return BundleValidation(False, ["modes must be an object"])
    errors: list[str] = []
    judge = modes.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            errors.append("modes.judge must be an object")
        else:
            seat = judge.get("seat")
            if seat is not None and seat not in PANEL_SEATS:
                errors.append(f"modes.judge.seat must be one of {PANEL_SEATS}")
            authority = judge.get("authority")
            if authority is not None and authority not in JUDGE_AUTHORITIES:
                errors.append(f"modes.judge.authority must be one of {JUDGE_AUTHORITIES}")
            animations = judge.get("animations")
            if animations is not None and (
                not isinstance(animations, list)
                or not all(isinstance(a, str) for a in animations)
            ):
                errors.append("modes.judge.animations must be string list")
    performer = modes.get("performer")
    if performer is not None and not isinstance(performer, dict):
        errors.append("modes.performer must be an object")
    return BundleValidation(not errors, errors)


def build_performance_manifest(
    performance_id: str,
    character: dict,
    score: DeliveryScore,
    words: list[Word],
    audio_ref: str,
    duration_ms: int,
    episode_id: str = "",
    avatar: dict | None = None,
    walkout_ref: str = "",
    walkout_duration_ms: int = 0,
) -> dict:
    """Sealed freaktown.performance.v1 manifest — what the stage performs.

    Immutable once issued: avatar + audio + delivery + words + cues are
    frozen. The stage refuses to start a performance whose manifest is
    missing. The same folder (avatar.vrm + avatar.json + delivery.json +
    set.wav + walkout.wav + character.json) runs identically in the Black
    Room, killella rehearsal, killella live, and future clients.
    """
    body_class = f"{species_to_body(character.get('species', ''))}-v1"
    cues = []
    for b in score.beats:
        if b.gesture:
            cues.append({"at": "beat", "beat_id": b.id, "type": "gesture", "value": b.gesture})
        if b.camera:
            cues.append({"at": "beat", "beat_id": b.id, "type": "camera", "value": b.camera})
        if b.sound and b.sound != "none":
            cues.append({"at": "beat", "beat_id": b.id, "type": "sfx", "value": b.sound})
    avatar_block: dict = {
        "version": AVATAR_SCHEMA_VERSION,
        "format": (avatar or {}).get("format")
        if (avatar or {}).get("format") in ("vrm", "glb") else "vrm",
        "asset": (avatar or {}).get("asset", "") or character.get("avatar_url", ""),
        "capabilities": avatar_capabilities(avatar),
    }
    if isinstance(avatar, dict) and avatar.get("vrm_version"):
        avatar_block["vrm_version"] = avatar["vrm_version"]
    actor: dict = {
        "name": character.get("name", "Guest Freak"),
        "species": character.get("species", ""),
        "premise": character.get("premise", ""),
        "avatar_url": avatar_block["asset"],
        "body_class": body_class,
        "voice": {"provider": score.provider, "voice_id": score.voice_id},
    }
    if isinstance(character.get("modes"), dict):
        actor["modes"] = character["modes"]
    manifest = {
        "version": PERFORMANCE_SCHEMA_VERSION,
        "performance_id": performance_id,
        "episode_id": episode_id,
        "actor": actor,
        "avatar": avatar_block,
        "audio": {
            "set_url": audio_ref,
            "duration_ms": duration_ms,
            "walkout_url": walkout_ref,
            "walkout_duration_ms": walkout_duration_ms,
        },
        "delivery": score.to_dict(),
        "words": [{"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in words],
        "motion": {"cues": cues},
    }
    manifest["sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    return manifest
