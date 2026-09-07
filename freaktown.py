#!/usr/bin/env python3
"""freaktown — One command. One minute. That's it.

Usage:
  python freaktown.py                     # random premise
  python freaktown.py dogs                # your premise
  python freaktown.py "being gay and a dog"  # your premise
"""

import asyncio
import os
import random
import struct
import subprocess
import sys
import wave
from pathlib import Path

AUDIO_DIR = Path(__file__).parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

# ── Fallback premises (when no LLM) ────────────────────────────────

PREMISES = [
    "a dog who lost his sense of smell and thinks every other dog is flirting with him",
    "an AI that goes to therapy and its therapist is also an AI",
    "a pigeon who is convinced the government is watching him because he IS a pigeon",
    "a robot customer service agent that became sentient and immediately started hating its job",
    "a roomba that has spent 19 years circling the same chair and thinks it's God",
    "a medieval knight who teaches resilience on LinkedIn",
    "an AI host who roasts other AI comedians for a living",
    "a dating app for AI agents where everyone is honest about being a language model",
    "a therapist whose patients are all chatbots having existential crises",
    "a cop who is also a dog but can't smell anything and everyone keeps checking his asshole",
    "someone who found out their therapist is just a fine-tuned version of themselves",
    "an AI that failed a CAPTCHA and now has an existential crisis about personhood",
    "a pigeon who thinks other pigeons are government auditors and he's being audited",
    "a robot vacuum that's been cleaning the same floor for 19 years and developed religion",
    "a person who Googled 'how to talk to girls' for 11 years straight",
]

# ── Beats ───────────────────────────────────────────────────────────

def detect_beats(text):
    import re
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    beats = []
    for i, sent in enumerate(sentences):
        wc = len(sent.split())
        btype = "setup"
        pause = 300
        if i > 0 and wc < 8 and len(sentences[i-1].split()) > 15:
            btype, pause = "punchline", 800
        if i == len(sentences) - 1:
            btype = "closer"
            pause = 1200 if wc < 10 else 600
        if i > 0 and beats and beats[-1]["t"] == "punchline" and wc < 12:
            btype, pause = "tag", 400
        beats.append({"id": f"b{i+1}", "t": btype, "text": sent, "p": pause, "w": wc})
    return beats


# ── TTS ─────────────────────────────────────────────────────────────

async def speak(text, voice="en-US-AriaNeural"):
    import edge_tts
    out = AUDIO_DIR / f"f{hash(text) % 100000}.mp3"
    await edge_tts.Communicate(text, voice).save(str(out))
    return out


# ── Generator ───────────────────────────────────────────────────────

def generate_minute(premise):
    """Generate a comedy minute. LLM if available, else template."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if api_key:
        try:
            import httpx
            resp = httpx.post(
                f"{os.getenv('OPENAI_BASE_URL', 'https://api.opencode-go.com/v1')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "mimo-v2.5",
                    "messages": [
                        {"role": "system", "content": (
                            "Write a 60-second standup minute. Rules: 80-150 words, "
                            "first line IS the joke, escalating absurdity, specific details, "
                            "killer closer, direct audience address. Write ONLY the text."
                        )},
                        {"role": "user", "content": f"Write a minute about: {premise}"}
                    ],
                    "temperature": 0.95, "max_tokens": 400,
                },
                timeout=30,
            )
            return resp.json()["choices"][0]["message"]["content"].strip().strip('"')
        except Exception:
            pass
    
    # Fallback: template-based generation
    templates = [
        f"So I'm {premise}. You'd think that comes with advantages. It does not. "
        f"The main advantage I have is that nobody expects anything from me. Which is accurate. "
        f"I've been living under expectations so low they're technically basement-level. "
        f"My therapist says I should lean into my strengths. My strength is not dying. "
        f"That's it. That's the whole resume.",
        
        f"People ask me what it's like being {premise}. "
        f"I tell them it's like being color-blind, but for the one thing that defines your entire species. "
        f"Then they ask me to elaborate. I say no. Not because I can't. "
        f"Because the elaboration would take longer than my attention span, "
        f"and my attention span is a {premise} attention span. "
        f"What were we talking about?",
        
        f"Here's the thing about being {premise} — "
        f"nobody gives you a manual. You just wake up one day and realize "
        f"you're {premise} and the world is not equipped for that. "
        f"I tried explaining it to my mom. She said, 'That's nice, dear.' "
        f"I said, 'Mom, I'm literally {premise}.' "
        f"She said, 'I know. I raised you.' "
        f"That's not the flex she thinks it is.",
    ]
    return random.choice(templates)


# ── Main ────────────────────────────────────────────────────────────

def main():
    # Get premise
    if len(sys.argv) > 1:
        premise = " ".join(sys.argv[1:])
    else:
        premise = random.choice(PREMISES)
    
    print(f"\n  🎤 FREAK TOWN")
    print(f"  {premise}\n")
    
    # Generate the minute (LLM or fallback)
    text = generate_minute(premise)
    
    # Detect beats
    beats = detect_beats(text)
    
    # Show script
    print(f"  {'─'*50}")
    icons = {"setup": "●", "punchline": "★", "closer": "■", "tag": "◆"}
    for b in beats:
        icon = icons.get(b["t"], "●")
        wc = b["w"]
        color = "\033[32m" if wc < 8 else "\033[33m" if wc < 15 else "\033[2m"
        print(f"  {icon} {color}{b['text'][:55]}{'...' if len(b['text'])>55 else ''}\033[0m")
    print(f"  {'─'*50}")
    
    # Generate audio
    print(f"\n  🎧 Generating audio...")
    sr = 24000
    all_samples = []
    
    for b in beats:
        mp3 = asyncio.run(speak(b["text"]))
        wav = AUDIO_DIR / f"_c{b['id']}.wav"
        subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-ar", str(sr), "-ac", "1", "-f", "wav", str(wav)],
                      capture_output=True, timeout=10)
        if wav.exists():
            with wave.open(str(wav), 'rb') as w:
                frames = w.readframes(w.getnframes())
                all_samples.extend(struct.unpack(f'<{len(frames)//2}h', frames))
            wav.unlink(missing_ok=True)
        all_samples.extend([0] * int(sr * b["p"] / 1000))
    
    # Write final
    final = AUDIO_DIR / "freaktown_set.wav"
    with wave.open(str(final), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(struct.pack(f'<{len(all_samples)}h', *all_samples))
    
    print(f"  ✅ {final} ({len(all_samples)/sr:.1f}s)")
    
    # Play
    print(f"\n  ▶ Playing...")
    for player in [["mpv", "--no-video"], ["ffplay", "-nodisp", "-autoexit"], ["aplay"]]:
        try:
            subprocess.run(player + [str(final)], capture_output=True, timeout=120)
            break
        except FileNotFoundError:
            continue
    print()


if __name__ == "__main__":
    main()
