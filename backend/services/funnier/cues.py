"""Beat-anchored manifest cues → stage-ready timed cues.

The sealed manifest stores cues as {"at": "beat", "beat_id", ...} because
beats are the authoring unit. The stage consumes absolute-ms MotionCues
(plus camera cuts and sfx). This module is the bridge Gap 1 needed.

Timing source, in order:
  1. Measured offsets (funnier offsets.json → spans_from_offsets).
  2. Estimation (estimate_spans) — flagged "estimated": True so the
     stage knows karaoke/cues may drift slightly.

Unknown gesture/camera/sfx values are SKIPPED, never raised: a weird
value must not be able to kill a live performance.
"""

from .bundle import BeatSpan, estimate_spans, spans_from_offsets
from harness_adapter import compile_harness_beats

# gesture → (action, layer, bone_mask, duration_ms)
GESTURE_ACTION = {
    "shrug": ("shrug", "upper", "upper", 1500),
    "point": ("point", "upper", "upper", 1200),
    "lean": ("lean_in", "base", "full", 1800),
    "wave": ("wave", "upper", "upper", 1500),
    "still": (None, "", "", 0),  # explicit no-op, not an error
}

# expression → face-layer cue action
EXPRESSION_ACTION = {
    "deadpan": "face_deadpan",
    "excited": "face_excited",
    "whisper": "face_whisper",
    "shout": "face_shout",
    "normal": "face_neutral",
}

# funnier camera vocab → killella CameraPreset
CAMERA_MAP = {
    "wide": "WIDE_STAGE",
    "medium": "COMIC_MEDIUM",
    "close": "COMIC_CLOSE",
    "side": "SIDE_STAGE",
}


def _spans(manifest_cues, offsets, beats, duration_ms):
    """Measured spans when offsets exist, else estimated. Returns (spans, estimated)."""
    if offsets:
        spans = spans_from_offsets(offsets)
        if spans:
            return spans, False
    return estimate_spans(beats or [], total_ms=duration_ms), True


def _start_of(spans: list[BeatSpan], beat_id: str) -> int | None:
    for s in spans:
        if s.beat_id == beat_id:
            return s.start_ms
    return None


def resolve_cues(manifest: dict, offsets: list[dict] | None = None,
                 duration_ms: int | None = None) -> dict:
    """Manifest → {"motion": [...MotionCue], "camera": [...], "sfx": [...],
    "estimated": bool}. Never raises on bad values."""
    cues = (manifest.get("motion") or {}).get("cues", []) if isinstance(manifest, dict) else []
    delivery_beats = {}
    try:
        for b in (manifest.get("delivery") or {}).get("beats", []):
            delivery_beats[b.get("id")] = b
    except Exception:
        pass
    beats_for_est = [{"id": bid, "text": (delivery_beats.get(bid) or {}).get("text", ""),
                      "pause_after_ms": (delivery_beats.get(bid) or {}).get("pause_after_ms", 300)}
                     for bid in [c.get("beat_id") for c in cues if isinstance(c, dict)]]
    spans, estimated = _spans(cues, offsets, beats_for_est, duration_ms)

    motion, camera, sfx = [], [], []
    for c in cues:
        if not isinstance(c, dict):
            continue
        at = _start_of(spans, c.get("beat_id", ""))
        if at is None:
            continue  # unknown beat: skip, don't kill the show
        kind, value = c.get("type"), c.get("value")
        if kind == "gesture":
            mapped = GESTURE_ACTION.get(value)
            if not mapped or not mapped[0]:
                continue
            action, layer, mask, dur = mapped
            motion.append({"at_ms": at, "action": action,
                           "motion_asset_id": None, "duration_ms": dur,
                           "intensity": 0.6, "bone_mask": mask, "layer": layer})
        elif kind == "expression":
            action = EXPRESSION_ACTION.get(value)
            if not action:
                continue
            motion.append({"at_ms": at, "action": action,
                           "motion_asset_id": None, "duration_ms": 2000,
                           "intensity": 0.7, "bone_mask": "head",
                           "layer": "face"})
        elif kind == "camera":
            preset = CAMERA_MAP.get(value)
            if preset:
                camera.append({"at_ms": at, "camera": preset})
        elif kind == "sfx":
            if value:
                sfx.append({"at_ms": at, "name": value})
    # Optional Mutuals Character Harness acting overlay. Timing is
    # measured from the sealed performance's word offsets, not estimated.
    acting = manifest.get("acting") if isinstance(manifest, dict) else None
    if isinstance(acting, dict) and acting.get("schema") == "mutuals-beats/v1":
        line = " ".join(b.get("text", "") for b in
                        (manifest.get("delivery") or {}).get("beats", []))
        word_times = manifest.get("words") or []
        caps = (manifest.get("avatar") or {}).get("capabilities") or {}
        try:
            compiled = compile_harness_beats(line, acting.get("beats", []), word_times, caps)
        except (ValueError, TypeError):
            # Malformed/unaligned optional directions must never kill a show.
            compiled = {"motion": [], "camera": []}
        motion.extend(compiled["motion"])
        camera.extend(compiled["camera"])
        # Only the base cues are estimates when no explicit offsets exist.
        if not cues:
            estimated = False
        # This overlay must NOT relabel AI reactions as observed human laughs.
    motion.sort(key=lambda m: m["at_ms"])
    camera.sort(key=lambda m: m["at_ms"])
    sfx.sort(key=lambda m: m["at_ms"])
    return {"motion": motion, "camera": camera, "sfx": sfx, "estimated": estimated}
