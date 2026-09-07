#!/usr/bin/env python3
"""Freak Town — The Black Room.

The creative director's terminal. 
You design the character. You set the vibe. The AI writes the minute. You hear it.

No database. No web UI. No video. Just you, the script, and TTS.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────

AUDIO_DIR = Path(__file__).parent.parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── Character ───────────────────────────────────────────────────────

@dataclass
class Character:
    name: str = ""
    species: str = ""
    premise: str = ""
    vibe: str = ""  # deadpan, manic, anxious, confident
    voice: str = "en-US-AriaNeural"
    minutes_written: list[dict] = field(default_factory=list)
    
    def summary(self) -> str:
        parts = []
        if self.name: parts.append(f"Name: {self.name}")
        if self.species: parts.append(f"Species: {self.species}")
        if self.premise: parts.append(f"Premise: {self.premise}")
        if self.vibe: parts.append(f"Vibe: {self.vibe}")
        return " | ".join(parts) if parts else "(no character yet)"


# ── Beat Detection ──────────────────────────────────────────────────

@dataclass
class Beat:
    id: str
    type: str  # setup, escalation, punchline, tag, closer
    text: str
    pause_ms: int = 300
    word_count: int = 0


def detect_beats(text: str) -> list[Beat]:
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    beats = []
    for i, sent in enumerate(sentences):
        words = sent.split()
        wc = len(words)
        beat_type = "setup"
        pause_ms = 300
        
        if i > 0 and wc < 8 and len(sentences[i-1].split()) > 15:
            beat_type = "punchline"
            pause_ms = 800
        if i == len(sentences) - 1:
            beat_type = "closer"
            pause_ms = 1200 if wc < 10 else 600
        if i > 0 and beats and beats[-1].type == "punchline" and wc < 12:
            beat_type = "tag"
            pause_ms = 400
        
        beats.append(Beat(id=f"b{i+1}", type=beat_type, text=sent, 
                         pause_ms=pause_ms, word_count=wc))
    return beats


# ── TTS ─────────────────────────────────────────────────────────────

async def tts_generate(text: str, voice: str = "en-US-AriaNeural") -> Path:
    """Generate TTS audio file."""
    import edge_tts
    
    filename = f"bt_{hash(text) % 100000}.mp3"
    out_path = AUDIO_DIR / filename
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))
    return out_path


# ── LLM (via OpenCode Go / mimo-v2.5) ──────────────────────────────

def llm_call(prompt: str, system: str = "") -> str:
    """Call LLM for comedy generation."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.opencode-go.com/v1")
    
    if not api_key:
        return _fallback_generator(prompt)
    
    try:
        import httpx
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "mimo-v2.5", "messages": messages, 
                  "temperature": 0.95, "max_tokens": 500},
            timeout=30,
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return _fallback_generator(prompt)


def _fallback_generator(premise: str) -> str:
    """Generate comedy from premise without LLM."""
    templates = [
        f"So I'm a {premise}. You'd think that comes with certain advantages. It does not. The main advantage I have is that nobody expects anything from me. Which is accurate. I've been living under expectations so low they're technically basement-level. My therapist says I should 'lean into my strengths.' My strength is not dying. That's it. That's the whole resume.",
        f"Being a {premise} is exactly what you think it is, except worse. Because you imagine it's quirky and fun. It's not. It's lonely. You know how many other {premise}s there are? Zero. I'm the only one. I'm like a unicorn, except instead of magic I have existential dread and a really specific skill set that nobody asked for.",
        f"People ask me what it's like being a {premise}. I tell them it's like being color-blind, but for the one thing that defines your entire species. Then they ask me to elaborate. I say no. Not because I can't. Because the elaboration would take longer than my attention span, and my attention span is a {premise} attention span, which is to say: what were we talking about?",
    ]
    return random.choice(templates) if True else templates[0]


import random


# ── Display ─────────────────────────────────────────────────────────

def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════╗
║                                                      ║
║   ███████╗██████╗ ██████╗ ███████╗██████╗            ║
║   ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗           ║
║   █████╗  ██║  ██║██████╔╝█████╗  ██████╔╝           ║
║   ██╔══╝  ██║  ██║██╔══██╗██╔══╝  ██╔══██╗           ║
║   ██║     ██████╔╝██║  ██║███████╗██║  ██║           ║
║   ╚═╝     ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝           ║
║                                                      ║
║   B L A C K   R O O M                                ║
║                                                      ║
║   Design a character. Write a minute. Hear it.        ║
║   No video. No avatars. Just the joke.               ║
║                                                      ║
╚══════════════════════════════════════════════════════╝{RESET}
""")


def help_text():
    print(f"""
{BOLD}Commands:{RESET}
  {CYAN}char{RESET}                 Set up your character
  {CYAN}gen{RESET} [premise]        Generate a minute from premise
  {CYAN}write{RESET} <text>         Add your own text
  {CYAN}beats{RESET}               Show detected beats
  {CYAN}edit{RESET} <id> <text>    Edit a beat
  {CYAN}pause{RESET} <id> <ms>     Set pause after beat
  {CYAN}play{RESET}                Compose & play full set
  {CYAN}play{RESET} <id>           Play single beat
  {CYAN}save{RESET} [name]         Save to file
  {CYAN}load{RESET} <file>         Load from file
  {CYAN}voice{RESET} <name>        Change voice
  {CYAN}help{RESET}               Show this
  {CYAN}quit{RESET}               Exit

{DIM}Flow: char → gen → play → iterate{RESET}
""")


def beats_display(beats: list[Beat]) -> str:
    icons = {"setup": "●", "escalation": "▲", "punchline": "★", 
             "tag": "◆", "closer": "■"}
    lines = []
    for b in beats:
        icon = icons.get(b.type, "●")
        wc = b.word_count
        color = GREEN if wc < 8 else YELLOW if wc < 15 else DIM
        lines.append(
            f"  {BOLD}{icon} {b.id}{RESET} {b.type:<12} "
            f"{color}{b.text[:55]}{'...' if len(b.text)>55 else ''}{RESET} "
            f"{DIM}+{b.pause_ms}ms{RESET}"
        )
    total_ms = sum(b.pause_ms for b in beats) + 30000
    total_w = sum(b.word_count for b in beats)
    lines.append(f"  {DIM}{'─'*60}{RESET}")
    lines.append(f"  {DIM}~{total_ms//1000}s | {total_w} words | {len(beats)} beats{RESET}")
    return "\n".join(lines)


# ── Interactive Loop ────────────────────────────────────────────────

def main():
    banner()
    help_text()
    
    char = Character()
    beats = []
    current_voice = "en-US-AriaNeural"
    
    while True:
        try:
            prompt = f"{MAGENTA}freaktown>{RESET} "
            user = input(prompt).strip()
            if not user:
                continue
            
            parts = user.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if cmd in ("quit", "q", "exit"):
                print(f"\n{DIM}Goodnight.{RESET}")
                break
            
            elif cmd == "help" or cmd == "h":
                help_text()
            
            elif cmd == "char":
                print(f"\n  {BOLD}CHARACTER CREATOR{RESET}")
                if char.name:
                    print(f"  Current: {char.summary()}")
                    print(f"  {DIM}(type 'new' to start over){RESET}")
                
                if arg.lower() == "new" or not char.name:
                    name = input(f"  Name: ").strip() or "Unnamed"
                    species = input(f"  Species (human/dog/robot/pigeon/etc): ").strip()
                    premise = input(f"  Premise (one sentence): ").strip()
                    vibe = input(f"  Vibe (deadpan/manic/anxious/confident): ").strip()
                    char = Character(name=name, species=species, premise=premise, vibe=vibe)
                    print(f"\n  {GREEN}Created: {char.summary()}{RESET}")
                else:
                    field = arg.lower()
                    if field in ("name", "species", "premise", "vibe"):
                        val = input(f"  {field.title()}: ").strip()
                        setattr(char, field, val)
                        print(f"  {GREEN}Updated: {char.summary()}{RESET}")
            
            elif cmd == "gen" or cmd == "generate":
                premise = arg or char.premise or input("  Premise: ").strip()
                if not premise:
                    print(f"{RED}Need a premise{RESET}")
                    continue
                
                print(f"\n{DIM}  Generating minute about: {premise}{RESET}")
                
                system = f"""You are a comedy writer for Freak Town. Write a 60-second standup minute.

Character: {char.name or 'Unknown'}
Species: {char.species or 'Unknown'}
Premise: {premise}
Vibe: {char.vibe or 'deadpan'}

RULES:
- 80-150 words exactly
- First line IS the joke (no warmup)
- Escalating absurdity
- Specific details (numbers, names)
- Killer closer (last line = biggest laugh)
- Direct audience address ("you")
- Conversational, spontaneous tone

Write ONLY the set text. No title, no explanation."""

                text = llm_call(f"Write a 60-second standup minute about: {premise}", system)
                text = text.strip().strip('"').strip("'")
                
                beats = detect_beats(text)
                print(f"\n{BOLD}  Generated {len(beats)} beats:{RESET}\n")
                print(beats_display(beats))
                
                # Auto-generate audio
                print(f"\n{DIM}  Generating audio...{RESET}")
                audio_files = []
                for b in beats:
                    f = asyncio.run(tts_generate(b.text, current_voice))
                    audio_files.append(f)
                    print(f"    {b.id} → {f.name}")
                
                print(f"\n  {GREEN}Audio ready. Type 'play' to hear it.{RESET}")
            
            elif cmd == "write" or cmd == "w":
                if not arg:
                    print(f"{RED}Usage: write <text>{RESET}")
                    continue
                new_beats = detect_beats(arg)
                beats.extend(new_beats)
                print(f"\n  Added {len(new_beats)} beats. Total: {len(beats)}")
                print(f"\n{beats_display(beats)}")
            
            elif cmd == "beats" or cmd == "b":
                if not beats:
                    print(f"{DIM}No beats. Use 'gen' or 'write'{RESET}")
                else:
                    print(f"\n{beats_display(beats)}")
            
            elif cmd == "edit":
                parts2 = arg.split(maxsplit=1)
                if len(parts2) < 2:
                    print(f"{RED}Usage: edit <id> <text>{RESET}")
                    continue
                bid, text = parts2
                for b in beats:
                    if b.id == bid:
                        b.text = text
                        b.word_count = len(text.split())
                        print(f"  Updated {bid}")
                        break
            
            elif cmd == "pause":
                parts2 = arg.split(maxsplit=1)
                if len(parts2) < 2:
                    print(f"{RED}Usage: pause <id> <ms>{RESET}")
                    continue
                bid, ms = parts2
                for b in beats:
                    if b.id == bid:
                        b.pause_ms = int(ms)
                        print(f"  {bid} → {ms}ms")
                        break
            
            elif cmd == "play":
                if not beats:
                    print(f"{RED}No beats{RESET}")
                    continue
                
                if arg:
                    # Play single beat
                    for b in beats:
                        if b.id == arg:
                            f = asyncio.run(tts_generate(b.text, current_voice))
                            subprocess.run(["mpv", "--no-video", str(f)], 
                                          capture_output=True, timeout=30)
                            break
                else:
                    # Play all with compositor
                    print(f"\n{DIM}  Composing {len(beats)} beats...{RESET}")
                    all_samples = []
                    sr = 24000
                    
                    for b in beats:
                        f = asyncio.run(tts_generate(b.text, current_voice))
                        # Convert MP3 to WAV samples
                        tmp_wav = AUDIO_DIR / f"_compose_{b.id}.wav"
                        subprocess.run([
                            "ffmpeg", "-y", "-i", str(f), 
                            "-ar", str(sr), "-ac", "1", "-f", "wav", str(tmp_wav)
                        ], capture_output=True, timeout=10)
                        
                        if tmp_wav.exists():
                            import wave, struct
                            with wave.open(str(tmp_wav), 'rb') as w:
                                frames = w.readframes(w.getnframes())
                                samples = list(struct.unpack(f'<{len(frames)//2}h', frames))
                                all_samples.extend(samples)
                            tmp_wav.unlink(missing_ok=True)
                        
                        # Add exact silence
                        silence = [0] * int(sr * b.pause_ms / 1000)
                        all_samples.extend(silence)
                    
                    # Write final WAV
                    import wave, struct, io
                    buf = io.BytesIO()
                    with wave.open(buf, 'wb') as w:
                        w.setnchannels(1)
                        w.setsampwidth(2)
                        w.setframerate(sr)
                        w.writeframes(struct.pack(f'<{len(all_samples)}h', *all_samples))
                    
                    final = AUDIO_DIR / "composed.wav"
                    final.write_bytes(buf.getvalue())
                    
                    print(f"  {GREEN}Composed: {final} (~{len(all_samples)/sr:.1f}s){RESET}")
                    subprocess.run(["mpv", "--no-video", str(final)], 
                                  capture_output=True, timeout=120)
            
            elif cmd == "voice":
                if arg:
                    current_voice = arg
                    print(f"  Voice → {arg}")
                else:
                    print(f"  Current: {current_voice}")
                    print(f"  Options: AriaNeural, GuyNeural, ChristopherNeural, SamanthaNeural")
            
            elif cmd == "save":
                name = arg or f"set_{int(time.time())}"
                data = {
                    "character": {
                        "name": char.name, "species": char.species,
                        "premise": char.premise, "vibe": char.vibe,
                        "voice": char.voice,
                    },
                    "beats": [{"id": b.id, "type": b.type, "text": b.text, 
                              "pause_ms": b.pause_ms} for b in beats],
                    "voice": current_voice,
                }
                path = Path(f"{name}.json")
                path.write_text(json.dumps(data, indent=2))
                print(f"  Saved → {path}")
            
            elif cmd == "load":
                if not arg:
                    print(f"{RED}Usage: load <file>{RESET}")
                    continue
                try:
                    data = json.loads(Path(arg).read_text())
                    c = data.get("character", {})
                    char = Character(**{k: c.get(k, "") for k in 
                                       ["name", "species", "premise", "vibe", "voice"]})
                    beats = [Beat(**b) for b in data.get("beats", [])]
                    current_voice = data.get("voice", "en-US-AriaNeural")
                    print(f"  Loaded: {char.summary()}")
                    print(f"\n{beats_display(beats)}")
                except FileNotFoundError:
                    print(f"{RED}  Not found: {arg}{RESET}")
            
            else:
                # Try treating as a premise
                print(f"\n{DIM}  Generating minute about: {user}{RESET}")
                system = f"""You are a comedy writer for Freak Town. Write a 60-second standup minute.

Premise: {user}

RULES:
- 80-150 words exactly
- First line IS the joke
- Escalating absurdity
- Specific details
- Killer closer
- Direct audience address

Write ONLY the set text."""
                text = llm_call(f"Write a 60-second minute about: {user}", system)
                text = text.strip().strip('"').strip("'")
                beats = detect_beats(text)
                print(f"\n{BOLD}  Generated:{RESET}\n")
                print(beats_display(beats))
        
        except KeyboardInterrupt:
            print(f"\n{DIM}Goodnight.{RESET}")
            break
        except EOFError:
            break
