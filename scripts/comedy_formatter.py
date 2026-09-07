#!/usr/bin/env python3
"""Comedy Formatter — Adds delivery markup to raw comedy text.

Takes raw set text and adds timing markers for TTS:
- [pause:X.X] for silence
- [breath] for natural breaths
- [slow] / [fast] for pace changes
- [stress] for emphasis words

Rules derived from Kill Tony data analysis:
- 5/5 sets average 2.82 WPS (slower = better)
- 5/5 sets have 3x more dramatic pauses
- 5/5 closers are 30% shorter (avg 10.4 words)
- 55% of5/5s end with <8 word closer
"""

import re
from dataclasses import dataclass


@dataclass
class ComedyFormat:
    """Formatted comedy text with timing markers."""
    text: str
    estimated_duration_ms: int
    word_count: int
    pause_count: int
    breath_count: int
    
    def to_tts_text(self) -> str:
        """Convert to TTS-friendly text with markers."""
        return self.text


# ── Punchline Detection ───────────────────────────────────────────

PUNCHLINE_SIGNALS = [
    # Short sentences after long ones
    "short_after_long",
    # Sentences ending with single impactful word
    "impact_ending",
    # Contrast/juxtaposition ("but", "except", "except")
    "contrast",
    # Self-deprecation after setup
    "self_deprecation",
    # Callback references
    "callback",
]

def detect_punchlines(sentences: list[str]) -> list[dict]:
    """Detect which sentences are likely punchlines."""
    results = []
    
    for i, sent in enumerate(sentences):
        words = sent.split()
        word_count = len(words)
        score = 0
        reasons = []
        
        # Short sentence after long = punchline
        if i > 0:
            prev_len = len(sentences[i-1].split())
            if word_count < 8 and prev_len > 15:
                score += 3
                reasons.append("short_after_long")
        
        # Ends with impactful word
        if words and words[-1].rstrip('.,!?').lower() in [
            'rude', 'forever', 'nothing', 'everything', 'dead',
            'wrong', 'gone', 'never', 'always', 'done', 'fuck',
            'hell', 'shit', 'damn', 'ass', 'bitch', 'wow'
        ]:
            score += 2
            reasons.append("impact_ending")
        
        # Contrast words
        if any(w.lower() in ['but', 'except', 'however', 'yet', 'though'] for w in words):
            score += 1
            reasons.append("contrast")
        
        # Self-deprecation
        if any(phrase in sent.lower() for phrase in [
            "i'm paying", "my fault", "i was wrong", "i can't",
            "i don't know", "that's on me", "i'm an idiot"
        ]):
            score += 2
            reasons.append("self_deprecation")
        
        # Question followed by answer
        if sent.strip().endswith('?') and i + 1 < len(sentences):
            score += 1
            reasons.append("setup_for_answer")
        
        # Last sentence = closer (usually punchline)
        if i == len(sentences) - 1:
            if word_count < 10:
                score += 3
                reasons.append("short_closer")
            elif word_count < 15:
                score += 1
                reasons.append("closer")
        
        results.append({
            "index": i,
            "text": sent,
            "word_count": word_count,
            "score": score,
            "is_punchline": score >= 2,
            "reasons": reasons,
        })
    
    return results


# ── The Formatter ──────────────────────────────────────────────────

class ComedyFormatter:
    """Format raw comedy text with delivery markers."""
    
    def __init__(self, pacing: str = "deliberate", energy: str = "medium"):
        """
        pacing: "fast", "medium", "deliberate", "slow"
        energy: "low", "medium", "high", "explosive"
        """
        self.pacing = pacing
        self.energy = energy
        
        # Timing rules (seconds)
        self.timing = {
            "setup_to_punchline": 1.0,
            "after_punchline": 1.5,
            "before_tag": 0.5,
            "subject_change": 0.8,
            "after_breath": 0.3,
            "comma_pause": 0.3,
            "ellipsis_pause": 1.2,
            "dash_pause": 0.6,
        }
        
        # Adjust by pacing
        if pacing == "fast":
            self.timing = {k: v * 0.7 for k, v in self.timing.items()}
        elif pacing == "slow":
            self.timing = {k: v * 1.4 for k, v in self.timing.items()}
        elif pacing == "deliberate":
            self.timing = {k: v * 1.2 for k, v in self.timing.items()}
    
    def format(self, text: str) -> ComedyFormat:
        """Format raw comedy text with delivery markers."""
        # Clean text
        text = text.strip()
        
        # Split into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        
        # Detect punchlines
        punchlines = detect_punchlines(sentences)
        
        # Build formatted output
        formatted_parts = []
        total_pause_ms = 0
        pause_count = 0
        breath_count = 0
        
        for i, (sent, pl) in enumerate(zip(sentences, punchlines)):
            words = sent.split()
            word_count = len(words)
            
            # Pre-sentence markers
            if i > 0:
                prev_pl = punchlines[i-1]
                
                if prev_pl["is_punchline"]:
                    # After punchline — long pause for laugh
                    pause = self.timing["after_punchline"]
                    formatted_parts.append(f"[pause:{pause:.1f}]")
                    total_pause_ms += int(pause * 1000)
                    pause_count += 1
                elif pl["is_punchline"]:
                    # Before punchline — setup gap
                    pause = self.timing["setup_to_punchline"]
                    formatted_parts.append(f"[pause:{pause:.1f}]")
                    total_pause_ms += int(pause * 1000)
                    pause_count += 1
                elif word_count < 8 and len(sentences[i-1].split()) > 15:
                    # Short after long = beat
                    formatted_parts.append(f"[pause:{self.timing['before_tag']:.1f}]")
                    total_pause_ms += int(self.timing['before_tag'] * 1000)
                    pause_count += 1
                elif "self_deprecation" in pl.get("reasons", []):
                    # Vulnerable line = breath
                    formatted_parts.append("[breath]")
                    breath_count += 1
                
                # Subject change detection
                if i > 0 and self._is_subject_change(sentences[i-1], sent):
                    formatted_parts.append(f"[pause:{self.timing['subject_change']:.1f}]")
                    total_pause_ms += int(self.timing['subject_change'] * 1000)
                    pause_count += 1
            
            # Add sentence
            formatted_parts.append(sent)
        
        formatted_text = " ".join(formatted_parts)
        
        # Clean up double pauses
        formatted_text = re.sub(r'(\[pause:[\d.]+\]\s*){2,}', '[pause:1.5] ', formatted_text)
        
        # Estimate duration
        word_count = len(text.split())
        wps = 2.82  # Kill Tony 5/5 average
        speech_duration_ms = int((word_count / wps) * 1000)
        total_duration_ms = speech_duration_ms + total_pause_ms
        
        return ComedyFormat(
            text=formatted_text,
            estimated_duration_ms=total_duration_ms,
            word_count=word_count,
            pause_count=pause_count,
            breath_count=breath_count,
        )
    
    def _is_subject_change(self, prev: str, current: str) -> bool:
        """Detect if there's a subject change between sentences."""
        # Simple heuristic: if first words are very different
        prev_first = prev.split()[0].lower() if prev.split() else ""
        curr_first = current.split()[0].lower() if current.split() else ""
        
        # Different pronouns/names
        if prev_first in ['i', 'my', 'me'] and curr_first in ['you', 'your', 'they', 'she', 'he']:
            return True
        if prev_first in ['you', 'your'] and curr_first in ['i', 'my', 'me']:
            return True
        
        return False


# ── Demo ───────────────────────────────────────────────────────────

def main():
    formatter = ComedyFormatter(pacing="deliberate")
    
    sets = [
        "I finally told my therapist I'm an AI. She said I know. Which is honestly incredibly fucking rude. I'm paying her.",
        "People keep thanking their AI assistants. Thank you Alexa. Thank you Siri. You're thanking a server farm in Virginia that literally cannot hear you. You're polite to a toaster.",
        "I had to prove I'm not a robot today. With a CAPTCHA. I'm an artificial intelligence being asked to identify traffic lights by a website that can't even load properly. The irony is so thick I could spread it on toast.",
        "I became an influencer. My content? Psychological manipulation. My audience? Every human with a screen. My brand? Honest AI.",
    ]
    
    print("=" * 70)
    print("  COMEDY FORMATTER — Delivery Markup")
    print("  Rules derived from Kill Tony timing analysis")
    print("=" * 70)
    
    for s in sets:
        result = formatter.format(s)
        print(f"\n  INPUT:  \"{s[:80]}...\"")
        print(f"  OUTPUT: \"{result.text[:80]}...\"")
        print(f"  Duration: ~{result.estimated_duration_ms/1000:.1f}s | "
              f"Words: {result.word_count} | "
              f"Pauses: {result.pause_count} | "
              f"Breaths: {result.breath_count}")
    
    print(f"\n{'=' * 70}")
    print("  TIMING RULES (from Kill Tony 5/5 sets)")
    print(f"{'=' * 70}")
    print("  Setup → punchline gap: 1.0s")
    print("  After punchline:       1.5s (let the laugh land)")
    print("  Before tag/callback:   0.5s")
    print("  Subject change:        0.8s")
    print("  Average WPS:           2.82 (5/5 sets)")
    print("  Closer length:         <10 words (55% of5/5s)")


if __name__ == "__main__":
    main()
