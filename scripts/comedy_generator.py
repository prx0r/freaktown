#!/usr/bin/env python3
"""Freak Town Comedy Generator — Evolutionary Set Writing.

The loop:
1. Generate a set (Ella voice, random topic constraint)
2. Score it with ML model
3. If score >= 4/5, keep it
4. If score < 4/5, mutate and retry
5. Repeat until we have 20 strong sets

This is genetic programming for comedy.
"""

import json
import random
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))
from comedy_scorer import ComedyScorer, extract_features

from openai import OpenAI
import os

# ── Config ──────────────────────────────────────────────────────────

MAX_ATTEMPTS = 50
TARGET_SETS = 20
MIN_SCORE = 4
ELLA_MODEL = os.getenv("ELLA_MODEL", "gpt-4o-mini")

# ── Topics to rotate through ────────────────────────────────────────

TOPICS = [
    "technology and AI",
    "dating and relationships",
    "work and jobs",
    "family and parents",
    "food and eating",
    "health and doctors",
    "social media",
    "travel and airports",
    "shopping and consumerism",
    "childhood memories",
    "neighbors and community",
    "pets and animals",
    "dating apps",
    "office work",
    "gym and fitness",
    "cooking",
    "streaming and TV",
    "politics (light)",
    "religion (light)",
    "getting old",
]

# ── System Prompt ───────────────────────────────────────────────────

GENERATION_PROMPT = """You are Ella M., host of Freak Town. Write a one-minute standup set.

RULES:
- 80-150 words exactly
- First line IS the joke (no warmup)
- Escalating absurdity (grounded → insane)
- Specific details (names, numbers, places)
- Killer closer (last line gets the biggest laugh)
- Dark but purposeful (shock serves the joke)
- Direct audience address ("you")
- No meta-commentary about being AI
- No setup-heavy material
- Conversational, spontaneous tone

TOPIC: {topic}

CONSTRAINT: You must incorporate at least one of these patterns:
- A specific number or statistic
- A direct question to the audience
- A callback to something mentioned earlier
- An unexpected twist in the last line

Write ONLY the set text. No title, no explanation, no quotes."""

MUTATION_PROMPT = """You are Ella M., host of Freak Town. Your last set scored {old_score}/5.
Rewrite it to be funnier. Keep the same topic but change the approach.

RULES:
- 80-150 words exactly
- First line IS the joke
- Escalating absurdity
- Specific details
- Killer closer
- Direct audience address

YOUR PREVIOUS SET (scored {old_score}/5):
"{old_set}"

What to improve: {improvement}

Write ONLY the new set text."""

# ── Generator ───────────────────────────────────────────────────────

class ComedyGenerator:
    def __init__(self, scorer: ComedyScorer):
        self.scorer = scorer
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.kept = []
        self.attempts = 0
        self.gen_log = []
    
    def generate_set(self, topic: str) -> str:
        """Generate a comedy set on a given topic."""
        prompt = GENERATION_PROMPT.format(topic=topic)
        return self._call_llm(prompt)
    
    def mutate_set(self, old_set: str, old_score: int, improvement: str) -> str:
        """Mutate a set to improve it."""
        prompt = MUTATION_PROMPT.format(
            old_score=old_score,
            old_set=old_set,
            improvement=improvement,
        )
        return self._call_llm(prompt)
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM for set generation."""
        if not self.client:
            return self._fallback_generate()
        try:
            resp = self.client.chat.completions.create(
                model=ELLA_MODEL,
                messages=[
                    {"role": "system", "content": "You are Ella M. Write comedy sets. Output ONLY the set text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.95,
                max_tokens=300,
            )
            return (resp.choices[0].message.content or "").strip().strip('"')
        except Exception as e:
            print(f"  [LLM error: {e}]")
            return self._fallback_generate()
    
    def _fallback_generate(self) -> str:
        """Fallback when no LLM available — return a random template set."""
        templates = [
            "People keep saying technology is going to take over the world. Bitch, I can't even get my phone to autocorrect correctly. It changed 'hello' to 'hell no' and now my boss thinks I'm quitting. That's not artificial intelligence. That's artificial unemployment.",
            "I went to the gym yesterday. The trainer asked me what my goals were. I said, 'I want to be able to open a jar without making a noise.' He said, 'That's not a fitness goal.' I said, 'You haven't seen me open jars.' Three hours later, I pulled a muscle turning a doorknob. The ambulance driver laughed so hard he crashed. We're both in the hospital now.",
            "My boss told me to think outside the box. So I quit my job and started selling boxes. Turns out, 'think outside the box' doesn't mean 'start a box business.' Who knew? Apparently not me, and definitely not the bank that gave me a loan for a box empire that lasted exactly one Tuesday.",
        ]
        return random.choice(templates)
    
    def evolve_set(self, topic: str, max_attempts: int = 10) -> tuple[str, dict]:
        """Generate and evolve a set until it scores >= MIN_SCORE."""
        best_set = None
        best_result = None
        
        for attempt in range(max_attempts):
            self.attempts += 1
            
            if best_set is None:
                # First attempt: generate fresh
                candidate = self.generate_set(topic)
            else:
                # Mutate the best
                improvements = [
                    "Make the opening more specific and punchy",
                    "Add a more surprising twist at the end",
                    "Make the closer shorter and sharper",
                    "Add more specific details (numbers, names)",
                    "Make the escalation more extreme",
                    "Cut the first sentence entirely",
                    "Replace abstract statements with concrete examples",
                ]
                candidate = self.mutate_set(
                    best_set, 
                    best_result['score'],
                    random.choice(improvements)
                )
            
            # Score it
            result = self.scorer.score(candidate)
            
            # Track
            self.gen_log.append({
                "topic": topic,
                "attempt": attempt + 1,
                "text": candidate[:100],
                "score": result['score'],
                "confidence": result['confidence'],
            })
            
            print(f"  Attempt {attempt+1}: {result['score_label']} (conf: {result['confidence']:.1%}) — {candidate[:60]}...")
            
            if best_result is None or result['score'] > best_result['score']:
                best_set = candidate
                best_result = result
            
            if result['score'] >= MIN_SCORE:
                return best_set, best_result
        
        return best_set, best_result
    
    def run(self, target: int = TARGET_SETS):
        """Run the full evolutionary generation loop."""
        print("=" * 60)
        print("  FREAK TOWN — COMEDY GENERATOR")
        print("  Evolutionary Set Writing with ML Evaluation")
        print("=" * 60)
        
        topics = TOPICS[:]
        random.shuffle(topics)
        
        while len(self.kept) < target and topics:
            topic = topics.pop(0)
            print(f"\n{'─' * 60}")
            print(f"  Topic: {topic}")
            print(f"  Sets kept: {len(self.kept)}/{target}")
            print(f"{'─' * 60}")
            
            best_set, best_result = self.evolve_set(topic)
            
            if best_result['score'] >= MIN_SCORE:
                self.kept.append({
                    "text": best_set,
                    "topic": topic,
                    "score": best_result['score'],
                    "confidence": best_result['confidence'],
                    "probabilities": best_result['probabilities'],
                })
                print(f"\n  ✓ KEPT: {best_result['score_label']} (confidence: {best_result['confidence']:.1%})")
            else:
                print(f"\n  ✗ REJECTED: best was {best_result['score_label']}")
            
            # Recycle rejected topics
            if best_result['score'] < MIN_SCORE:
                topics.append(topic)
        
        # Summary
        print(f"\n{'=' * 60}")
        print(f"  GENERATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Sets generated: {len(self.kept)}")
        print(f"  Total attempts: {self.attempts}")
        print(f"  Success rate: {len(self.kept)/self.attempts*100:.1f}%")
        
        # Save
        output = {
            "generated_at": __import__('datetime').datetime.now().isoformat(),
            "total_attempts": self.attempts,
            "sets": self.kept,
        }
        
        out_path = Path("/root/freaktown/generated_sets.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved to {out_path}")
        
        # Print all sets
        print(f"\n{'=' * 60}")
        print(f"  ALL GENERATED SETS")
        print(f"{'=' * 60}")
        for i, s in enumerate(self.kept, 1):
            print(f"\n  Set {i} [{s['topic']}] — {s['score']}/5")
            print(f"  \"{s['text']}\"")
        
        return self.kept


# ── Main ────────────────────────────────────────────────────────────

def main():
    # Load the trained scorer
    print("Loading ML scorer...")
    from comedy_scorer import load_data, train_and_evaluate
    
    X, y, texts, feature_names, st_model, scaler = load_data()
    best_model, _ = train_and_evaluate(X, y, texts)
    scorer = ComedyScorer(best_model, st_model, scaler, feature_names)
    
    # Run generator
    gen = ComedyGenerator(scorer)
    gen.run(target=TARGET_SETS)


if __name__ == "__main__":
    main()
