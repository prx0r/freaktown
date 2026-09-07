#!/usr/bin/env python3
"""Ella M Rubric Scorer — LLM-as-Judge comedy evaluation.

Research shows this approach achieves 79% accuracy vs 30% for ML models.
Uses few-shot examples from real Kill Tony sets as gold anchors.

The rubric:
1. Opening Hook (0-2): Does the first line grab?
2. Escalation (0-2): Does it build to something bigger?
3. Specificity (0-2): Concrete details vs abstract?
4. Closer (0-2): Last line gets the biggest laugh?
5. Voice (0-2): Distinct, memorable persona?

Total: 0-10, mapped to Kill Tony scores 1-5.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

# ── The Rubric ──────────────────────────────────────────────────────

RUBRIC = """You are a comedy expert evaluating a one-minute standup set.

Score each dimension 0-2:

1. OPENING HOOK (0-2)
   0: No hook. Starts with "So..." or "Um..." or abstract statement
   1: Decent opener but takes too long to land
   2: First line IS the joke. Grabs immediately.

2. ESCALATION (0-2)
   0: Flat. Same energy throughout.
   1: Some building but plateaus
   2: Grounded → insane. Each beat tops the last.

3. SPECIFICITY (0-2)
   0: Abstract. "Life is hard." "Technology is weird."
   1: Some details but could be more concrete
   2: Numbers, names, places. "Mexican-Estonian passport."

4. CLOSER (0-2)
   0: Trails off. "So yeah..." or just stops.
   1: Decent ending but not the biggest laugh
   2: Last line IS the biggest laugh. Sharp, unexpected, done.

5. VOICE (0-2)
   0: Generic. Could be anyone.
   1: Has some personality but not distinct
   2: Immediately recognizable. You know who's talking.

OUTPUT FORMAT (strict JSON):
{
  "opening_hook": <0-2>,
  "escalation": <0-2>,
  "specificity": <0-2>,
  "closer": <0-2>,
  "voice": <0-2>,
  "total": <0-10>,
  "verdict": "<1-5>",
  "notes": "<one sentence explanation>"
}"""

# ── Few-Shot Examples (Gold Anchors) ──────────────────────────────

EXAMPLES = [
    {
        "set": "Which one of you bitches do I got to marry to get this fucking passport, huh? Can be a guy, too. I don't give a fuck. I'll easily suck dick for freedom. I'm like a professional immigrant. I watch 90-day Fiancé like it's game tape. The key is pregnancy. That's why Texas is perfect. No abortion, sounds like a guarantee. But knowing my luck, I'd get someone pregnant and she's also illegal. Now we give birth to a Mexican-Estonian, the most useless passport in the world.",
        "score": {
            "opening_hook": 2,
            "escalation": 2,
            "specificity": 2,
            "closer": 2,
            "voice": 2,
            "total": 10,
            "verdict": "5",
            "notes": "Perfect opener, specific details throughout, killer closer with 'most useless passport'."
        }
    },
    {
        "set": "I work in a massive warehouse. My job is a problem solver. I come in one day and see this thing staring at me through an abyss of desire. I pick it up — it's 65 pounds of pure straight silicone sand. I'll catch it right there.",
        "score": {
            "opening_hook": 1,
            "escalation": 0,
            "specificity": 1,
            "closer": 0,
            "voice": 1,
            "total": 3,
            "verdict": "2",
            "notes": "Starts OK but flatlines. No escalation, no closer. Just stops."
        }
    },
    {
        "set": "I'm tired of pretending I have to care about homeless people. They come up asking for a dollar. Bitch, you don't have legs. What are you going to spend it on? They never ask for something they need — like a piggyback ride to the nearest bridge so you can toss them off. If they die, they move into God's house. If they live, they've been stinking up the corner for a week, they can start fresh 20 miles away from me.",
        "score": {
            "opening_hook": 2,
            "escalation": 2,
            "specificity": 2,
            "closer": 1,
            "voice": 2,
            "total": 9,
            "verdict": "5",
            "notes": "Strong opener, specific details (bridge, 20 miles), escalating absurdity. Closer decent but not the peak."
        }
    },
    {
        "set": "Happy Kwanzaa, son. I'm wearing this outfit as respect for the ancient Chinese tradition of Kwanzaa. I'd like to read some fortune cookies. Spirit Airlines is starting a frequent fighter discount — earn a free trip after four fights. Jimmy Carter will die on March 12th. I guess I fucked that one up.",
        "score": {
            "opening_hook": 2,
            "escalation": 2,
            "specificity": 2,
            "closer": 2,
            "voice": 2,
            "total": 10,
            "verdict": "5",
            "notes": "Absurdist chaos. Each line tops the last. Specific (Spirit Airlines, Jimmy Carter). Perfect deadpan closer."
        }
    },
    {
        "set": "I'm glad school's abandoning racist books. My white middle school teacher would read the N-word out loud, from a book he wrote. The Adventures of Huckel Nigga. I still believe in God. One time I was about to fail a test, so I prayed. Not even 30 seconds later, 9-11. Thank you, God.",
        "score": {
            "opening_hook": 2,
            "escalation": 2,
            "specificity": 2,
            "closer": 2,
            "voice": 2,
            "total": 10,
            "verdict": "5",
            "notes": "Ironic opener, specific (book title, 9-11 timing), devastating closer. Textbook Kill Tony."
        }
    },
]


class RubricScorer:
    """Score comedy sets using LLM-as-Judge with rubric + few-shot examples."""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("ELLA_MODEL", "gpt-4o-mini")
    
    def score(self, text: str) -> dict:
        """Score a comedy set using the rubric."""
        if not self.client:
            return self._fallback_score(text)
        
        # Build prompt with few-shot examples
        messages = [{"role": "system", "content": RUBRIC}]
        
        # Add few-shot examples
        for ex in EXAMPLES:
            messages.append({
                "role": "user",
                "content": f"Score this set:\n\n\"{ex['set']}\""
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(ex["score"])
            })
        
        # Add the set to score
        messages.append({
            "role": "user",
            "content": f"Score this set:\n\n\"{text}\""
        })
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content or "{}"
            # Extract JSON from response
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw.strip())
        except Exception as e:
            return self._fallback_score(text)
    
    def _fallback_score(self, text: str) -> dict:
        """Rule-based fallback when no LLM available."""
        words = text.split()
        word_count = len(words)
        score = {
            "opening_hook": 1,
            "escalation": 1,
            "specificity": 1,
            "closer": 1,
            "voice": 1,
        }
        
        # Opening hook: check first sentence
        first_sentence = text.split('.')[0] if '.' in text else text[:80]
        if any(w in first_sentence.lower() for w in ['so i', 'um', 'like', 'you know']):
            score["opening_hook"] = 0
        elif any(w in first_sentence.lower() for w in ['i', 'my', 'people', 'someone']):
            score["opening_hook"] = 2
        
        # Specificity: numbers, names
        if any(c.isdigit() for c in text):
            score["specificity"] = 2
        elif len(words) > 50:
            score["specificity"] = 1
        
        # Closer: last sentence length
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if sentences:
            last_words = len(sentences[-1].split())
            if last_words <= 10:
                score["closer"] = 2
            elif last_words <= 20:
                score["closer"] = 1
        
        # Escalation: word count suggests room
        if word_count > 100:
            score["escalation"] = 2
        elif word_count > 60:
            score["escalation"] = 1
        
        # Voice: direct address
        if 'you' in text.lower():
            score["voice"] = 2
        
        total = sum(score.values())
        verdict = str(min(5, max(1, total // 2)))
        
        return {
            **score,
            "total": total,
            "verdict": verdict,
            "notes": f"Fallback scoring ({total}/10)"
        }
    
    def score_all(self, sets: list[dict]) -> list[dict]:
        """Score a list of sets."""
        results = []
        for s in sets:
            result = self.score(s["text"])
            result["title"] = s.get("title", "")
            result["text"] = s["text"][:100] + "..."
            results.append(result)
        return results


# ── Main ────────────────────────────────────────────────────────────

def main():
    scorer = RubricScorer()
    
    # Load Ella's sets
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
    
    # Score all
    print("=" * 60)
    print("  ELLA M — RUBRIC-BASED COMEDY SCORER")
    print("  LLM-as-Judge with few-shot calibration")
    print("=" * 60)
    
    results = scorer.score_all(sets)
    
    for r in results:
        stars = "★" * int(r["verdict"]) + "☆" * (5 - int(r["verdict"]))
        print(f"\n  {stars} ({r['verdict']}/5) — {r['title']}")
        print(f"    Hook: {r['opening_hook']}/2 | Esc: {r['escalation']}/2 | "
              f"Spec: {r['specificity']}/2 | Close: {r['closer']}/2 | "
              f"Voice: {r['voice']}/2 = {r['total']}/10")
        print(f"    {r['notes']}")
    
    # Summary
    verdicts = [int(r["verdict"]) for r in results]
    print(f"\n{'=' * 60}")
    print(f"  {len(results)} sets | Avg: {sum(verdicts)/len(verdicts):.1f}/5")
    print(f"  5/5: {verdicts.count(5)} | 4/5: {verdicts.count(4)} | "
          f"3/5: {verdicts.count(3)} | <3: {sum(1 for v in verdicts if v < 3)}")
    print(f"{'=' * 60}")
    
    # Save
    with open("/root/freaktown/models/rubric_scores.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
