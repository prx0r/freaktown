"""Stage Direction Parser — natural language → semantic movement cues.

Takes creator input like "stare at Ella" or "shrug and look away"
and resolves it to semantic actions the motion system can execute.

Reference: anime.dm — SAY HOW... interaction
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedDirection:
    """A parsed stage direction with resolved semantic actions."""
    actions: list[dict]  # [{action, emotion, intensity, duration_ms}]
    raw: str
    confidence: float


# ── Keyword → Semantic Mapping ──────────────────────────────────────

GESTURE_KEYWORDS = {
    r"\bshru?g\b": "gesture.shrug",
    r"\bpoint\b": "gesture.point",
    r"\bwave\b": "gesture.wave",
    r"\b(bow|take a bow)\b": "gesture.open_palm",
    r"\b(stop|halt|freeze)\b": "locomotion.freeze",
    r"\bnod\b": "gesture.beat",
    r"\b(clap|applaud)\b": "reaction.enjoy_laugh",
    r"\bfacepalm\b": "reaction.annoyed",
}

GAZE_KEYWORDS = {
    r"\b(look at|stare at|gaze at|watch)\b.*\bell[ae]\b": "gaze.ella",
    r"\b(look at|stare at|gaze at)\b.*\b(audience|crowd)\b": "gaze.audience",
    r"\b(look away|avert|avoid)\b": "gaze.away",
    r"\b(look down|downcast)\b": "gaze.ground",
    r"\b(look up|upward)\b": "gaze.sky",
    r"\b(stare|blank stare|dead stare|deadpan)\b": "reaction.dead_stare",
    r"\b(look left)\b": "gaze.left",
    r"\b(look right)\b": "gaze.right",
}

REACTION_KEYWORDS = {
    r"\b(confused|puzzled|bewildered)\b": "reaction.confused",
    r"\b(annoyed|irritated|frustrated)\b": "reaction.annoyed",
    r"\b(bored|unimpressed| indifferent)\b": "reaction.bored",
    r"\b(shocked|surprised|astonished)\b": "reaction.shock",
    r"\b(nervous|fidget|anxious)\b": "reaction.nervous",
    r"\b(embarrassed|ashamed|mortified)\b": "reaction.annoyed",
    r"\b(enjoy|delight|love this)\b": "reaction.enjoy_laugh",
    r"\b(double.take|look away then back)\b": "reaction.double_take",
}

LOCOMOTION_KEYWORDS = {
    r"\b(pace|walk|stroll)\b": "locomotion.pace",
    r"\b(walk away|retreat|back away)\b": "locomotion.exit",
    r"\b(enter|walk on|step up)\b": "locomotion.enter",
    r"\b(sit|sit down)\b": "pose.slump",
    r"\b(stand|stand up|straighten)\b": "pose.confident",
}

EMOTION_KEYWORDS = {
    r"\b(embarrassed|ashamed|mortified)\b": "face.annoyed",
    r"\b(angry|furious|livid)\b": "face.annoyed",
    r"\b(happy|delighted|pleased)\b": "face.smile",
    r"\b(sad|disappointed|dejected)\b": "face.frown",
    r"\b(smug|self.satisfied|proud)\b": "face.smug",
    r"\b(surprised|shocked|astonished)\b": "face.surprised",
    r"\b(disgusted|repulsed|grossed out)\b": "face.disgusted",
    r"\b(neutral|flat|expressionless)\b": "face.deadpan",
}

POSE_KEYWORDS = {
    r"\b(cross arms|arms crossed)\b": "pose.cross_arms",
    r"\b(hands on hips)\b": "pose.hands_on_hips",
    r"\b(lean forward|lean in)\b": "pose.lean_forward",
    r"\b(lean back|relax)\b": "pose.lean_back",
    r"\b(slump|defeated|droop)\b": "pose.slump",
    r"\b(confident|strong|commanding)\b": "pose.confident",
}


# ── Parser ──────────────────────────────────────────────────────────

class StageDirectionParser:
    """Parse natural language stage directions into semantic actions.

    Example inputs:
        "stare at Ella"
        "shrug and look away"
        "really emphasize this word"
        "slow head tilt then freeze"
        "Do The Nolan after this punchline"
    """

    def parse(self, text: str) -> ParsedDirection:
        """Parse a natural language direction into semantic actions."""
        text_lower = text.lower().strip()
        actions = []
        confidence = 0.0

        # Check gesture keywords
        for pattern, action in GESTURE_KEYWORDS.items():
            if re.search(pattern, text_lower):
                actions.append({"action": action, "intensity": 0.5})
                confidence += 0.3

        # Check gaze keywords
        for pattern, action in GAZE_KEYWORDS.items():
            if re.search(pattern, text_lower):
                actions.append({"action": action, "intensity": 0.6})
                confidence += 0.4

        # Check reaction keywords
        for pattern, action in REACTION_KEYWORDS.items():
            if re.search(pattern, text_lower):
                actions.append({"action": action, "intensity": 0.5})
                confidence += 0.3

        # Check locomotion keywords
        for pattern, action in LOCOMOTION_KEYWORDS.items():
            if re.search(pattern, text_lower):
                actions.append({"action": action, "intensity": 0.4})
                confidence += 0.3

        # Check emotion keywords
        for pattern, action in EMOTION_KEYWORDS.items():
            if re.search(pattern, text_lower):
                # Emotions go to face layer
                actions.append({"action": action, "emotion": action.split(".")[-1], "intensity": 0.5})
                confidence += 0.3

        # Check pose keywords
        for pattern, action in POSE_KEYWORDS.items():
            if re.search(pattern, text_lower):
                actions.append({"action": action, "intensity": 0.5})
                confidence += 0.3

        # Intensity modifiers
        intensity = 0.5
        if any(w in text_lower for w in ["really", "very", "strongly", "heavily"]):
            intensity = 0.8
        elif any(w in text_lower for w in ["slightly", "subtly", "barely", "a little"]):
            intensity = 0.2
        elif any(w in text_lower for w in ["slowly", "gentle", "soft"]):
            intensity = 0.3

        for a in actions:
            a["intensity"] = min(1.0, a["intensity"] * intensity / 0.5)

        # Duration hints
        duration_ms = 0
        if any(w in text_lower for w in ["long", "extended", "hold"]):
            duration_ms = 2000
        elif any(w in text_lower for w in ["quick", "brief", "short"]):
            duration_ms = 300

        for a in actions:
            if duration_ms:
                a["duration_ms"] = duration_ms

        # If nothing matched, use the raw text as a description
        if not actions:
            actions = [{"action": "gesture.beat", "description": text, "intensity": 0.3}]
            confidence = 0.1
        else:
            confidence = min(1.0, confidence)

        return ParsedDirection(
            actions=actions,
            raw=text,
            confidence=confidence,
        )


# Singleton
stage_direction_parser = StageDirectionParser()
