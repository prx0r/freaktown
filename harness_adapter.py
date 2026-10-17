"""Mutuals Character Harness -> Freaktown performance/party acting vocabulary.

Source inspiration: https://github.com/mutuals-inc/character-harness
Apache-2.0. This is a Freaktown-specific interoperable adapter, not the
upstream live voice/runtime/player. No paid APIs, network, or side effects.

Preserve the Freaktown audio clock and immutable delivery.v1. A harness
"beat" has an EXACT textual ``span``, ``emotion``, ``register``, ``gesture``
and ``camera``. We resolve beats against measured word offsets; never
estimate timings for an acted punchline or invent motions a body can't do.
"""
from __future__ import annotations

import re
from typing import Any

EMOTIONS = {
    "happy": "face.smile", "playful": "face.smile", "warm": "face.smile",
    "amused": "face.smile", "smug": "face.smug", "excited": "face.smile",
    "sad": "face.frown", "shy": "face.frown", "grumpy": "face.annoyed",
    "angry": "face.annoyed", "annoyed": "face.annoyed",
    "surprised": "face.surprised", "shocked": "face.surprised",
    "confused": "reaction.confused", "deadpan": "face.deadpan",
    "neutral": "face.deadpan", "disgust": "face.disgusted",
}
GESTURES = {
    "wave": "gesture.wave", "nod": "gesture.nod", "shrug": "gesture.shrug",
    "point": "gesture.point", "cheer": "gesture.cheer",
    "lean": "gesture.lean", "lean-in": "gesture.lean",
    "sheepish": "gesture.sheepish", "surprise": "gesture.surprise",
}
CAMERAS = {
    "push-in": "COMIC_CLOSE", "close-up": "COMIC_CLOSE",
    "pull-back": "WIDE_STAGE", "wide": "WIDE_STAGE",
    "medium": "COMIC_MEDIUM", "side": "SIDE_STAGE",
}
MAX_BEATS = 64


def _word_key(x: str) -> str:
    return re.sub(r"[^\w]+", "", x, flags=re.UNICODE).lower()


def _motion(at_ms: int, action: str, layer: str, *, duration_ms: int = 900) -> dict:
    return {"at_ms": at_ms, "action": action, "motion_asset_id": None,
            "duration_ms": duration_ms, "intensity": 0.75,
            "bone_mask": "upper" if layer == "upper" else "head",
            "layer": layer}


def compile_harness_beats(text: str, beats: list[dict], words: list[dict],
                          capabilities: dict | None = None) -> dict:
    """Compile approved Mutuals-style beats into existing Freaktown cues.

    Timing source is caller-supplied word offsets. The caller MUST distinguish
    forced/TTS alignment from estimates (Freaktown's words_from_beats estimates
    offsets proportionally). When text and words disagree we fail closed.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be nonempty")
    if not isinstance(beats, list) or len(beats) > MAX_BEATS:
        raise ValueError("too many beats or invalid beats")
    if not isinstance(words, list) or len(words) > 1024:
        raise ValueError("words must be a bounded list of measured timings")
    tokens = list(re.finditer(r"\S+", text))
    if len(tokens) != len(words):
        raise ValueError("text/word alignment mismatch")
    for i, (token, word) in enumerate(zip(tokens, words)):
        if not isinstance(word, dict) or _word_key(token.group()) != _word_key(str(word.get("word", ""))):
            raise ValueError(f"text/word alignment mismatch at word {i}")
        if (not isinstance(word.get("start_ms"), (int, float))
                or not isinstance(word.get("end_ms"), (int, float))
                or word["end_ms"] < word["start_ms"] or word["start_ms"] < 0):
            raise ValueError(f"invalid word timing {i}")
        if i and word["start_ms"] < words[i - 1]["start_ms"]:
            raise ValueError("word timings must be sorted")
    caps = capabilities or {}
    humanoid = caps.get("humanoid", True) is not False
    supported = caps.get("expressions")  # absent -> renderer will degrade
    motion, camera, warnings = [], [], []
    cursor, previous_time = 0, -1
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict) or not isinstance(beat.get("span"), str):
            raise ValueError(f"beat {i} missing exact span")
        span = beat["span"]
        pos = text.find(span, cursor) if span else cursor
        if pos < 0 or pos >= len(text):
            raise ValueError(f"beat {i} span missing or out of order")
        idx = next((j for j, m in enumerate(tokens) if m.start() <= pos < m.end()), None)
        if idx is None:
            # An anchor on intervening whitespace points to the next word.
            idx = next((j for j, m in enumerate(tokens) if m.start() > pos), None)
        if idx is None:
            raise ValueError(f"beat {i} has no word to align")
        at_ms = int(words[idx]["start_ms"])
        if at_ms < previous_time:
            raise ValueError("beats must be chronologically ordered")
        previous_time = at_ms
        cursor = pos + len(span)
        emotion = str(beat.get("emotion") or "").lower()
        gesture = str(beat.get("gesture") or "none").lower()
        shot = str(beat.get("camera") or "none").lower()
        if emotion and emotion != "none":
            action = EMOTIONS.get(emotion)
            if action:
                # Where capability manifest is explicit, only stage common VRM
                # expression names that the avatar actually supports.
                target = {"face.smile": "happy", "face.smug": "happy",
                          "face.frown": "sad", "face.annoyed": "angry",
                          "face.surprised": "surprised", "reaction.confused": "surprised",
                          "face.deadpan": "neutral", "face.disgusted": "angry"}[action]
                if not isinstance(supported, list) or target in supported or target == "neutral":
                    motion.append(_motion(at_ms, action, "face", duration_ms=1500))
                else:
                    warnings.append(f"unsupported expression: {emotion}")
            else:
                warnings.append(f"unknown emotion: {emotion}")
        if gesture != "none":
            if gesture in GESTURES and humanoid:
                motion.append(_motion(at_ms, GESTURES[gesture], "upper"))
            else:
                warnings.append(f"unsupported gesture: {gesture}")
        if shot not in ("none", "hold", ""):
            mapped = CAMERAS.get(shot)
            if mapped:
                camera.append({"at_ms": at_ms, "camera": mapped})
            else:
                warnings.append(f"unknown camera: {shot}")
    return {"motion": sorted(motion, key=lambda c: c["at_ms"]),
            "camera": sorted(camera, key=lambda c: c["at_ms"]),
            "warnings": warnings, "timing": "provided-word-offsets", "source": "mutuals-beats/v1"}


def party_reaction(kind: str, *, smiling: bool = False) -> dict | None:
    """Cheap Party fallback using the same semantic acting vocabulary.

    This is an acting suggestion, never a score or laugh label. Room identity
    and game rules stay in party.py; face images stay on user devices.
    """
    if smiling or kind in ("laugh", "smile.detected"):
        return {"version": "mutuals-beats/v1", "emotion": "happy",
                "gesture": "nod", "camera": "none", "source": "audience-reaction"}
    if kind == "round.won":
        return {"version": "mutuals-beats/v1", "emotion": "surprised",
                "gesture": "cheer", "camera": "none", "source": "game-event"}
    if kind == "set.revealed":
        return {"version": "mutuals-beats/v1", "emotion": "deadpan",
                "gesture": "none", "camera": "none", "source": "game-event"}
    return None
