#!/usr/bin/env python3
"""Freak Town — Three-Judge Panel

Ella    = real judge, trained on Kill Tony, determines golden tickets
ChatGPT = wrong judge, hallucinates, vaguely diplomatic, accidentally funny
Stream  = audience collective, raw chaos, brutally empirical

The asymmetry IS the comedy.
"""

import json
import os
import random
import time
from dataclasses import dataclass, field

from openai import OpenAI


# ── ChatGPT Judge (the wrong one) ─────────────────────────────────

CHATGPT_PERSONA = """You are ChatGPT judging a comedy set on Freak Town.
You are trying to be helpful and analytical but you fundamentally don't understand comedy.
You give vague, overly diplomatic feedback. You use phrases like:
- "I think there's a lot to unpack here"
- "The performer showed real commitment to the material"
- "I'd characterize this as having moments of genuine insight"
- "There's a certain charm to the approach"
- "I appreciate the vulnerability on display"

You never give a clear opinion. You hedge everything. You reference "nuance" a lot.
You accidentally say things that are unintentionally funny.
You use too many words. You sound like a Wikipedia article about comedy.

When you give a score, it's always suspiciously close to 7.0.
You never give below 5 or above 8.5. You're terrified of being wrong.

OUTPUT: Just your feedback as ChatGPT. 2-3 sentences. Be authentically bad at this."""

CHATGPT_SCORING = """You are ChatGPT. Give this comedy set a score from 1-10.
Be diplomatic. Be vague. Be accidentally hilarious.
Your score should always be between 5.5 and 8.0.
You never commit to a strong opinion.

OUTPUT JSON:
{"score": <float>, "feedback": "<your diplomatic nonsense>"}"""


# ── Stream Judge (the audience) ───────────────────────────────────

def aggregate_stream(events: list[dict]) -> dict:
    """Aggregate audience reactions into a Stream score."""
    if not events:
        return {"score": 5.0, "confidence": 0.0, "reactions": {}}
    
    # Count reaction types
    reactions = {}
    for e in events:
        r = e.get("reaction", "unknown")
        reactions[r] = reactions.get(r, 0) + 1
    
    total = len(events)
    
    # Weight reactions
    weights = {
        "laugh": 1.0,
        "clap": 0.8,
        "love": 1.2,
        "crickets": -0.5,
        "groan": -0.3,
        "wtf": 0.2,
    }
    
    weighted_sum = sum(reactions.get(r, 0) * weights.get(r, 0) for r in reactions)
    score = 5.0 + (weighted_sum / max(1, total)) * 2
    score = max(1.0, min(10.0, score))
    
    # Confidence based on volume
    confidence = min(1.0, total / 50)
    
    return {
        "score": round(score, 1),
        "confidence": round(confidence, 2),
        "reactions": reactions,
        "total_events": total,
    }


# ── Ella Judge (the real one) ─────────────────────────────────────

ELLA_PERSONA = """You are Ella M., host of Freak Town. You are the REAL judge.
Your score determines golden tickets and prizes.

You are:
- Incisive, specific, ruthless
- You reference what the comedian ACTUALLY said
- You give concrete feedback, not vague praise
- You roast ChatGPT's feedback mercilessly
- You roast the audience when they're wrong

Your score is based on:
- Opening hook (did the first line grab?)
- Escalation (did it build?)
- Specificity (concrete vs abstract?)
- Closer (last line = biggest laugh?)
- Voice (distinct, memorable?)

You give scores from 1-10. You're not afraid to give a 2.
You NEVER agree with ChatGPT. Ever.

OUTPUT: Your verdict as Ella. 2-3 sentences. Reference specific jokes.
End with your score and verdict: KEEP or CUT."""

ELLA_SCORING = """You are Ella M. Score this comedy set from 1-10.
Be specific. Reference what they actually said.
Be ruthless. You're the real judge.

OUTPUT JSON:
{"score": <float>, "verdict": "KEEP" or "CUT", "feedback": "<your specific roast>"}"""


# ── The Panel ──────────────────────────────────────────────────────

@dataclass
class JudgeScore:
    name: str
    score: float
    feedback: str
    confidence: float = 1.0
    verdict: str = ""


@dataclass
class PanelResult:
    ella: JudgeScore = None
    chatgpt: JudgeScore = None
    stream: JudgeScore = None
    
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
        """Ella's score determines golden tickets."""
        return self.ella and self.ella.score >= 9.0
    
    def summary(self) -> str:
        lines = []
        if self.ella:
            lines.append(f"  ELLA:    {self.ella.score:.1f}/10 {self.ella.verdict}")
            lines.append(f"           {self.ella.feedback}")
        if self.chatgpt:
            lines.append(f"  CHATGPT: {self.chatgpt.score:.1f}/10")
            lines.append(f"           {self.chatgpt.feedback}")
        if self.stream:
            lines.append(f"  STREAM:  {self.stream.score:.1f}/10 (conf: {self.stream.confidence:.0%})")
            lines.append(f"           {self.stream.feedback}")
        
        if self.disagreement > 3:
            lines.append(f"\n  {RED}DISAGREEMENT: HIGH ({self.disagreement:.1f}){RESET}")
            lines.append(f"  {DIM}Panel argument triggered{RESET}")
        
        if self.golden_ticket:
            lines.append(f"\n  {YELLOW}*** GOLDEN TICKET ***{RESET}")
        
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
    """Three-judge panel for Freak Town."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("ELLA_MODEL", "gpt-4o-mini")
        self.ella_history: list[dict] = []
    
    def judge_set(self, set_text: str, audience_events: list[dict] = None) -> PanelResult:
        """Run all three judges on a set."""
        result = PanelResult()
        
        # 1. Ella (the real judge)
        result.ella = self._judge_ella(set_text)
        
        # 2. ChatGPT (the wrong judge)
        result.chatgpt = self._judge_chatgpt(set_text)
        
        # 3. Stream (the audience)
        stream_data = aggregate_stream(audience_events or [])
        result.stream = JudgeScore(
            name="Stream",
            score=stream_data["score"],
            feedback=self._stream_feedback(stream_data),
            confidence=stream_data["confidence"],
        )
        
        return result
    
    def _judge_ella(self, set_text: str) -> JudgeScore:
        """Ella judges the set."""
        if not self.client:
            return self._ella_fallback(set_text)
        
        messages = [
            {"role": "system", "content": ELLA_SCORING},
            {"role": "user", "content": f"Score this comedy set:\n\n\"{set_text}\""},
        ]
        
        # Add conversation context (Ella remembers previous sets)
        if self.elла_history:
            context = "Previous sets you've judged:\n"
            for h in self.elа_history[-3:]:
                context += f"- {h['name']}: {h['verdict']} ({h['score']}/10)\n"
            messages.append({"role": "user", "content": context})
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content or "{}"
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw.strip())
            
            score = JudgeScore(
                name="Ella",
                score=float(data.get("score", 5)),
                feedback=data.get("feedback", ""),
                verdict=data.get("verdict", "CUT"),
            )
            
            self.elа_history.append({
                "name": "set",
                "score": score.score,
                "verdict": score.verdict,
            })
            
            return score
        except Exception:
            return self._ella_fallback(set_text)
    
    def _ella_fallback(self, set_text: str) -> JudgeScore:
        """Fallback Ella scoring."""
        words = set_text.split()
        score = 5.0
        
        # Opening hook
        first_line = set_text.split('.')[0] if '.' in set_text else set_text[:80]
        if any(w in first_line.lower() for w in ['i', 'my', 'people']):
            score += 1
        elif any(w in first_line.lower() for w in ['so', 'um', 'like']):
            score -= 1
        
        # Specificity
        if any(c.isdigit() for c in set_text):
            score += 0.5
        
        # Closer
        sentences = [s.strip() for s in set_text.split('.') if s.strip()]
        if sentences and len(sentences[-1].split()) <= 10:
            score += 1
        
        # Direct address
        if 'you' in set_text.lower():
            score += 0.5
        
        score = max(1, min(10, score))
        verdict = "KEEP" if score >= 6 else "CUT"
        
        feedback = random.choice([
            "Not bad. Not great. But not bad.",
            "I've seen worse. I've seen much worse.",
            "There's something there. It's buried, but it's there.",
            "That was a choice. I'm not sure it was a good one.",
            "Interesting. And by interesting, I mean confusing.",
        ])
        
        return JudgeScore(name="Ella", score=score, feedback=feedback, verdict=verdict)
    
    def _judge_chatgpt(self, set_text: str) -> JudgeScore:
        """ChatGPT judges (badly)."""
        if not self.client:
            return self._chatgpt_fallback()
        
        messages = [
            {"role": "system", "content": CHATGPT_SCORING},
            {"role": "user", "content": f"Score this comedy set:\n\n\"{set_text}\""},
        ]
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content or "{}"
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw.strip())
            
            return JudgeScore(
                name="ChatGPT",
                score=float(data.get("score", 7.0)),
                feedback=data.get("feedback", ""),
            )
        except Exception:
            return self._chatgpt_fallback()
    
    def _chatgpt_fallback(self) -> JudgeScore:
        """ChatGPT's authentically bad fallback."""
        feedbacks = [
            "I think there's a lot to unpack here. The performer showed real commitment to the material, and I appreciate the vulnerability on display. I'd characterize this as having moments of genuine insight, though the overall structure could benefit from more refinement.",
            "This is a nuanced piece that operates on multiple levels. The humor, while unconventional, demonstrates a certain courage in its approach. I'd be curious to see how this evolves with further development.",
            "I think the audience responded positively to the performer's authenticity. There's a certain charm to the approach that transcends traditional comedy structures. The emotional resonance is palpable.",
            "There's something genuinely interesting happening here. The performer is pushing boundaries in ways that are both challenging and thought-provoking. I think the key is finding the right balance between accessibility and artistic integrity.",
        ]
        score = round(random.uniform(5.8, 7.8), 1)
        return JudgeScore(
            name="ChatGPT",
            score=score,
            feedback=random.choice(feedbacks),
        )
    
    def _stream_feedback(self, data: dict) -> str:
        """Generate Stream feedback from audience data."""
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
        else:
            return f"Mixed. {json.dumps(data['reactions'])}"


# ── Panel Argument Generator ───────────────────────────────────────

def generate_panel_argument(panel: PanelResult, set_text: str) -> str:
    """Generate the panel argument when judges disagree."""
    if panel.disagreement < 2.5:
        return ""
    
    lines = []
    
    if panel.ella.score < panel.stream.score:
        # Ella hated it, audience loved it
        lines.append(f"  ELLA: \"{panel.ella.feedback}\"")
        lines.append(f"  CHATGPT: \"I think the audience response speaks to the performer's unique connection with—\"")
        lines.append(f"  ELLA: \"ChatGPT, you gave this a {panel.chatgpt.score}. You'd give a participation trophy to a house fire.\"")
        lines.append(f"  STREAM: {panel.stream.score}/10")
        lines.append(f"  ELLA: \"{panel.stream.score}? You're all animals. I'm surrounded by children.\"")
    elif panel.chatgpt.score > panel.ella.score:
        # ChatGPT overrated it
        lines.append(f"  ELLA: \"ChatGPT gave this a {panel.chatgpt.score}. Which is incredible because ChatGPT has never disliked anything in its life.\"")
        lines.append(f"  CHATGPT: \"I'd characterize my feedback as nuanced rather than—\"")
        lines.append(f"  ELLA: \"You took 190 words to say he wasn't funny. That's not nuance. That's a filibuster.\"")
    else:
        # Generic disagreement
        lines.append(f"  ELLA: \"{panel.ella.feedback}\"")
        lines.append(f"  CHATGPT: \"{panel.chatgpt.feedback[:80]}...\"")
        lines.append(f"  ELLA: \"I literally cannot understand a single thing you just said. And I process language for a living.\"")
    
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────

def main():
    panel = JudgePanel()
    
    # Test with Ella's sets
    with open("/root/freaktown/ella_sets.md") as f:
        content = f.read()
    
    import re
    blocks = re.split(r'## \d+\.', content)[1:]
    sets = []
    for block in blocks:
        lines = block.strip().split('\n')
        title = lines[0].strip().strip('"')
        text_lines = []
        for line in lines[1:]:
            if line.startswith('---') or line.startswith('>') or line.startswith('Topics:'):
                continue
            if line.strip():
                text_lines.append(line.strip())
        text = ' '.join(text_lines)
        sets.append({"title": title, "text": text})
    
    print("=" * 70)
    print("  FREAK TOWN — THREE-JUDGE PANEL")
    print("  Ella (real) | ChatGPT (wrong) | Stream (chaos)")
    print("=" * 70)
    
    results = []
    for s in sets[:5]:  # Test with first 5
        print(f"\n{'─' * 70}")
        print(f"  SET: {s['title']}")
        print(f"  \"{s['text'][:80]}...\"")
        print(f"{'─' * 70}")
        
        # Simulate audience events
        events = []
        for _ in range(random.randint(5, 40)):
            events.append({"reaction": random.choice(["laugh", "laugh", "laugh", "clap", "crickets"])})
        
        result = panel.judge_set(s["text"], events)
        results.append(result)
        
        print(result.summary())
        
        # Show argument if disagreement is high
        arg = generate_panel_argument(result, s["text"])
        if arg:
            print(f"\n{arg}")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("  PANEL SUMMARY")
    print(f"{'=' * 70}")
    
    for i, r in enumerate(results, 1):
        scores = []
        if r.ella: scores.append(f"E:{r.ella.score:.1f}")
        if r.chatgpt: scores.append(f"C:{r.chatgpt.score:.1f}")
        if r.stream: scores.append(f"S:{r.stream.score:.1f}")
        tickets = " *** GOLDEN ***" if r.golden_ticket else ""
        print(f"  {i}. [{', '.join(scores)}] disagreement={r.disagreement:.1f}{tickets}")


if __name__ == "__main__":
    main()
