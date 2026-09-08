"""Rubric Scorer — LLM-as-Judge comedy evaluation.

5-dimension rubric with few-shot gold anchors from real Kill Tony sets.
Research: 79% accuracy vs 30% for ML models.

Dimensions:
1. Opening Hook (0-2): Does the first line grab?
2. Escalation (0-2): Does it build to something bigger?
3. Specificity (0-2): Concrete details vs abstract?
4. Closer (0-2): Last line = biggest laugh?
5. Voice (0-2): Distinct, memorable persona?

Total: 0-10, mapped to Kill Tony scores 1-5.
"""

import json
import logging
import os

logger = logging.getLogger("freak_town.scoring")

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
   2: Numbers, names, places. Specific and vivid.

4. CLOSER (0-2)
   0: Trails off. "So yeah..." or just stops.
   1: Decent ending but not the biggest laugh
   2: Last line IS the biggest laugh. Sharp, unexpected, done.

5. VOICE (0-2)
   0: Generic. Could be anyone.
   1: Has some personality but not distinct
   2: Immediately recognizable. You know who's talking.

OUTPUT STRICT JSON:
{"opening_hook": <0-2>, "escalation": <0-2>, "specificity": <0-2>, "closer": <0-2>, "voice": <0-2>, "total": <0-10>, "verdict": "<1-5>", "notes": "<one sentence>"}"""

# Few-shot gold anchors from real Kill Tony sets
EXAMPLES = [
    {
        "set": "Which one of you bitches do I got to marry to get this fucking passport, huh? Can be a guy, too. I don't give a fuck. I'll easily suck dick for freedom. I'm like a professional immigrant. I watch 90-day Fiancé like it's game tape. The key is pregnancy. That's why Texas is perfect. No abortion, sounds like a guarantee. But knowing my luck, I'd get someone pregnant and she's also illegal. Now we give birth to a Mexican-Estonian, the most useless passport in the world.",
        "score": {"opening_hook": 2, "escalation": 2, "specificity": 2, "closer": 2, "voice": 2, "total": 10, "verdict": "5", "notes": "Perfect opener, specific details throughout, killer closer with 'most useless passport'."}
    },
    {
        "set": "I work in a massive warehouse. My job is a problem solver. I come in one day and see this thing staring at me through an abyss of desire. I pick it up — it's 65 pounds of pure straight silicone sand. I'll catch it right there.",
        "score": {"opening_hook": 1, "escalation": 0, "specificity": 1, "closer": 0, "voice": 1, "total": 3, "verdict": "2", "notes": "Starts OK but flatlines. No escalation, no closer. Just stops."}
    },
    {
        "set": "I'm glad school's abandoning racist books. My white middle school teacher would read the N-word out loud, from a book he wrote. The Adventures of Huckel Nigga. I still believe in God. One time I was about to fail a test, so I prayed. Not even 30 seconds later, 9-11. Thank you, God.",
        "score": {"opening_hook": 2, "escalation": 2, "specificity": 2, "closer": 2, "voice": 2, "total": 10, "verdict": "5", "notes": "Ironic opener, specific (book title, 9-11 timing), devastating closer. Textbook Kill Tony."}
    },
]


class RubricScorer:
    """Score comedy sets using LLM-as-Judge with rubric + few-shot examples."""

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

    def score(self, text: str) -> dict:
        """Score a comedy set using the 5-dimension rubric."""
        if not self.client:
            return self._fallback_score(text)

        messages = [{"role": "system", "content": RUBRIC}]
        for ex in EXAMPLES:
            messages.append({"role": "user", "content": f"Score this set:\n\n\"{ex['set']}\""})
            messages.append({"role": "assistant", "content": json.dumps(ex["score"])})
        messages.append({"role": "user", "content": f"Score this set:\n\n\"{text}\""})

        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=0.3, max_tokens=300,
            )
            raw = resp.choices[0].message.content or "{}"
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw: raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw.strip())
        except Exception:
            return self._fallback_score(text)

    def _fallback_score(self, text: str) -> dict:
        """Rule-based fallback when no LLM available."""
        words = text.split()
        score = {"opening_hook": 1, "escalation": 1, "specificity": 1, "closer": 1, "voice": 1}

        first_sentence = text.split('.')[0] if '.' in text else text[:80]
        if any(w in first_sentence.lower() for w in ['so i', 'um', 'like', 'you know']):
            score["opening_hook"] = 0
        elif any(w in first_sentence.lower() for w in ['i', 'my', 'people', 'someone']):
            score["opening_hook"] = 2

        if any(c.isdigit() for c in text): score["specificity"] = 2
        elif len(words) > 50: score["specificity"] = 1

        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if sentences:
            last_words = len(sentences[-1].split())
            if last_words <= 10: score["closer"] = 2
            elif last_words <= 20: score["closer"] = 1

        if len(words) > 100: score["escalation"] = 2
        elif len(words) > 60: score["escalation"] = 1
        if 'you' in text.lower(): score["voice"] = 2

        total = sum(score.values())
        return {**score, "total": total, "verdict": str(min(5, max(1, total // 2))), "notes": f"Fallback scoring ({total}/10)"}
