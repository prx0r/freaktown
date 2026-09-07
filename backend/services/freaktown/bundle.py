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
import re
from dataclasses import dataclass, field

from backend.services.clips import Word
from backend.services.delivery.sequencer import DeliveryScore

SCHEMA_VERSION = "freaktown.delivery.v1"
PERFORMANCE_SCHEMA_VERSION = "freaktown.performance.v1"

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


def build_performance_manifest(
    performance_id: str,
    character: dict,
    score: DeliveryScore,
    words: list[Word],
    audio_ref: str,
    duration_ms: int,
    episode_id: str = "",
) -> dict:
    """Sealed freaktown.performance.v1 manifest — what the stage performs.

    Immutable once issued: audio + delivery + words + cues are frozen.
    The stage refuses to start a performance whose manifest is missing.
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
    manifest = {
        "version": PERFORMANCE_SCHEMA_VERSION,
        "performance_id": performance_id,
        "episode_id": episode_id,
        "actor": {
            "name": character.get("name", "Guest Freak"),
            "species": character.get("species", ""),
            "premise": character.get("premise", ""),
            "avatar_url": character.get("avatar_url", ""),
            "body_class": body_class,
            "voice": {"provider": score.provider, "voice_id": score.voice_id},
        },
        "audio": {"set_url": audio_ref, "duration_ms": duration_ms},
        "delivery": score.to_dict(),
        "words": [{"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in words],
        "motion": {"cues": cues},
    }
    manifest["sha256"] = hashlib.sha256(
        __import__("json").dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    return manifest
