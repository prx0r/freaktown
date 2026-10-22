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
# Tail block (brow/eye/cheek/nose) appended 2026-10-21: the emotion
# carriers. VRM avatars only honour the head block (5 presets); ARKit
# avatars get the full face. Additive only: never rename/remove a field.
POG_FACE_V1 = (
    "jaw_open", "mouth_open",
    "blink_left", "blink_right",
    "smile_left", "smile_right", "frown_left", "frown_right",
    "look_up", "look_down", "look_left", "look_right",
    "viseme_sil", "viseme_PP", "viseme_FF", "viseme_TH", "viseme_DD",
    "viseme_kk", "viseme_CH", "viseme_SS", "viseme_nn", "viseme_RR",
    "viseme_aa", "viseme_E", "viseme_I", "viseme_O", "viseme_U",
    "brow_down_left", "brow_down_right", "brow_inner_up",
    "brow_outer_up_left", "brow_outer_up_right",
    "eye_squint_left", "eye_squint_right",
    "eye_wide_left", "eye_wide_right",
    "cheek_squint_left", "cheek_squint_right", "cheek_puff",
    "nose_sneer_left", "nose_sneer_right", "tongue_out",
    # Lower-face articulation for FACS-complete recipes (AU16/20/23):
    # appended 2026-10-21, same additive rule as the brow block.
    "mouth_stretch_left", "mouth_stretch_right",
    "mouth_press_left", "mouth_press_right",
    "mouth_lower_down_left", "mouth_lower_down_right",
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
    "viseme_aa": ["viseme_aa", "aa", "v_aa", "A", "mouth_a",
                  "Fcl_MTH_A"],
    "viseme_E": ["viseme_E", "ee", "v_e", "E", "mouth_e",
                 "Fcl_MTH_E"],
    "viseme_I": ["viseme_I", "ih", "v_ih", "I", "mouth_i",
                 "Fcl_MTH_I"],
    "viseme_O": ["viseme_O", "oh", "v_oh", "O", "mouth_o",
                 "Fcl_MTH_O"],
    "viseme_U": ["viseme_U", "ou", "v_ou", "U", "mouth_u",
                 "Fcl_MTH_U"],
    # Emotion carriers: exact ARKit names first, common aliases after.
    "brow_down_left": ["browDownLeft"],
    "brow_down_right": ["browDownRight"],
    "brow_inner_up": ["browInnerUp"],
    "brow_outer_up_left": ["browOuterUpLeft"],
    "brow_outer_up_right": ["browOuterUpRight"],
    "eye_squint_left": ["eyeSquintLeft"],
    "eye_squint_right": ["eyeSquintRight"],
    "eye_wide_left": ["eyeWideLeft"],
    "eye_wide_right": ["eyeWideRight"],
    "cheek_squint_left": ["cheekSquintLeft"],
    "cheek_squint_right": ["cheekSquintRight"],
    "cheek_puff": ["cheekPuff"],
    "nose_sneer_left": ["noseSneerLeft"],
    "nose_sneer_right": ["noseSneerRight"],
    "tongue_out": ["tongueOut"],
    "mouth_stretch_left": ["mouthStretchLeft"],
    "mouth_stretch_right": ["mouthStretchRight"],
    "mouth_press_left": ["mouthPressLeft"],
    "mouth_press_right": ["mouthPressRight"],
    "mouth_lower_down_left": ["mouthLowerDownLeft"],
    "mouth_lower_down_right": ["mouthLowerDownRight"],
}
for _v in sorted(OCULUS_15):
    _INTENT_CANDIDATES.setdefault(_v, [_v])

# Stage expression words -> POG_FACE_V1 intent weights (× intensity).
# Full-face recipes calibrated to the FACS canonical table (AUBlendNet
# ICCV'25 suppl. Table 2 — Happy AU6+12, Sad AU1+4+15, Surprise
# AU1+2+5+27, Fear AU1+2+4+5+7+20+26, Anger AU4+5+7+9+23, Disgust
# AU9+AU5+AU16, Contempt AU4+AU14+AU64):
#   AU1->brow_inner_up AU2->brow_outer_up AU4->brow_down AU5->eye_wide
#   AU6->cheek_squint AU7->eye_squint AU9->nose_sneer AU12->smile
#   AU14->dimple (unavailable: unilateral smile approx) AU15->frown
#   AU16->mouth_lower_down AU20->mouth_stretch AU23->mouth_press
#   AU26/27->jaw_open AU45->blink AU64->look (dynamic, not in recipes).
# Unknown words -> [] so the stage stays procedural instead of guessing
# a face. BEAT (76h, 30 speakers, measured ARKit weights per emotion)
# is the future calibration source; these hand weights are the baseline.
EXPRESSION_INTENTS = {
    "neutral": [],
    "happy": [("smile_left", 1.0), ("smile_right", 1.0),
              ("cheek_squint_left", 0.6), ("cheek_squint_right", 0.6)],
    "love": [("smile_left", 1.0), ("smile_right", 1.0),
             ("cheek_squint_left", 0.4), ("cheek_squint_right", 0.4)],
    "sad": [("frown_left", 0.8), ("frown_right", 0.8),
            ("brow_inner_up", 0.9), ("brow_down_left", 0.5),
            ("brow_down_right", 0.5)],
    "angry": [("brow_down_left", 1.0), ("brow_down_right", 1.0),
              ("eye_wide_left", 0.5), ("eye_wide_right", 0.5),
              ("eye_squint_left", 0.5), ("eye_squint_right", 0.5),
              ("nose_sneer_left", 0.5), ("nose_sneer_right", 0.5),
              ("mouth_press_left", 0.7), ("mouth_press_right", 0.7)],
    "surprised": [("jaw_open", 0.8),
                  ("brow_inner_up", 0.5),
                  ("brow_outer_up_left", 0.7),
                  ("brow_outer_up_right", 0.7),
                  ("eye_wide_left", 0.9), ("eye_wide_right", 0.9)],
    "afraid": [("brow_inner_up", 0.6), ("brow_outer_up_left", 0.6),
               ("brow_outer_up_right", 0.6), ("brow_down_left", 0.4),
               ("brow_down_right", 0.4),
               ("eye_wide_left", 1.0), ("eye_wide_right", 1.0),
               ("eye_squint_left", 0.3), ("eye_squint_right", 0.3),
               ("mouth_stretch_left", 0.6),
               ("mouth_stretch_right", 0.6),
               ("jaw_open", 0.5)],
    "disgust": [("nose_sneer_left", 0.9), ("nose_sneer_right", 0.9),
                ("eye_wide_left", 0.4), ("eye_wide_right", 0.4),
                ("mouth_lower_down_left", 0.7),
                ("mouth_lower_down_right", 0.7)],
    "contempt": [("smile_left", 0.8),
                 ("brow_down_left", 0.5),
                 ("eye_squint_left", 0.3),
                 ("cheek_squint_left", 0.4)],
    "deadpan": [],
    "annoyed": [("frown_left", 0.4), ("brow_down_left", 0.5)],
    "smirk": [("smile_left", 0.7)],
    "shout": [("jaw_open", 0.7),
              ("eye_wide_left", 0.5), ("eye_wide_right", 0.5)],
    "whisper": [],
    "grin": [("smile_left", 1.0), ("smile_right", 1.0),
             ("cheek_squint_left", 0.7), ("cheek_squint_right", 0.7)],
    "confused": [("frown_left", 0.4), ("frown_right", 0.4),
                 ("brow_inner_up", 0.4)],
}

# Same recipes as concrete ARKit morph names + weights, for renderers
# that drive GLB morph targets directly (MorphVisemePlayer-style emotion
# writers bind only the names present in the file). Derived from
# EXPRESSION_INTENTS via _INTENT_CANDIDATES: first candidate wins.
def expression_morphs(expression, intensity=1.0):
    """Stage word -> [(arkit_morph_name, weight)]. Unknown -> []."""
    try:
        w = max(0.0, min(1.0, float(intensity)))
    except Exception:
        w = 1.0
    out = []
    for intent, wt in EXPRESSION_INTENTS.get(
            str(expression or "").lower(), []):
        names = _INTENT_CANDIDATES.get(intent, [])
        if names:
            out.append((names[0], round(wt * w, 3)))
    return out


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
