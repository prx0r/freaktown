#!/usr/bin/env python3
"""Face profiles: vendor morph sets -> POG_FACE_V1 semantic intents.

Stdlib only. Detection is coverage-based over morph names sniffed from GLB
bytes; mapping NEVER invents a morph name that isn't in the file. Unknown
sets stay usable (procedural fallback) instead of mislabeled.

Profiles: NONE | JAW | ARKIT_52 | METAPERSON_MOBILE51 | VISEMES15 | OCULUS
| VRM | CUSTOM. JAW covers BASIC bodies and mascots (one working jaw,
analyser-driven, honest). METAPERSON_MOBILE51 = ARKit-majority face plus a
full Oculus-15 viseme set (Avatar SDK export shape).
"""

ARKIT_52 = frozenset({
    "eyeBlinkLeft", "eyeBlinkRight",
    "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight",
    "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight",
    "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight",
    "jawForward", "jawLeft", "jawRight", "jawOpen",
    "mouthClose", "mouthFunnel", "mouthPucker", "mouthLeft", "mouthRight",
    "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthStretchLeft",
    "mouthStretchRight", "mouthRollLower", "mouthRollUpper",
    "mouthShrugLower", "mouthShrugUpper", "mouthPressLeft", "mouthPressRight",
    "mouthLowerDownLeft", "mouthLowerDownRight",
    "mouthUpperUpLeft", "mouthUpperUpRight",
    "browDownLeft", "browDownRight", "browInnerUp",
    "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "noseSneerLeft", "noseSneerRight", "tongueOut",
})

OCULUS_15 = frozenset({
    "viseme_sil", "viseme_PP", "viseme_FF", "viseme_TH", "viseme_DD",
    "viseme_kk", "viseme_CH", "viseme_SS", "viseme_nn", "viseme_RR",
    "viseme_aa", "viseme_E", "viseme_I", "viseme_O", "viseme_U",
})

JAW_NAMES = frozenset({"jawOpen", "jaw", "mouthOpen"})

# VRM 1.0 expression presets (extensions.VRMC_vrm.expressions.preset).
# Semantically facial morphs even though they live outside mesh targetNames.
VRM_PRESETS = frozenset({
    "aa", "ee", "ih", "oh", "ou", "neutral", "blink", "blinkLeft",
    "blinkRight", "happy", "angry", "sad", "relaxed", "surprised",
    "lookUp", "lookDown", "lookLeft", "lookRight",
})
VRM_VISEMES = frozenset({"aa", "ee", "ih", "oh", "ou"})

# POG_FACE_V1: the semantic intents games/agents emit. Renderers map these
# to local morphs via to_pog_face(); never address morphTargetN directly.
POG_FACE_V1 = (
    "jaw_open", "mouth_open",
    "blink_left", "blink_right",
    "smile_left", "smile_right", "frown_left", "frown_right",
    "look_up", "look_down", "look_left", "look_right",
    "viseme_sil", "viseme_PP", "viseme_FF", "viseme_TH", "viseme_DD",
    "viseme_kk", "viseme_CH", "viseme_SS", "viseme_nn", "viseme_RR",
    "viseme_aa", "viseme_E", "viseme_I", "viseme_O", "viseme_U",
)

# Preferred morph per intent, first present name wins. Short viseme aliases
# (aa/ih/ou/ee/oh, VRM-style) are accepted fallbacks for the matching viseme.
_INTENT_CANDIDATES = {
    "jaw_open": ["jawOpen", "jaw", "mouthOpen"],
    "mouth_open": ["mouthOpen", "jawOpen"],
    "blink_left": ["eyeBlinkLeft", "blinkLeft", "blink", "eyesClosed"],
    "blink_right": ["eyeBlinkRight", "blinkRight", "blink", "eyesClosed"],
    "smile_left": ["mouthSmileLeft", "mouthSmile", "happy"],
    "smile_right": ["mouthSmileRight", "mouthSmile", "happy"],
    "frown_left": ["mouthFrownLeft", "angry", "sad"],
    "frown_right": ["mouthFrownRight", "angry", "sad"],
    "look_up": ["eyeLookUpLeft", "eyeLookUpRight"],
    "look_down": ["eyeLookDownLeft", "eyeLookDownRight"],
    "look_left": ["eyeLookInLeft", "eyeLookOutRight"],
    "look_right": ["eyeLookInRight", "eyeLookOutLeft"],
    "viseme_aa": ["viseme_aa", "aa"],
    "viseme_E": ["viseme_E", "ee"],
    "viseme_I": ["viseme_I", "ih"],
    "viseme_O": ["viseme_O", "oh"],
    "viseme_U": ["viseme_U", "ou"],
}
for _v in sorted(OCULUS_15):
    _INTENT_CANDIDATES.setdefault(_v, [_v])

# Stage expression words -> POG_FACE_V1 intent weights (× intensity).
EXPRESSION_INTENTS = {
    "neutral": [],
    "happy": [("smile_left", 1.0), ("smile_right", 1.0)],
    "love": [("smile_left", 1.0), ("smile_right", 1.0)],
    "sad": [("frown_left", 1.0), ("frown_right", 1.0)],
    "angry": [("frown_left", 1.0), ("frown_right", 1.0)],
    "surprised": [("jaw_open", 0.8), ("mouth_open", 0.6)],
    "afraid": [("jaw_open", 0.5)],
    "disgust": [("frown_left", 0.8), ("frown_right", 0.8)],
    "deadpan": [],
    "annoyed": [("frown_left", 0.4)],
    "smirk": [("smile_left", 0.7)],
}


def detect_face_profile(morph_names, format_hint="glb"):
    """Classify a morph-name set. Pure function, never raises."""
    try:
        if isinstance(morph_names, str) or not isinstance(
                morph_names, (list, tuple, set, frozenset)):
            return "NONE"
        names = {str(n) for n in morph_names}
    except Exception:
        return "NONE"
    if not names:
        return "NONE"
    arkit = len(names & ARKIT_52)
    oculus = len(names & OCULUS_15)
    vrm = len(names & VRM_PRESETS)
    if oculus >= 12 and arkit >= 30:
        return "METAPERSON_MOBILE51"
    if arkit >= 48:
        return "ARKIT_52"
    if oculus >= 12:
        return "VISEMES15"
    if vrm >= 4 and (names & VRM_VISEMES):
        return "VRM"
    if oculus >= 1:
        return "OCULUS"
    # A lone working jaw (BASIC bodies, mascots) is a jaw rig even though
    # jawOpen itself is an ARKit name — analyser-driven and honest.
    if names & JAW_NAMES and arkit < 4:
        return "JAW"
    if (format_hint or "").lower() == "vrm":
        return "VRM"
    if arkit > 0 or (names & JAW_NAMES):
        return "CUSTOM"
    return "CUSTOM" if len(names) > 0 else "NONE"


def to_pog_face(morph_names, format_hint="glb"):
    """Resolve POG_FACE_V1 intents to real morph names present in the file.

    Returns {profile, intents: {intent: morph_name}, visemes: [...],
    unmapped: [...]}. Intents with no available morph are listed in
    `unmapped`, never hallucinated — the renderer falls back to procedural.
    """
    names = {str(n) for n in (morph_names or [])} if morph_names else set()
    intents, unmapped = {}, []
    for intent in POG_FACE_V1:
        hit = next((c for c in _INTENT_CANDIDATES.get(intent, [])
                    if c in names), None)
        if hit is None:
            unmapped.append(intent)
        else:
            intents[intent] = hit
    return {
        "profile": detect_face_profile(names, format_hint),
        "intents": intents,
        "visemes": sorted(n for n in names if n in OCULUS_15),
        "unmapped": unmapped,
    }


def map_expression(expression, intensity=1.0):
    """Stage expression word -> [(intent, weight)]. Unknown words -> [] so
    the stage stays procedural instead of guessing a face."""
    try:
        w = float(intensity)
    except Exception:
        w = 1.0
    w = max(0.0, min(1.0, w))
    return [(intent, round(wt * w, 3))
            for intent, wt in EXPRESSION_INTENTS.get(
                str(expression or "").lower(), [])]
