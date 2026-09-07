#!/usr/bin/env python3
"""Sound Bank — Pre-generated comedy stings and effects.

The band: rimshots, drum hits, crowd sounds, walkout stings.
All generated once, cached forever. No GPU needed at runtime.

Usage:
  python sound_bank.py                    # show all sounds
  python sound_bank.py --generate         # generate all
  python sound_bank.py --play rimshot     # play a sound
"""

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


SOUND_DIR = Path(__file__).parent / "sounds"
SOUND_DIR.mkdir(exist_ok=True)


# ── Sound Templates ─────────────────────────────────────────────────

SOUNDS = {
    # Comedy band sounds
    "rimshot": {
        "prompt": "Comedy rimshot, ba-dum-tss, drum sting, punchline punctuation",
        "duration": 2,
        "category": "band",
    },
    "drum_hit": {
        "prompt": "Single snare drum hit, sharp attack, comedy punctuation, 1 second",
        "duration": 1,
        "category": "band",
    },
    "rimshot_long": {
        "prompt": "Extended comedy rimshot, ba-dum-tss-crash, triumphant drum sting",
        "duration": 3,
        "category": "band",
    },
    "ba_dum_tss": {
        "prompt": "Classic ba-dum-tss comedy drums, two hits and a cymbal",
        "duration": 2,
        "category": "band",
    },
    "sting": {
        "prompt": "Dramatic orchestral sting, tension hit, surprise reveal sound",
        "duration": 2,
        "category": "band",
    },
    
    # Crowd sounds
    "laugh": {
        "prompt": "Studio audience laughter, sitcom laugh track, warm genuine laughter, 3 seconds",
        "duration": 3,
        "category": "crowd",
    },
    "laugh_big": {
        "prompt": "Large audience roaring with laughter, comedy club crowd going wild, 4 seconds",
        "duration": 4,
        "category": "crowd",
    },
    "clap": {
        "prompt": "Audience applause, clapping, appreciation, 3 seconds",
        "duration": 3,
        "category": "crowd",
    },
    "boo": {
        "prompt": "Crowd booing, disapproval, arena atmosphere, 2 seconds",
        "duration": 2,
        "category": "crowd",
    },
    "crickets": {
        "prompt": "Crickets chirping, awkward silence, comedy failure sound, 3 seconds",
        "duration": 3,
        "category": "crowd",
    },
    "gasp": {
        "prompt": "Audience gasping, shocked reaction, collective surprise, 2 seconds",
        "duration": 2,
        "category": "crowd",
    },
    "ohhhh": {
        "prompt": "Audience saying ohhhh, shocked disapproval, comedy club reaction, 2 seconds",
        "duration": 2,
        "category": "crowd",
    },
    
    # Musical stings
    "fanfare": {
        "prompt": "Triumphant fanfare, victory sting, celebration, bright brass, 3 seconds",
        "duration": 3,
        "category": "music",
    },
    "sad_trombone": {
        "prompt": "Comedy failure sound, sad trombone, wah-wah-wah, deflating, 3 seconds",
        "duration": 3,
        "category": "music",
    },
    "suspense": {
        "prompt": "Suspenseful build, tension rising, dramatic pause music, 3 seconds",
        "duration": 3,
        "category": "music",
    },
    "walkout_funk": {
        "prompt": "Sleazy 1980s cop-show funk, heroic saxophone, punchy bass, walk-on stage music",
        "duration": 8,
        "category": "walkout",
    },
    "walkout_rock": {
        "prompt": "Epic stadium rock, power chord riff, triumphant walk-on music, 120 BPM",
        "duration": 8,
        "category": "walkout",
    },
    "walkout_electronic": {
        "prompt": "Driving synthwave, pulsing bass, neon energy, walk-on stage, 128 BPM",
        "duration": 8,
        "category": "walkout",
    },
    "walkout_jazz": {
        "prompt": "Cool jazz walk-on, walking bass, brush drums, confident entrance, 110 BPM",
        "duration": 8,
        "category": "walkout",
    },
    "walkout_orchestral": {
        "prompt": "Grand orchestral fanfare, brass section, heroic entrance, 100 BPM",
        "duration": 8,
        "category": "walkout",
    },
    "walkout_comedy": {
        "prompt": "Quirky comedy entrance, tuba and plucked strings, absurdly serious, 100 BPM",
        "duration": 8,
        "category": "walkout",
    },
    
    # Character-specific walkouts
    "walkout_pigeon": {
        "prompt": "Paranoid military snare drum with pigeon coos, nervous energy, absurdly heroic",
        "duration": 8,
        "category": "character",
    },
    "walkout_robot": {
        "prompt": "Horrible corporate hold music that drops into heavy bass, robot entrance",
        "duration": 8,
        "category": "character",
    },
    "walkout_roomba": {
        "prompt": "Grand orchestral entrance that ends with vacuum cleaner noise, absurdly epic",
        "duration": 8,
        "category": "character",
    },
    "walkout_medieval": {
        "prompt": "Gregorian chant that transitions into motivational EDM, medieval knight entrance",
        "duration": 8,
        "category": "character",
    },
    "walkout_dog": {
        "prompt": "Sleazy detective show theme, police dog entrance, bouncy bass, confident",
        "duration": 8,
        "category": "character",
    },
}


# ── Sound Bank Manager ──────────────────────────────────────────────

class SoundBank:
    """Manage pre-generated comedy sounds."""
    
    def __init__(self):
        self.sounds_dir = SOUND_DIR
        self.manifest_path = SOUND_DIR / "manifest.json"
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                return json.load(f)
        return {"sounds": {}}
    
    def _save_manifest(self):
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2)
    
    def list_sounds(self, category: str = None):
        """List available sounds."""
        for name, info in sorted(SOUNDS.items()):
            cat = info["category"]
            if category and cat != category:
                continue
            
            exists = (self.sounds_dir / f"{name}.mp3").exists()
            status = f"{GREEN}●{RESET}" if exists else f"{RED}○{RESET}"
            
            print(f"  {status} {name:<25} [{cat}] {info['duration']}s  {DIM}{info['prompt'][:50]}...{RESET}")
    
    def has_sound(self, name: str) -> bool:
        return (self.sounds_dir / f"{name}.mp3").exists()
    
    def get_sound_path(self, name: str) -> Path:
        return self.sounds_dir / f"{name}.mp3"
    
    async def generate_sound(self, name: str):
        """Generate a single sound using edge-tts as placeholder.
        In production, use Stable Audio Open or MiniMax Music.
        """
        info = SOUNDS.get(name)
        if not info:
            print(f"  {RED}Unknown sound: {name}{RESET}")
            return
        
        out_path = self.sounds_dir / f"{name}.mp3"
        
        # For now, use edge-tts to generate a placeholder
        # In production, this would call Stable Audio Open API
        try:
            import edge_tts
            # Generate a simple tone as placeholder
            communicate = edge_tts.Communicate(
                f"[Sound effect: {info['prompt']}]",
                "en-US-GuyNeural"
            )
            await communicate.save(str(out_path))
            print(f"  {GREEN}Generated: {name}{RESET}")
        except Exception as e:
            print(f"  {RED}Failed: {name} — {e}{RESET}")
    
    async def generate_all(self):
        """Generate all sounds."""
        print(f"\n  Generating {len(SOUNDS)} sounds...")
        for name in SOUNDS:
            await self.generate_sound(name)
        print(f"\n  {GREEN}Done. Sounds saved to {self.sounds_dir}/{RESET}")
    
    def play_sound(self, name: str):
        """Play a sound."""
        path = self.get_sound_path(name)
        if not path.exists():
            print(f"  {RED}Sound not found: {name}{RESET}")
            return
        
        try:
            subprocess.run(["mpv", "--no-video", "--really-quiet", str(path)], timeout=10)
        except FileNotFoundError:
            try:
                subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)], timeout=10)
            except FileNotFoundError:
                print(f"  {DIM}Install mpv or ffplay to play sounds{RESET}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sound Bank — Comedy sound effects")
    parser.add_argument("--generate", action="store_true", help="Generate all sounds")
    parser.add_argument("--play", type=str, help="Play a sound")
    parser.add_argument("--list", action="store_true", help="List all sounds")
    parser.add_argument("--category", type=str, help="Filter by category")
    args = parser.parse_args()
    
    bank = SoundBank()
    
    if args.generate:
        asyncio.run(bank.generate_all())
    elif args.play:
        bank.play_sound(args.play)
    else:
        print(f"\n{BOLD}  SOUND BANK{RESET}")
        print(f"  {DIM}Pre-generated comedy sounds for the band{RESET}\n")
        bank.list_sounds(args.category)
        print(f"\n  {DIM}Generate: python sound_bank.py --generate{RESET}")
        print(f"  {DIM}Play: python sound_bank.py --play rimshot{RESET}\n")


if __name__ == "__main__":
    main()
