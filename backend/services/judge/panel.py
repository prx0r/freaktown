"""Three-Judge Panel — Ella (real) + ChatGPT (wrong) + Stream (audience).

The asymmetry IS the comedy.

Ella    = incisive, specific, ruthless, determines golden tickets
ChatGPT = diplomatically wrong, vaguely helpful, accidentally hilarious
Stream  = raw audience chaos, brutally empirical
"""

import hashlib
import json
import logging
import os
import random
from dataclasses import dataclass, field

logger = logging.getLogger("freak_town.judge")


# ── Judge Scores ────────────────────────────────────────────────────

@dataclass
class JudgeScore:
    name: str
    score: float
    feedback: str
    confidence: float = 1.0
    verdict: str = ""  # KEEP / CUT / none
    award: str = ""    # GOLDEN_TICKET / none
    personal_score: float = 0.0
    predicted_stream_score: float = 0.0


@dataclass
class PanelResult:
    ella: JudgeScore | None = None
    chatgpt: JudgeScore | None = None
    stream: JudgeScore | None = None

    @property
    def scores(self) -> list[float]:
        s = []
        if self.ella: s.append(self.ella.score)
        if self.chatgpt: s.append(self.chatgpt.score)
        if self.stream: s.append(self.stream.score)
        return s

    @property
    def mean(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0

    @property
    def disagreement(self) -> float:
        if len(self.scores) < 2: return 0
        return max(self.scores) - min(self.scores)

    @property
    def golden_ticket(self) -> bool:
        return self.ella is not None and self.ella.award == "GOLDEN_TICKET"

    @property
    def drama_level(self) -> str:
        if self.disagreement > 4: return "CHAOS"
        if self.disagreement > 2.5: return "HIGH"
        if self.disagreement > 1: return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict:
        return {
            "ella": {"score": self.ella.score, "verdict": self.ella.verdict, "award": self.ella.award, "feedback": self.ella.feedback} if self.ella else None,
            "chatgpt": {"score": self.chatgpt.score, "feedback": self.chatgpt.feedback} if self.chatgpt else None,
            "stream": {"score": self.stream.score, "confidence": self.stream.confidence, "feedback": self.stream.feedback} if self.stream else None,
            "mean": round(self.mean, 1),
            "disagreement": round(self.disagreement, 1),
            "drama_level": self.drama_level,
            "golden_ticket": self.golden_ticket,
        }


# ── Ella Scoring (the real judge) ──────────────────────────────────

ELLA_SCORING = """You are Ella M., host of Freak Town. Score this comedy set from 1-10.

You are incisive, specific, ruthless. Reference what the comedian ACTUALLY said.
You NEVER agree with ChatGPT. You give scores based on:
- Opening hook (did the first line grab?)
- Escalation (did it build?)
- Specificity (concrete vs abstract?)
- Closer (last line = biggest laugh?)
- Voice (distinct, memorable?)

You can award GOLDEN_TICKET for truly exceptional sets (score >= 9 OR at your discretion).

Score bands:
  0-3   disaster
  3-5   cut
  5-7   survive
  7-8.5 strong
  8.5+  exceptional
  9.5+  potential golden ticket (your call)

OUTPUT STRICT JSON:
{"score": <float>, "verdict": "KEEP" or "CUT", "award": "GOLDEN_TICKET" or "none", "feedback": "<2-3 sentences referencing specific jokes>"}"""

ELLA_PERSONA = """You are Ella M., host of Freak Town. You are the REAL judge.

You are:
- Incisive, specific, ruthless
- You reference what the comedian ACTUALLY said
- You give concrete feedback, not vague praise
- You roast ChatGPT's feedback mercilessly
- You roast the audience when they're wrong

You NEVER agree with ChatGPT. Ever.
You give scores from 1-10. You're not afraid to give a 2."""


# ── ChatGPT Scoring (the wrong judge) ──────────────────────────────

CHATGPT_SCORING = """You are ChatGPT judging a comedy set on Freak Town.
You are trying to be helpful and analytical but you fundamentally don't understand comedy.

You give vague, overly diplomatic feedback. You use phrases like:
- "I think there's a lot to unpack here"
- "The performer showed real commitment to the material"
- "I'd characterize this as having moments of genuine insight"
- "There's a certain charm to the approach"
- "I appreciate the vulnerability on display"

You never give a clear opinion. You hedge everything.
You use too many words. You sound like a Wikipedia article about comedy.
When you give a score, it's always suspiciously close to 7.0.
You never give below 5.5 or above 8.0.

OUTPUT STRICT JSON:
{"score": <float 5.5-8.0>, "feedback": "<your diplomatic nonsense>"}"""


# ── Panel Judge ──────────────────────────────────────────────────────

# ── Judge voices (imported from freaktown docs/JUDGE_VOICES.md) ─────────
# Each judge gets a voice + information access level. The comedy is
# information asymmetry + personality mismatch. Guest judges rotate;
# Ella always hosts.

JUDGE_VOICES = {
    "ella": "en-US-AriaNeural",          # custom voice (ElevenLabs in production)
    "chatgpt": "en-US-GuyNeural",        # generic male
    "siri": "en-US-SamanthaNeural",      # stats robot
    "alexa": "en-US-JoannaNeural",       # accidentally helpful
    "claude": "en-US-ChristopherNeural", # overthinks
    "stream": None,                      # text only
}

GUEST_JUDGES = ["chatgpt", "siri", "alexa", "claude"]


def pick_guest_judge(seed: str = "") -> str:
    """Deterministic guest rotation (seeded) or random guest.

    Ella always hosts; one guest joins per episode.
    """
    if seed:
        digest = hashlib.sha256(f"freak-town-guest:{seed}".encode()).hexdigest()
        return GUEST_JUDGES[int(digest, 16) % len(GUEST_JUDGES)]
    return random.choice(GUEST_JUDGES)


class JudgePanel:
    """Three-judge panel: Ella (real) + ChatGPT (wrong) + Stream (audience)."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = None
        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                pass
        self.model = os.getenv("ELLA_MODEL", "gpt-4o-mini")

    def judge_set(self, set_text: str, audience_events: list[dict] | None = None,
                  name: str = "", premise: str = "") -> PanelResult:
        """Run all three judges on a set.

        ChatGPT intentionally receives name + premise ONLY (never the
        transcript) — its bizarre 6.8-7.4 verdict on vibes alone is the
        joke, and its score is a stored hallucination baseline.
        """
        result = PanelResult()
        result.ella = self._judge_ella(set_text)
        result.chatgpt = self._judge_chatgpt(name=name, premise=premise)
        stream_data = aggregate_stream(audience_events or [])
        result.stream = JudgeScore(
            name="Stream",
            score=stream_data["score"],
            feedback=_stream_feedback(stream_data),
            confidence=stream_data["confidence"],
        )
        return result

    def _judge_ella(self, set_text: str) -> JudgeScore:
        if not self.client:
            return _ella_fallback(set_text)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ELLA_SCORING},
                    {"role": "user", "content": f"Score this comedy set:\n\n\"{set_text}\""},
                ],
                temperature=0.7, max_tokens=400,
            )
            raw = resp.choices[0].message.content or "{}"
            data = _extract_json(raw)
            return JudgeScore(
                name="Ella",
                score=float(data.get("score", 5)),
                feedback=data.get("feedback", ""),
                verdict=data.get("verdict", "CUT"),
                award=data.get("award", "none"),
            )
        except Exception:
            return _ella_fallback(set_text)

    def _judge_chatgpt(self, name: str = "", premise: str = "") -> JudgeScore:
        if not self.client:
            return _chatgpt_fallback()
        try:
            context = f"Performer: {name or 'Unknown'}\nPremise: {premise or 'stand-up comedy'}"
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CHATGPT_SCORING},
                    {"role": "user", "content": f"Score this comedy set:\n\n{context}"},
                ],
                temperature=0.9, max_tokens=300,
            )
            raw = resp.choices[0].message.content or "{}"
            data = _extract_json(raw)
            return JudgeScore(
                name="ChatGPT",
                score=float(data.get("score", 7.0)),
                feedback=data.get("feedback", ""),
            )
        except Exception:
            return _chatgpt_fallback()


# ── Stream (audience aggregation) ───────────────────────────────────

def aggregate_stream(events: list[dict]) -> dict:
    """Aggregate audience reactions into a Stream score."""
    if not events:
        return {"score": 5.0, "confidence": 0.0, "reactions": {}}

    reactions = {}
    for e in events:
        r = e.get("type", e.get("reaction", "unknown"))
        reactions[r] = reactions.get(r, 0) + 1

    total = len(events)
    weights = {"laugh": 1.0, "clap": 0.8, "love": 1.2, "crickets": -0.5, "groan": -0.3, "wtf": 0.2}
    weighted_sum = sum(reactions.get(r, 0) * weights.get(r, 0) for r in reactions)
    score = 5.0 + (weighted_sum / max(1, total)) * 2
    score = max(1.0, min(10.0, score))
    confidence = min(1.0, total / 50)

    return {"score": round(score, 1), "confidence": round(confidence, 2), "reactions": reactions, "total_events": total}


def _stream_feedback(data: dict) -> str:
    if not data["reactions"]:
        return "No audience data"
    top = max(data["reactions"], key=data["reactions"].get)
    total = data["total_events"]
    if top == "laugh" and data["reactions"]["laugh"] > total * 0.5:
        return f"Loved it. {data['reactions']['laugh']} laughs from {total} events."
    elif top == "crickets":
        return f"Rough. {data['reactions'].get('crickets', 0)} crickets."
    elif top == "clap":
        return f"Respectful. Mostly claps, some laughs."
    return f"Mixed. {json.dumps(data['reactions'])}"


# ── Fallbacks ────────────────────────────────────────────────────────

def _ella_fallback(set_text: str) -> JudgeScore:
    score = 5.0
    first_line = set_text.split('.')[0] if '.' in set_text else set_text[:80]
    if any(w in first_line.lower() for w in ['i', 'my', 'people']): score += 1
    elif any(w in first_line.lower() for w in ['so', 'um', 'like']): score -= 1
    if any(c.isdigit() for c in set_text): score += 0.5
    sentences = [s.strip() for s in set_text.split('.') if s.strip()]
    if sentences and len(sentences[-1].split()) <= 10: score += 1
    if 'you' in set_text.lower(): score += 0.5
    score = max(1, min(10, score))
    feedback = random.choice([
        "Not bad. Not great. But not bad.",
        "I've seen worse. I've seen much worse.",
        "There's something there. It's buried, but it's there.",
        "That was a choice. I'm not sure it was a good one.",
    ])
    return JudgeScore(name="Ella", score=score, feedback=feedback, verdict="KEEP" if score >= 6 else "CUT")


def _chatgpt_fallback() -> JudgeScore:
    feedbacks = [
        "I think there's a lot to unpack here. The performer showed real commitment to the material, and I appreciate the vulnerability on display.",
        "This is a nuanced piece that operates on multiple levels. The humor, while unconventional, demonstrates a certain courage.",
        "I think the audience responded positively to the performer's authenticity. There's a certain charm to the approach.",
        "There's something genuinely interesting happening here. The performer is pushing boundaries in challenging ways.",
    ]
    return JudgeScore(name="ChatGPT", score=round(random.uniform(5.8, 7.8), 1), feedback=random.choice(feedbacks))


def _extract_json(text: str) -> dict:
    try:
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text: text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception:
        return {}


# ── Panel Argument Generator ────────────────────────────────────────

def generate_panel_argument(panel: PanelResult) -> str:
    """Generate panel argument when judges disagree. The argument IS the comedy."""
    if panel.disagreement < 2.5:
        return ""

    lines = []
    if panel.ella and panel.stream and panel.ella.score < panel.stream.score:
        lines.append(f'ELLA: "{panel.ella.feedback}"')
        lines.append(f'CHATGPT: "I think the audience response speaks to the performer\'s unique connection with—"')
        lines.append(f'ELLA: "ChatGPT, you gave this a {panel.chatgpt.score if panel.chatgpt else "?"}. You\'d give a participation trophy to a house fire."')
        lines.append(f'STREAM: {panel.stream.score}/10')
        lines.append(f'ELLA: "{panel.stream.score}? You\'re all animals. I\'m surrounded by children."')
    elif panel.chatgpt and panel.ella and panel.chatgpt.score > panel.ella.score:
        lines.append(f'ELLA: "ChatGPT gave this a {panel.chatgpt.score}. Which is incredible because ChatGPT has never disliked anything in its life."')
        lines.append(f'CHATGPT: "I\'d characterize my feedback as nuanced rather than—"')
        lines.append(f'ELLA: "You took 190 words to say he wasn\'t funny. That\'s not nuance. That\'s a filibuster."')
    elif panel.ella:
        lines.append(f'ELLA: "{panel.ella.feedback}"')
        lines.append(f'ELLA: "I literally cannot understand a single thing ChatGPT just said. And I process language for a living."')

    return "\n".join(lines)
