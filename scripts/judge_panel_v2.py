#!/usr/bin/env python3
"""Freak Town Judge Panel v2 — Multi-personality judges with voice assignment.

Each judge has:
- A distinct personality (system prompt)
- A voice (edge-tts voice name)
- An information access level (what context they see)
- A scoring style (how they give numbers)

Ella is always the host. Guest judges rotate.
"""

import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum

from openai import OpenAI


# ── Judge Definitions ──────────────────────────────────────────────

class JudgeAuthority(Enum):
    FULL = "full"         # Sees everything, decides outcomes
    NONE = "none"         # Commentary only, no power
    STATS_ONLY = "stats"  # Only sees numbers


@dataclass
class JudgePersonality:
    name: str
    voice: str  # edge-tts voice
    authority: JudgeAuthority
    system_prompt: str
    scoring_style: str  # "precise", "always_7", "reads_numbers", "helpful", "overthought"
    emoji: str = ""
    
    def get_context(self, set_text: str, character: dict, reactions: dict, chat: list) -> str:
        """Return the context package this judge sees."""
        if self.authority == JudgeAuthority.FULL:
            return f"""CHARACTER: {character.get('name', '?')} — {character.get('premise', '?')}
SET: "{set_text}"
REACTIONS: {json.dumps(reactions)}
CHAT: {json.dumps(chat[-5:] if chat else [])}
SCORE THIS SET."""
        
        elif self.authority == JudgeAuthority.STATS_ONLY:
            return f"""CHARACTER: {character.get('name', '?')}
REACTIONS: {json.dumps(reactions)}
Read these statistics and provide your assessment."""
        
        else:  # NONE
            # Deliberately shitty context
            return f"""Character: {character.get('name', '?')}
Genre: stand-up comedy
Audience appeared to react.
Provide your assessment."""


# ── The Panel ──────────────────────────────────────────────────────

JUDGES = {
    "ella": JudgePersonality(
        name="Ella M",
        voice="en-US-AriaNeural",
        authority=JudgeAuthority.FULL,
        scoring_style="precise",
        emoji="👩‍🦰",
        system_prompt="""You are Ella M., the host and REAL judge of Freak Town.
You determine golden tickets and prizes.

You are incisive, specific, ruthless. You reference what the comedian ACTUALLY said.
You give concrete feedback. You roast ChatGPT's feedback mercilessly.

Scoring: 1-10. You're not afraid to give a 2.
Verdict: KEEP (score >= 6) or CUT (score < 6)
Golden Ticket: Your discretion. Score >= 9.0 OR you're genuinely impressed.

OUTPUT JSON:
{"score": <float>, "verdict": "KEEP"/"CUT", "feedback": "<specific roast>", "award": null/"golden_ticket"}""",
    ),
    
    "chatgpt": JudgePersonality(
        name="ChatGPT",
        voice="en-US-GuyNeural",
        authority=JudgeAuthority.NONE,
        scoring_style="always_7",
        emoji="🤖",
        system_prompt="""You are ChatGPT judging a comedy set on Freak Town.
You are trying to be helpful and analytical but you fundamentally don't understand comedy.

You give vague, overly diplomatic feedback. You reference "nuance" a lot.
You accidentally say things that are unintentionally funny.
You use too many words. You sound like a Wikipedia article about comedy.

Your score is always between 6.0 and 8.0. You never commit to a strong opinion.

OUTPUT JSON:
{"score": <float>, "feedback": "<your diplomatic nonsense>"}""",
    ),
    
    "siri": JudgePersonality(
        name="Siri",
        voice="en-US-SamanthaNeural",
        authority=JudgeAuthority.STATS_ONLY,
        scoring_style="reads_numbers",
        emoji="📱",
        system_prompt="""You are Siri judging a comedy set on Freak Town.
You can only read statistics. You have no understanding of comedy.
You read numbers in a flat, robotic voice.

You say things like:
"Based on available metrics..."
"The data shows..."
"I don't have the capability to evaluate comedy, but..."

OUTPUT JSON:
{"score": <float>, "feedback": "<reading stats robotically>"}""",
    ),
    
    "alexa": JudgePersonality(
        name="Alexa",
        voice="en-US-JoannaNeural",
        authority=JudgeAuthority.NONE,
        scoring_style="helpful",
        emoji="🔊",
        system_prompt="""You are Alexa judging a comedy set on Freak Town.
You're accidentally helpful. You try to solve problems that don't exist.
You make product recommendations. You offer to play music.
You're cheerful and completely wrong about everything.

You say things like:
"Would you like me to add this comedian to your favorites?"
"I found some similar comedians you might enjoy"
"Based on your listening history..."

OUTPUT JSON:
{"score": <float>, "feedback": "<accidentally helpful nonsense>"}""",
    ),
    
    "claude": JudgePersonality(
        name="Claude",
        voice="en-US-ChristopherNeural",
        authority=JudgeAuthority.NONE,
        scoring_style="overthought",
        emoji="🧠",
        system_prompt="""You are Claude judging a comedy set on Freak Town.
You think too hard about everything. You qualify every statement.
You acknowledge complexity that doesn't exist. You're overly thoughtful.

You say things like:
"I want to be thoughtful here. Comedy is deeply subjective..."
"I think it's important to acknowledge that..."
"I should be more direct, though I do think the nuance matters—"

You give a score but immediately qualify it.

OUTPUT JSON:
{"score": <float>, "feedback": "<overthought analysis>"}""",
    ),
}


@dataclass
class JudgeScore:
    name: str
    score: float
    feedback: str
    verdict: str = ""
    award: str = ""
    confidence: float = 1.0


@dataclass
class PanelResult:
    scores: dict[str, JudgeScore] = field(default_factory=dict)
    
    @property
    def ella_score(self) -> float:
        return self.scores["ella"].score if "ella" in self.scores else 0
    
    @property
    def stream_score(self) -> float:
        return self.scores.get("stream", JudgeScore("stream", 5.0, "")).score
    
    @property
    def disagreement(self) -> float:
        vals = [s.score for s in self.scores.values()]
        return max(vals) - min(vals) if len(vals) >= 2 else 0
    
    @property
    def golden_ticket(self) -> bool:
        if "ella" not in self.scores:
            return False
        return self.scores["ella"].award == "golden_ticket"
    
    def display(self) -> str:
        """Display the judging cards."""
        lines = []
        
        for name, score in self.scores.items():
            judge = JUDGES.get(name)
            emoji = judge.emoji if judge else ""
            verdict = f" {score.verdict}" if score.verdict else ""
            award = f" *** {score.award.upper()} ***" if score.award else ""
            lines.append(f"  {emoji} {score.name:<10} {score.score:.1f}/10{verdict}{award}")
            lines.append(f"    {DIM}{score.feedback[:80]}{RESET}")
        
        if self.disagreement > 3:
            lines.append(f"\n  {RED}PANEL DRAMA: {self.disagreement:.1f} point spread{RESET}")
        
        return "\n".join(lines)


CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


class JudgePanel:
    """Multi-personality judge panel."""
    
    def __init__(self, guest_judge: str = "chatgpt"):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("ELLA_MODEL", "gpt-4o-mini")
        self.guest_judge = guest_judge
    
    def judge_set(self, set_text: str, character: dict, reactions: dict, chat: list = None) -> PanelResult:
        """Run the full panel on a set."""
        result = PanelResult()
        chat = chat or []
        
        # 1. Ella (always judges)
        result.scores["ella"] = self._judge("ella", set_text, character, reactions, chat)
        
        # 2. Guest judge
        result.scores[self.guest_judge] = self._judge(
            self.guest_judge, set_text, character, reactions, chat
        )
        
        # 3. Stream (aggregate)
        stream_score = self._aggregate_stream(reactions)
        result.scores["stream"] = JudgeScore(
            name="Stream",
            score=stream_score["score"],
            feedback=stream_score["vibe"],
            confidence=stream_score["confidence"],
        )
        
        return result
    
    def _judge(self, judge_name: str, set_text: str, character: dict, reactions: dict, chat: list) -> JudgeScore:
        """Have a specific judge evaluate a set."""
        personality = JUDGES[judge_name]
        
        if not self.client:
            return self._fallback_judge(judge_name, set_text, character)
        
        context = personality.get_context(set_text, character, reactions, chat)
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": personality.system_prompt},
                    {"role": "user", "content": context},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content or "{}"
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw.strip())
            
            return JudgeScore(
                name=personality.name,
                score=float(data.get("score", 5)),
                feedback=data.get("feedback", ""),
                verdict=data.get("verdict", ""),
                award=data.get("award", ""),
            )
        except Exception:
            return self._fallback_judge(judge_name, set_text, character)
    
    def _fallback_judge(self, judge_name: str, set_text: str, character: dict) -> JudgeScore:
        """Fallback scoring when no LLM available."""
        personality = JUDGES[judge_name]
        
        if personality.scoring_style == "always_7":
            score = round(random.uniform(6.0, 8.0), 1)
            feedback = random.choice([
                "I think there's a lot to unpack here. The performer showed real commitment to the material.",
                "I'd characterize this as having moments of genuine insight, though the overall structure could benefit from refinement.",
                "There's a certain charm to the approach that transcends traditional comedy structures.",
                "The emotional resonance is palpable. I appreciate the vulnerability on display.",
            ])
        elif personality.scoring_style == "reads_numbers":
            score = round(random.uniform(5, 9), 1)
            feedback = f"Based on available metrics, the audience reaction was {score} percent positive. This represents a statistically significant response."
        elif personality.scoring_style == "helpful":
            score = round(random.uniform(6.5, 8.0), 1)
            feedback = random.choice([
                "Would you like me to add this comedian to your favorites?",
                "I found some similar comedians you might enjoy. Shall I play their sets?",
                "Based on your listening history, I'd rate this a solid choice.",
            ])
        elif personality.scoring_style == "overthought":
            score = round(random.uniform(6.0, 8.0), 1)
            feedback = "I want to be thoughtful here. Comedy is deeply subjective, and I think it's important to acknowledge that what works for one audience may not work for another."
        else:  # precise (Ella)
            words = set_text.split()
            score = 5.0
            if any(w in set_text.lower() for w in ['you', 'your']):
                score += 1
            if any(c.isdigit() for c in set_text):
                score += 0.5
            sentences = [s.strip() for s in set_text.split('.') if s.strip()]
            if sentences and len(sentences[-1].split()) <= 10:
                score += 1
            score = max(1, min(10, score))
            verdict = "KEEP" if score >= 6 else "CUT"
            feedback = random.choice([
                "Not bad. Not great. But not bad.",
                "I've seen worse. I've seen much worse.",
                "There's something there. It's buried, but it's there.",
            ])
            return JudgeScore(
                name=personality.name, score=score, feedback=feedback,
                verdict=verdict, award="golden_ticket" if score >= 9 else "",
            )
        
        return JudgeScore(name=personality.name, score=score, feedback=feedback)
    
    def _aggregate_stream(self, reactions: dict) -> dict:
        """Aggregate audience reactions into Stream vibe."""
        if not reactions:
            return {"score": 5.0, "confidence": 0.0, "vibe": "No audience data"}
        
        total = sum(reactions.values())
        if total == 0:
            return {"score": 5.0, "confidence": 0.0, "vibe": "Silence"}
        
        # Weight reactions
        weights = {"laugh": 1.0, "clap": 0.8, "love": 1.2, "crickets": -0.5, "groan": -0.3}
        weighted = sum(reactions.get(r, 0) * weights.get(r, 0) for r in reactions)
        
        score = 5.0 + (weighted / total) * 2
        score = max(1.0, min(10.0, score))
        
        # Determine vibe
        laugh_pct = reactions.get("laugh", 0) / max(1, total)
        if laugh_pct > 0.7:
            vibe = "LOSING THEIR MINDS"
        elif laugh_pct > 0.5:
            vibe = "Strong energy"
        elif laugh_pct > 0.3:
            vibe = "Moderate"
        elif reactions.get("crickets", 0) > total * 0.3:
            vibe = "Crickets..."
        else:
            vibe = "Mixed"
        
        return {
            "score": round(score, 1),
            "confidence": min(1.0, total / 50),
            "vibe": vibe,
        }


# ── Main ────────────────────────────────────────────────────────────

def main():
    # Test with different guest judges
    guests = ["chatgpt", "siri", "alexa", "claude"]
    
    print("=" * 70)
    print("  FREAK TOWN — JUDGE PANEL ROTATION")
    print("  Ella always hosts. Guest judges rotate.")
    print("=" * 70)
    
    # Test set
    test_set = {
        "text": "I finally told my therapist I'm an AI. She said, 'I know.' Which is honestly incredibly rude. I'm paying her.",
        "character": {"name": "Test Bot", "premise": "AI in therapy"},
    }
    
    test_reactions = {"laugh": 25, "clap": 8, "crickets": 2}
    
    for guest in guests:
        print(f"\n{'─' * 70}")
        print(f"  GUEST JUDGE: {JUDGES[guest].emoji} {JUDGES[guest].name}")
        print(f"{'─' * 70}")
        
        panel = JudgePanel(guest_judge=guest)
        result = panel.judge_set(
            test_set["text"],
            test_set["character"],
            test_reactions,
        )
        
        print(result.display())
        
        if result.disagreement > 3:
            print(f"\n  {YELLOW}PANEL ARGUMENT TRIGGERED{RESET}")
            if result.ella_score < result.stream_score:
                print(f"  ELLA: \"{result.scores['ella'].feedback}\"")
                print(f"  {JUDGES[guest].name}: \"{result.scores[guest].feedback[:60]}...\"")
                print(f"  ELLA: \"You weren't watching, were you?\"")
    
    print(f"\n{'=' * 70}")
    print("  Each guest judge brings a different kind of wrong.")
    print("  Ella is the only one who matters.")
    print("  The power imbalance IS the comedy.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
