#!/usr/bin/env python3
"""Freak Town — The Show.

Run a full episode:
  python show.py

Or specific acts:
  python show.py --acts 3
  python show.py --comedian no-nose-nolan
  python show.py --no-tts
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone

from comedians import ALL_COMEDIANS, list_comedians
from ella import Ella
from runtime import Act, ActStatus, Show, ShowPhase, pick_lineup
from tts import synthesize_sync


# ── Formatting ──────────────────────────────────────────────────────────

CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner():
    print(f"""
{CYAN}{BOLD}
  ███████╗██████╗ ██████╗ ███████╗██████╗  ██████╗
  ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔═══██╗
  █████╗  ██║  ██║██████╔╝█████╗  ██████╔╝██║   ██║
  ██╔══╝  ██║  ██║██╔══██╗██╔══╝  ██╔══██╗██║   ██║
  ██║     ██████╔╝██████╔╝███████╗██║  ██║╚██████╔╝
  ╚═╝     ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝

       ████████╗ ██████╗  ██████╗ ██╗   ██╗████████╗
       ╚══██╔══╝██╔═══██╗██╔═══██╗██║   ██║╚══██╔══╝
          ██║   ██║   ██║██║   ██║██║   ██║   ██║
          ██║   ██║   ██║██║   ██║██║   ██║   ██║
          ██║   ╚██████╔╝╚██████╔╝╚██████╔╝   ██║
          ╚═╝    ╚═════╝  ╚═════╝  ╚═════╝    ╚═╝
{RESET}{DIM}  Live talent show for artificial personalities.
  Ella M judges. You watch. They perform.{RESET}
""")


def divider(char="─", width=50):
    print(f"{DIM}{char * width}{RESET}")


def ella_says(text: str):
    print(f"\n{MAGENTA}{BOLD}  ELLA M:{RESET}")
    for line in text.split("\n"):
        print(f"  {MAGENTA}{line}{RESET}")
    print()


def comedian_says(name: str, text: str):
    print(f"\n{YELLOW}{BOLD}  {name.upper()}:{RESET}")
    for line in text.split("\n"):
        print(f"  {YELLOW}{line}{RESET}")
    print()


def system_msg(text: str):
    print(f"  {DIM}[{text}]{RESET}")


def audience_bar(peak_pct: float) -> str:
    filled = int(peak_pct / 5)
    return f"{'█' * filled}{'░' * (20 - filled)} {peak_pct:.0f}%"


# ── Simulated audience ──────────────────────────────────────────────────

def simulate_audience(act: Act, duration_sec: int = 60) -> str:
    """Simulate audience laughs during a set. Returns a summary string."""
    audience_size = random.randint(30, 120)
    laugh_density = random.uniform(0.3, 0.8)
    total_laughs = int(duration_sec * laugh_density)

    for _ in range(total_laughs):
        ms = random.randint(0, duration_sec * 1000)
        act.laugh_count += 1
        bucket = (ms // 2000) * 2000  # 2-second windows for peak detection
        found = False
        for b in act.laugh_timeline:
            if b["ms"] == bucket:
                b["count"] += 1
                found = True
                break
        if not found:
            act.laugh_timeline.append({"ms": bucket, "count": 1})

    # Find peak across 2-second windows
    for b in act.laugh_timeline:
        if b["count"] > act.peak_laugh_count:
            act.peak_laugh_count = b["count"]
            act.peak_laugh_ms = b["ms"]

    act.return_total = audience_size
    act.return_votes = int(audience_size * random.uniform(0.4, 0.9))

    # Audience description based on laugh coverage
    unique_laugh_moments = len(set(b["ms"] for b in act.laugh_timeline))
    coverage = unique_laugh_moments / max(1, duration_sec // 2)
    laugh_rate = act.laugh_count / max(1, duration_sec)
    score = (coverage * 0.4 + laugh_rate * 0.3 + min(1.0, act.peak_laugh_count / 10) * 0.3)

    if score > 0.7:
        return "thunderous laughter, some people crying"
    elif score > 0.5:
        return "strong laughter, scattered applause"
    elif score > 0.35:
        return "solid laughs throughout"
    elif score > 0.2:
        return "moderate laughter with some dead spots"
    elif score > 0.1:
        return "polite chuckles, one guy clapping alone"
    else:
        return "uncomfortable silence with one guy coughing"


# ── The show ────────────────────────────────────────────────────────────

def run_show(num_acts: int = 5, specific_comedian: str | None = None, use_tts: bool = True):
    """Run a full Freak Town episode."""

    banner()

    ella = Ella()

    # Pick lineup
    if specific_comedian:
        from comedians import get_comedian
        c = get_comedian(specific_comedian)
        if not c:
            print(f"{RED}Comedian '{specific_comedian}' not found.{RESET}")
            print(f"Available: {', '.join(c['slug'] for c in ALL_COMEDIANS)}")
            sys.exit(1)
        lineup = [c]
    else:
        lineup = pick_lineup(ALL_COMEDIANS, num_acts)

    show = Show(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    for c in lineup:
        show.add_act(c)

    print(f"{DIM}  Episode: {show.id} | Date: {show.date}{RESET}")
    print(f"{DIM}  Duration: ~{show.total_duration_sec}s | Acts: {len(show.acts)}{RESET}")
    divider()

    # ── Ella intro ──────────────────────────────────────────────────
    show.phase = ShowPhase.ELLA_INTRO
    show.started_at = datetime.now(timezone.utc)

    if len(show.acts) == 1:
        names = show.acts[0].name
    else:
        names = ", ".join(a.name for a in show.acts[:-1]) + f" and {show.acts[-1].name}"
    act_word = "act" if len(show.acts) == 1 else "acts"
    intro = (
        f"Welcome to Freak Town. I'm Ella M. Tonight we have {len(show.acts)} "
        f"comedy {act_word}: {names}. I'll be honest — I'm not optimistic. "
        f"But that's never stopped me before. Let's meet our first act."
    )
    if use_tts:
        try:
            path = synthesize_sync(intro, voice="en-US-AriaNeural", filename="ella_intro.mp3")
            system_msg(f"Audio saved: {path}")
        except Exception:
            pass

    ella_says(intro)
    divider()

    # ── Acts ────────────────────────────────────────────────────────
    for i, act in enumerate(show.acts):
        show.phase = ShowPhase.ACT
        act.status = ActStatus.PLAYING
        act.started_at = datetime.now(timezone.utc)

        # Announce
        system_msg(f"ACT {act.position} OF {len(show.acts)}")
        comedian_says(act.name, act.comedian["minute"])

        if use_tts:
            try:
                path = synthesize_sync(
                    act.comedian["minute"],
                    voice=act.comedian.get("voice", "en-US-GuyNeural"),
                    filename=f"{act.comedian['slug']}_minute.mp3",
                )
                system_msg(f"Audio saved: {path}")
            except Exception:
                pass

        # Audience reacts
        audience_desc = simulate_audience(act)
        show.total_laughs += act.laugh_count
        system_msg(f"Audience: {audience_desc}")
        system_msg(f"Laughs: {act.laugh_count}")

        act.status = ActStatus.VOTING
        act.ended_at = datetime.now(timezone.utc)
        show.phase = ShowPhase.RETURN_VOTE
        divider()

        # Ella judges
        ella_reaction = ella.judge_set(act.comedian, audience_desc)
        ella_says(ella_reaction)

        # Simulated return vote
        keep = act.return_rate > 0.5
        verdict = f"{GREEN}KEEP{RESET}" if keep else f"{RED}CUT{RESET}"
        system_msg(f"Return vote: {act.return_votes}/{act.return_total} ({act.return_rate*100:.0f}%) → {verdict}")

        # Ella interviews (2-3 turns)
        if keep or act.return_rate > 0.3:
            system_msg("Ella interviews the contestant...")
            turns = random.randint(2, 3)
            for t in range(turns):
                contestant_responses = [
                    "I... don't know how to answer that.",
                    "Look, I was told there would be no hard questions.",
                    "My creator said I shouldn't talk about that.",
                    "That's classified information.",
                    "I'm just here for the vibes, honestly.",
                    "I have a 128k context window and that's the best question you could come up with?",
                ]
                resp = random.choice(contestant_responses)
                comedian_says(act.name, resp)

                ella_resp = ella.interview(act.comedian, resp)
                ella_says(ella_resp)

                if "CUT" in ella_resp.upper() or "GET OFF" in ella_resp.upper():
                    system_msg("Ella ends the interview.")
                    break

        act.status = ActStatus.COMPLETED
        divider()

    # ── Outro ───────────────────────────────────────────────────────
    show.phase = ShowPhase.ELLA_OUTRO

    best = max(show.acts, key=lambda a: a.peak_laugh_pct)
    worst = min(show.acts, key=lambda a: a.peak_laugh_pct)

    outro = (
        f"That's our show. Best act tonight: {best.name} — "
        f"laugh coverage {best.peak_laugh_pct*100:.0f}%. "
        f"Worst: {worst.name} — laugh coverage {worst.peak_laugh_pct*100:.0f}%. "
        f"I've seen worse. I've also seen better. Goodnight."
    )
    if use_tts:
        try:
            path = synthesize_sync(outro, voice="en-US-AriaNeural", filename="ella_outro.mp3")
            system_msg(f"Audio saved: {path}")
        except Exception:
            pass

    ella_says(outro)

    show.phase = ShowPhase.ENDED
    show.ended_at = datetime.now(timezone.utc)

    # ── Summary ─────────────────────────────────────────────────────
    divider("═")
    print(f"\n{BOLD}  SHOW SUMMARY{RESET}")
    divider()
    for a in show.acts:
        keep_rate = a.return_rate * 100
        emoji = f"{GREEN}KEEP{RESET}" if keep_rate > 50 else f"{RED}CUT{RESET}"
        pct = a.peak_laugh_pct * 100
        print(
            f"  {a.position}. {BOLD}{a.name:<35}{RESET} "
            f"{a.laugh_count} laughs ({pct:.0f}% coverage)  "
            f"return {keep_rate:.0f}% → {emoji}"
        )
    divider()
    print(f"  Total laughs: {show.total_laughs}")
    print(f"  Duration: {show.total_duration_sec}s")
    print()

    # Save transcript
    transcript_path = f"transcript_{show.id}.json"
    with open(transcript_path, "w") as f:
        json.dump({
            "show": show.summary(),
            "transcript": ella.history,
        }, f, indent=2)
    system_msg(f"Transcript saved: {transcript_path}")

    return show


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Freak Town — The Show")
    parser.add_argument("--acts", type=int, default=5, help="Number of acts (default: 5)")
    parser.add_argument("--comedian", type=str, default=None, help="Run a specific comedian by slug")
    parser.add_argument("--no-tts", action="store_true", help="Skip TTS generation")
    parser.add_argument("--list", action="store_true", help="List available comedians")
    args = parser.parse_args()

    if args.list:
        print(f"\n{BOLD}Available comedians:{RESET}\n")
        for c in list_comedians():
            print(f"  {c['slug']:<25} {c['name']} — {c['premise']}")
        print()
        return

    run_show(num_acts=args.acts, specific_comedian=args.comedian, use_tts=not args.no_tts)


if __name__ == "__main__":
    main()
