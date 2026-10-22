"""Voice-linked face: Rhubarb poses -> viseme intents, expression envelopes,
room-event reaction policy.

Stdlib only. Pure functions (no network, no clock) so the contract suite
can pin them. Additive: nothing here renames any existing contract field.

Channel discipline (mirrors LipSync.ts): mouth = voice, face = beats +
reactions, blink = timer. This module emits mouth frames and face frames
separately; renderers must never let one channel clear another.
"""

from face_profiles import EXPRESSION_INTENTS, to_pog_face

# Rhubarb pose -> POG_FACE_V1 viseme intent. Calibration v1: retune this
# one dict, nothing else. Poses: A closed MBP, B open k/g, C E-spread,
# D wide ah, E rounded oh, F puckered oo, G teeth FV, H tongue L, X rest.
RHUBARB_TO_INTENT = {
    "A": "viseme_PP",
    "B": "viseme_kk",
    "C": "viseme_E",
    "D": "viseme_aa",
    "E": "viseme_O",
    "F": "viseme_U",
    "G": "viseme_FF",
    "H": "viseme_DD",
    "X": "viseme_sil",
}

# Delivery-beat expression words -> (face target, weight). Mirrors the
# runtime ExpressionLayer map; keep the two in sync when adding words.
DELIVERY_TO_FACE = {
    "deadpan": ("neutral", 1.0),
    "excited": ("happy", 0.9),
    "whisper": ("neutral", 0.35),
    "shout": ("surprised", 0.8),
    "normal": ("neutral", 0.6),
    # Seen in real take timelines (performance.expression):
    "grin": ("happy", 1.0),
    "confused": ("surprised", 0.5),
    "annoyed": ("angry", 0.8),
    "surprised": ("surprised", 0.8),
    "love": ("happy", 0.9),
    "afraid": ("surprised", 0.6),
    "disgust": ("angry", 0.7),
    "contempt": ("angry", 0.6),
}


# Every expression word any producer may name (beats, takes, reactor,
# Omni tone overrides). The override gate in resolve_expression.
EXPRESSION_WORDS = frozenset(DELIVERY_TO_FACE) | frozenset(
    EXPRESSION_INTENTS)


def resolve_expression(event=None, emotion=None, intensity=None):
    """Room/Omni output -> (expression_word, intensity).

    Default is the event's own expression from REACTIONS; an explicit
    emotion word (authored beat, or Omni hearing tone/prosody) overrides
    it when it names a known expression. Unknown everything -> deadpan.
    Pure function — the single place event+emotion become a face."""
    try:
        inten = 1.0 if intensity is None else max(
            0.0, min(1.0, float(intensity)))
    except Exception:
        inten = 1.0
    base = None
    try:
        if event in (REACTIONS or {}):
            base = REACTIONS[event]
    except Exception:
        base = None
    word = (base or {}).get("expression", "deadpan")
    if base is not None:
        try:
            inten = max(0.0, min(1.0, float(intensity) if intensity
                                 is not None else base.get(
                                     "intensity", 1.0)))
        except Exception:
            inten = 1.0
    emo = str(emotion or "").lower()
    if emo in EXPRESSION_WORDS:
        word = emo
    return word, round(inten, 3)


def mouth_cues_to_face_frames(mouth_cues_doc, morph_names,
                               format_hint="glb"):
    """pog.mouth-cues.v1 + avatar morphs -> timed mouth frames.

    Returns {"frames": [{start_ms, end_ms, pose, intent, morph, weight}],
    "unmapped_visemes": [...], "jaw_fallbacks": n}. A viseme the avatar
    lacks falls back to jaw_open at the pose angle (jaw is the honest
    universal mouth); poses never invent morph names.
    """
    try:
        cues = (mouth_cues_doc or {}).get("cues", []) or []
    except Exception:
        cues = []
    resolved = to_pog_face(morph_names, format_hint)
    intents = resolved.get("intents", {})
    jaw = intents.get("jaw_open")
    frames, unmapped, fallbacks = [], [], 0
    for c in cues:
        if not isinstance(c, dict):
            continue
        pose = str(c.get("pose", "X")).upper()
        intent = RHUBARB_TO_INTENT.get(pose, "viseme_sil")
        morph = intents.get(intent)
        weight = 1.0
        if morph is None and jaw is not None:
            morph, weight, fallbacks = jaw, 1.0, fallbacks + 1
            try:
                weight = max(0.0, min(1.0, abs(float(c.get("angle", -0.2)))
                             / 0.35))
            except Exception:
                weight = 1.0
        if morph is None:
            if intent not in unmapped:
                unmapped.append(intent)
            continue
        try:
            start_ms = int(c.get("start_ms", 0))
            end_ms = int(c.get("end_ms", start_ms))
        except Exception:
            continue
        frames.append({"start_ms": start_ms, "end_ms": end_ms,
                       "pose": pose, "intent": intent, "morph": morph,
                       "weight": round(weight, 3)})
    frames.sort(key=lambda f: f["start_ms"])
    return {"frames": frames, "unmapped_visemes": sorted(unmapped),
            "jaw_fallbacks": fallbacks}


def expression_envelope(start_ms, end_ms, attack_ms=120, decay_ms=300,
                        peak=1.0):
    """Beat span -> weight keyframes [(t_ms, weight)] with attack ramp,
    sustain, and decay tail. Renderers interpolate linearly; no pops."""
    try:
        s, e = int(start_ms), int(end_ms)
    except Exception:
        return []
    if e <= s:
        return [(s, 0.0)]
    try:
        peak = max(0.0, min(1.0, float(peak)))
    except Exception:
        peak = 1.0
    attack = max(0, int(attack_ms))
    decay = max(0, int(decay_ms))
    keys = [(s, 0.0)]
    held = e - s
    if attack > 0 and attack < held:
        keys.append((s + attack, round(peak, 3)))
    else:
        keys.append((s, round(peak, 3)))
    if decay > 0:
        keys.append((e, round(peak, 3)))
        keys.append((e + decay, 0.0))
    else:
        keys.append((e, 0.0))
    return keys


# Room events -> face/gesture/gaze. Existing runtime verbs only, so the
# layer below needs no changes to perform any of these.
REACTIONS = {
    # single laugh / one POG press
    "room_laugh": {"expression": "smirk", "intensity": 0.7,
                   "hold_ms": 800, "gesture": None, "gaze": None},
    # >=3 POG presses inside 2000 ms
    "pog_burst": {"expression": "smile", "intensity": 1.0,
                  "hold_ms": 1500, "gesture": ("lean", 0.5),
                  "gaze": None},
    # sustained crowd energy
    "applause": {"expression": "smile", "intensity": 1.0,
                 "hold_ms": 2000, "gesture": ("lean", 0.4),
                 "gaze": None},
    # shout-band energy + speech (heckler)
    "heckle": {"expression": "annoyed", "intensity": 0.8,
               "hold_ms": 1200, "gesture": None,
               "gaze": "gaze.audience"},
    # >2.5 s low energy right after a punchline beat
    "silence_after_punch": {"expression": "surprised", "intensity": 0.4,
                            "hold_ms": 1000, "gesture": ("lean", 0.6),
                            "gaze": None},
}

POG_BURST_COUNT = 3
POG_BURST_WINDOW_MS = 2000
SILENCE_AFTER_PUNCH_MS = 2500

# Room events -> live-stage runtime.react() kinds (crowd.reaction).
# Their kinds play sfx + excite the room + trigger a reaction.* face,
# so the reactor output gains sound for free through this map.
STAGE_KINDS = {
    "room_laugh": "laugh",
    "pog_burst": "laugh",
    "applause": "clap",
    "heckle": "boo",
    "silence_after_punch": "crickets",
}


def to_stage_kind(event):
    """REACTIONS key -> live-stage crowd kind, or None if unmapped."""
    try:
        return STAGE_KINDS.get(str(event))
    except Exception:
        return None


class ReactionPolicy:
    """Pure room-event -> reaction classifier. Feed it POG-press times,
    crowd-energy samples, and beat markers; it emits REACTIONS keys.
    No clock inside: callers pass now_ms."""

    def __init__(self):
        self.pog_presses = []  # ms timestamps, pruned per call
        self.last_punch_ms = None

    def mark_punch(self, now_ms):
        self.last_punch_ms = int(now_ms)

    def decide(self, now_ms, pog_pressed=False, crowd=None,
               beat_kind=None):
        """crowd: None or {"level": 0-1, "speech": bool, "sustained": bool}.
        Returns a REACTIONS key or None. Never raises."""
        try:
            now = int(now_ms)
        except Exception:
            return None
        try:
            if pog_pressed:
                self.pog_presses.append(now)
            self.pog_presses = [t for t in self.pog_presses
                                if now - t <= POG_BURST_WINDOW_MS]
            if len(self.pog_presses) >= POG_BURST_COUNT:
                self.pog_presses = []
                return "pog_burst"
            c = crowd or {}
            level = float(c.get("level", 0.0) or 0.0)
            speech = bool(c.get("speech", False))
            sustained = bool(c.get("sustained", False))
            if sustained and level >= 0.6:
                return "applause"
            if speech and level >= 0.7:
                return "heckle"
            if (self.last_punch_ms is not None
                    and beat_kind == "punchline"
                    and now - self.last_punch_ms >= SILENCE_AFTER_PUNCH_MS
                    and level < 0.15):
                self.last_punch_ms = None  # fire once per punchline
                return "silence_after_punch"
            if pog_pressed:
                return "room_laugh"
            return None
        except Exception:
            return None
