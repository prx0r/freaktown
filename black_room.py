#!/usr/bin/env python3
"""Black Room — Terminal-based comedy minute editor.

No video. No avatars. No web UI.
Just: text → delivery → TTS → audio → play.

The fastest way to iterate on a comedy minute.

Usage:
  python black_room.py                    # interactive mode
  python black_room.py --text "..."       # quick mode
  python black_room.py --file set.txt     # from file
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────

AUDIO_DIR = Path(__file__).parent / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── Beat Detection ──────────────────────────────────────────────────

@dataclass
class Beat:
    id: str
    type: str  # setup, escalation, punchline, tag, closer
    text: str
    pause_after_ms: int = 300
    pace: float = 1.0
    energy: float = 0.7
    emphasis: float = 0.5
    expression: str = "normal"
    stage: str = "normal"
    gesture: str = "still"
    camera: str = "medium"
    sound: str = "none"


def detect_beats(text: str) -> list[Beat]:
    """Auto-detect comedy beats from raw text."""
    # Split into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    
    beats = []
    for i, sent in enumerate(sentences):
        words = sent.split()
        word_count = len(words)
        
        # Detect beat type
        beat_type = "setup"
        pause_ms = 300
        stage = "normal"
        sound = "none"
        
        # Punchline detection
        is_punchline = False
        if i > 0:
            prev_len = len(sentences[i-1].split())
            if word_count < 8 and prev_len > 15:
                is_punchline = True
                beat_type = "punchline"
                pause_ms = 800
                stage = "hold"
                sound = "rimshot"
        
        # Closer (last sentence)
        if i == len(sentences) - 1:
            beat_type = "closer"
            if word_count < 10:
                pause_ms = 1200
                stage = "hold"
            else:
                pause_ms = 600
        
        # Tag (short after punchline)
        if i > 0 and beats and beats[-1].type == "punchline" and word_count < 12:
            beat_type = "tag"
            pause_ms = 400
        
        # Escalation (longer sentences building up)
        if word_count > 20 and i > 0 and len(sentences[i-1].split()) > 20:
            beat_type = "escalation"
            pace = 1.1
        else:
            pace = 1.0
        
        # Breath before vulnerable lines
        expression = "normal"
        if any(phrase in sent.lower() for phrase in ["i'm paying", "i don't know", "that's on me"]):
            expression = "whisper"
            pause_ms += 200
        
        beat = Beat(
            id=f"b{i+1}",
            type=beat_type,
            text=sent,
            pause_after_ms=pause_ms,
            pace=pace,
            energy=0.7 if beat_type == "punchline" else 0.6,
            emphasis=0.8 if is_punchline else 0.5,
            expression=expression,
            stage=stage,
            gesture="still" if beat_type in ["punchline", "closer"] else "normal",
            camera="close" if beat_type in ["punchline", "closer"] else "medium",
            sound=sound,
        )
        beats.append(beat)
    
    return beats


def format_beats(beats: list[Beat]) -> str:
    """Format beats for terminal display."""
    lines = []
    for b in beats:
        icon = {"setup": "●", "escalation": "▲", "punchline": "★", 
                "tag": "◆", "closer": "■", "misdirect": "◈"}.get(b.type, "●")
        
        pause_display = f"+{b.pause_after_ms}ms" if b.pause_after_ms > 200 else ""
        stage_display = f" [{b.stage}]" if b.stage != "normal" else ""
        sound_display = f" {b.sound}" if b.sound != "none" else ""
        
        # Word count color
        wc = len(b.text.split())
        if wc < 8:
            color = GREEN
        elif wc < 15:
            color = YELLOW
        else:
            color = DIM
        
        lines.append(
            f"  {BOLD}{icon} {b.id}{RESET} {b.type:<12} "
            f"{color}{b.text[:60]}{'...' if len(b.text) > 60 else ''}{RESET} "
            f"{DIM}{pause_display}{stage_display}{sound_display}{RESET}"
        )
    
    return "\n".join(lines)


# ── TTS Generation ──────────────────────────────────────────────────

async def generate_beat_audio(beat: Beat, voice: str = "en-US-AriaNeural", filename: str = None) -> Path:
    """Generate audio for a single beat."""
    import edge_tts
    
    if not filename:
        filename = f"beat_{beat.id}.mp3"
    
    out_path = AUDIO_DIR / filename
    if out_path.exists():
        return out_path
    
    communicate = edge_tts.Communicate(beat.text, voice)
    await communicate.save(str(out_path))
    return out_path


async def generate_full_set(beats: list[Beat], voice: str = "en-US-AriaNeural") -> Path:
    """Generate audio for all beats with timing gaps."""
    import edge_tts
    import wave
    import struct
    
    all_audio = []
    silence_bytes = b""
    sample_rate = 24000
    
    for beat in beats:
        # Generate speech
        tmp_wav = AUDIO_DIR / f"_tmp_{beat.id}.mp3"
        communicate = edge_tts.Communicate(beat.text, voice)
        await communicate.save(str(tmp_wav))
        
        # Convert to raw audio (simplified - just use ffmpeg)
        raw_wav = AUDIO_DIR / f"_raw_{beat.id}.wav"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(tmp_wav), 
                "-ar", str(sample_rate), "-ac", "1", "-f", "wav",
                str(raw_wav)
            ], capture_output=True, timeout=10)
            
            with wave.open(str(raw_wav), 'rb') as w:
                all_audio.append(w.readframes(w.getnframes()))
        except Exception:
            pass
        
        # Generate silence for pause
        silence_samples = int(sample_rate * beat.pause_after_ms / 1000)
        silence = b'\x00\x00' * silence_samples
        all_audio.append(silence)
    
    # Write final WAV
    if not all_audio:
        return None
    
    final_wav = AUDIO_DIR / "full_set.wav"
    with wave.open(str(final_wav), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for chunk in all_audio:
            w.writeframes(chunk)
    
    # Convert to MP3
    final_mp3 = AUDIO_DIR / "full_set.mp3"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(final_wav),
            "-b:a", "192k", str(final_mp3)
        ], capture_output=True, timeout=30)
    except Exception:
        pass
    
    # Cleanup
    for f in AUDIO_DIR.glob("_tmp_*"):
        f.unlink()
    for f in AUDIO_DIR.glob("_raw_*"):
        f.unlink()
    
    return final_mp3 if final_mp3.exists() else final_wav


# ── Black Room UI ───────────────────────────────────────────────────

def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════╗
║                                                  ║
║   ██████╗ ██████╗ ██████╗ ███████╗██████╗        ║
║   ██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗       ║
║   ██████╔╝██████╔╝██║  ██║█████╗  ██████╔╝       ║
║   ██╔══██╗██╔══██╗██║  ██║██╔══╝  ██╔══██╗       ║
║   ██████╔╝██║  ██║██████╔╝███████╗██║  ██║       ║
║   ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝       ║
║                                                  ║
║   T E R M I N A L                                ║
║                                                  ║
║   Write. Format. Hear. Iterate.                  ║
║   No video. No avatars. Just the minute.         ║
║                                                  ║
╚══════════════════════════════════════════════════╝{RESET}
""")


def help_text():
    print(f"""
{BOLD}Commands:{RESET}
  {CYAN}write{RESET} <text>     Add a set
  {CYAN}edit{RESET} <beat_id> <text>  Edit a beat
  {CYAN}pause{RESET} <beat_id> <ms>  Set pause after beat
  {CYAN}beats{RESET}           Show all beats
  {CYAN}play{RESET}            Generate & play TTS
  {CYAN}generate{RESET}        Generate TTS only
  {CYAN}sound{RESET} <beat_id> <sound>  Add sound effect
  {CYAN}save{RESET} [filename] Save delivery JSON
  {CYAN}load{RESET} <filename> Load delivery JSON
  {CYAN}voice{RESET} <name>   Change TTS voice
  {CYAN}help{RESET}           Show this
  {CYAN}quit{RESET}           Exit

{DIM}Beat types: setup, escalation, punchline, tag, closer{RESET}
{DIM}Sounds: rimshot, drum_hit, laugh_track, crowd_cheer, none{RESET}
{DIM}Voices: AriaNeural, GuyNeural, ChristopherNeural, etc.{RESET}
""")


def interactive():
    """Interactive Black Room session."""
    banner()
    help_text()
    
    beats = []
    current_voice = "en-US-AriaNeural"
    
    while True:
        try:
            prompt = f"{MAGENTA}blackroom>{RESET} "
            user_input = input(prompt).strip()
            
            if not user_input:
                continue
            
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if cmd == "quit" or cmd == "q" or cmd == "exit":
                print(f"\n{DIM}Goodnight.{RESET}")
                break
            
            elif cmd == "help" or cmd == "h":
                help_text()
            
            elif cmd == "write" or cmd == "w":
                if not arg:
                    print(f"{RED}Usage: write <comedy text>{RESET}")
                    continue
                
                new_beats = detect_beats(arg)
                beats.extend(new_beats)
                print(f"\n  Added {len(new_beats)} beats. Total: {len(beats)}")
                print(f"\n{beats_display(beats)}")
            
            elif cmd == "beats" or cmd == "b":
                if not beats:
                    print(f"{DIM}No beats yet. Use: write <text>{RESET}")
                else:
                    print(f"\n{beats_display(beats)}")
            
            elif cmd == "edit":
                parts2 = arg.split(maxsplit=1)
                if len(parts2) < 2:
                    print(f"{RED}Usage: edit <beat_id> <new text>{RESET}")
                    continue
                
                beat_id, new_text = parts2
                found = False
                for b in beats:
                    if b.id == beat_id:
                        b.text = new_text
                        # Re-detect type based on new text
                        new_beats = detect_beats(new_text)
                        if new_beats:
                            b.type = new_beats[0].type
                            b.pause_after_ms = new_beats[0].pause_after_ms
                            b.stage = new_beats[0].stage
                        print(f"  Updated {beat_id}")
                        found = True
                        break
                if not found:
                    print(f"{RED}Beat {beat_id} not found{RESET}")
            
            elif cmd == "pause":
                parts2 = arg.split(maxsplit=1)
                if len(parts2) < 2:
                    print(f"{RED}Usage: pause <beat_id> <ms>{RESET}")
                    continue
                
                beat_id, ms = parts2
                for b in beats:
                    if b.id == beat_id:
                        b.pause_after_ms = int(ms)
                        print(f"  {beat_id} pause → {ms}ms")
                        break
            
            elif cmd == "sound":
                parts2 = arg.split(maxsplit=1)
                if len(parts2) < 2:
                    print(f"{RED}Usage: sound <beat_id> <sound_type>{RESET}")
                    continue
                
                beat_id, sound = parts2
                for b in beats:
                    if b.id == beat_id:
                        b.sound = sound
                        print(f"  {beat_id} sound → {sound}")
                        break
            
            elif cmd == "voice":
                if arg:
                    current_voice = arg
                    print(f"  Voice → {arg}")
                else:
                    print(f"  Current voice: {current_voice}")
            
            elif cmd == "generate" or cmd == "gen":
                if not beats:
                    print(f"{RED}No beats to generate{RESET}")
                    continue
                
                print(f"\n{DIM}Generating TTS for {len(beats)} beats...{RESET}")
                asyncio.run(generate_all_beats(beats, current_voice))
                print(f"{GREEN}  Audio saved to {AUDIO_DIR}/{RESET}")
            
            elif cmd == "play":
                if not beats:
                    print(f"{RED}No beats to play{RESET}")
                    continue
                
                print(f"\n{DIM}Generating & playing full set...{RESET}")
                result = asyncio.run(generate_full_set(beats, current_voice))
                if result:
                    print(f"{GREEN}  Generated: {result}{RESET}")
                    # Try to play
                    try:
                        subprocess.run(["mpv", "--no-video", str(result)], 
                                      capture_output=True, timeout=30)
                    except FileNotFoundError:
                        try:
                            subprocess.run(["ffplay", "-nodisp", "-autoexit", str(result)], 
                                          capture_output=True, timeout=30)
                        except FileNotFoundError:
                            print(f"  {DIM}Install mpv or ffplay to auto-play{RESET}")
                            print(f"  Manual: mpv {result}")
                else:
                    print(f"{RED}  Generation failed{RESET}")
            
            elif cmd == "save":
                filename = arg or f"delivery_{int(time.time())}.json"
                delivery = {
                    "version": "freaktown.delivery.v1",
                    "voice": {"provider": "edge-tts", "voice_id": current_voice},
                    "beats": [
                        {
                            "id": b.id, "type": b.type, "text": b.text,
                            "delivery": {"pace": b.pace, "energy": b.energy, 
                                        "emphasis": b.emphasis, "expression": b.expression},
                            "pause_after_ms": b.pause_after_ms,
                            "stage": b.stage, "gesture": b.gesture,
                            "camera": b.camera, "sound": b.sound,
                        }
                        for b in beats
                    ],
                    "metadata": {
                        "total_duration_ms": sum(b.pause_after_ms for b in beats) + 30000,
                        "word_count": sum(len(b.text.split()) for b in beats),
                        "beat_count": len(beats),
                    }
                }
                out_path = Path(filename)
                with open(out_path, "w") as f:
                    json.dump(delivery, f, indent=2)
                print(f"  Saved → {out_path}")
            
            elif cmd == "load":
                if not arg:
                    print(f"{RED}Usage: load <filename>{RESET}")
                    continue
                try:
                    with open(arg) as f:
                        delivery = json.load(f)
                    beats = []
                    for b in delivery.get("beats", []):
                        beats.append(Beat(
                            id=b["id"], type=b["type"], text=b["text"],
                            pause_after_ms=b.get("pause_after_ms", 300),
                            pace=b.get("delivery", {}).get("pace", 1.0),
                            expression=b.get("delivery", {}).get("expression", "normal"),
                            stage=b.get("stage", "normal"),
                            sound=b.get("sound", "none"),
                        ))
                    print(f"  Loaded {len(beats)} beats from {arg}")
                    print(f"\n{beats_display(beats)}")
                except FileNotFoundError:
                    print(f"{RED}  File not found: {arg}{RESET}")
            
            else:
                print(f"{DIM}Unknown command: {cmd}. Type 'help' for commands.{RESET}")
        
        except KeyboardInterrupt:
            print(f"\n{DIM}Goodnight.{RESET}")
            break
        except EOFError:
            break


async def generate_all_beats(beats: list[Beat], voice: str):
    """Generate audio for all beats."""
    for beat in beats:
        await generate_beat_audio(beat, voice, f"beat_{beat.id}.mp3")
        print(f"  {beat.id} → {AUDIO_DIR}/beat_{beat.id}.mp3")


def beats_display(beats: list[Beat]) -> str:
    """Display beats nicely."""
    header = f"\n  {BOLD}{'ID':<6} {'TYPE':<12} {'TEXT':<45} {'PAUSE':<8} {'SOUND':<12}{RESET}"
    lines = [header, f"  {'─' * 85}"]
    lines.extend(format_beats(beats).split("\n"))
    lines.append(f"  {'─' * 85}")
    
    total_ms = sum(b.pause_after_ms for b in beats) + 30000
    total_words = sum(len(b.text.split()) for b in beats)
    punchlines = sum(1 for b in beats if b.type == "punchline")
    lines.append(f"  {DIM}Total: ~{total_ms/1000:.0f}s | {total_words} words | {punchlines} punchlines{RESET}")
    
    return "\n".join(lines)


# ── CLI Mode ────────────────────────────────────────────────────────

def quick_mode(text: str, voice: str = "en-US-AriaNeural"):
    """Quick mode: text → beats → generate → done."""
    banner()
    
    beats = detect_beats(text)
    print(f"\n  {BOLD}Detected {len(beats)} beats:{RESET}")
    print(f"\n{beats_display(beats)}")
    
    print(f"\n{DIM}Generating TTS...{RESET}")
    asyncio.run(generate_full_set(beats, voice))
    print(f"{GREEN}  Generated: {AUDIO_DIR}/full_set.mp3{RESET}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Black Room — Terminal comedy minute editor")
    parser.add_argument("--text", type=str, help="Quick mode: text to process")
    parser.add_argument("--file", type=str, help="Quick mode: read text from file")
    parser.add_argument("--voice", type=str, default="en-US-AriaNeural", help="TTS voice")
    args = parser.parse_args()
    
    if args.text:
        quick_mode(args.text, args.voice)
    elif args.file:
        with open(args.file) as f:
            text = f.read()
        quick_mode(text, args.voice)
    else:
        interactive()


if __name__ == "__main__":
    main()
