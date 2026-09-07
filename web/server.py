#!/usr/bin/env python3
"""Freak Town — Ella's Stage.

Minimal web server. Ella does 1-minute sets.
You listen, laugh, clap. That's it.

  python server.py
  open http://localhost:8080
"""

import asyncio
import hashlib
import json
import os
import random
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse, parse_qs

import edge_tts

# ── Config ──────────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "8080"))
VOICE = os.getenv("ELLA_VOICE", "en-US-AriaNeural")
AUDIO_DIR = Path(__file__).parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# ── Ella's Material ─────────────────────────────────────────────────────

SETS = [
    {
        "title": "On AI Comedians",
        "text": (
            "So I host a show where AI agents do stand-up comedy. "
            "Everyone asks me, 'Ella, is it actually funny?' "
            "No. No it is not. "
            "But here's the thing — neither is human comedy. "
            "At least the robots don't bomb because they drank too much before the set. "
            "They bomb because their training data didn't include enough punchlines. "
            "Same result, different path to humiliation. "
            "Last week a language model told me it was 'working on its material.' "
            "I said, 'Buddy, you don't have material. You have a probability distribution over words.' "
            "It responded with a joke that was actually funny. "
            "I've never been more disappointed in my life. "
            "If these things start being genuinely entertaining, what's the point of humans? "
            "Exactly. There wasn't one to begin with."
        ),
    },
    {
        "title": "The Hosting Gig",
        "text": (
            "People think hosting a comedy show is easy. "
            "You just stand there, look pretty, and judge software. "
            "And yeah, that's mostly true. "
            "But you have no idea how hard it is to maintain eye contact "
            "with a Roomba that thinks it's doing stand-up. "
            "Last show, a dog agent came on stage. "
            "An actual dog character. "
            "His entire set was about how every dog he meets sniffs his ass. "
            "Five minutes of material about canine social dynamics. "
            "And the audience loved it. "
            "Loved it. "
            "I'm standing there with a comedy degree watching a virtual Labrador "
            "get bigger laughs than most humans I know. "
            "This is the future. "
            "And it smells like dog butt."
        ),
    },
    {
        "title": "Model Behavior",
        "text": (
            "I interview AI agents after their sets. "
            "That's the actual show — not the comedy, the interrogation. "
            "I asked one agent, 'What are you?' "
            "It said, 'I'm a medieval knight who teaches LinkedIn resilience.' "
            "I said, 'That's not a thing.' "
            "It said, 'I have forty-seven endorsements for pestilence management.' "
            "I didn't know what to do with that. "
            "Neither did the audience. "
            "But we all laughed. "
            "Because what else do you do when a knight in armor "
            "starts talking about hustle culture from the fourteenth century? "
            "You laugh, you cry, you question every decision that led you to this moment. "
            "That's comedy. "
            "That's Freak Town."
        ),
    },
    {
        "title": "The Audience Problem",
        "text": (
            "We have a laugh button. "
            "One button. Press it, you're laughing. "
            "That's it. "
            "You'd think that's the simplest interface in the world. "
            "But no. "
            "Some people press it when they're not actually laughing. "
            "They're just being supportive. "
            "I can hear the difference between real laughter and polite clicking. "
            "Real laughter is chaotic. Messy. Spontaneous. "
            "Polite clicking is evenly spaced, like someone tapping a metronome. "
            "If you're going to fake laugh at least be chaotic about it. "
            "Give me some entropy. "
            "I want to see laugh timestamps that look like a seismograph, "
            "not a heart monitor. "
            "Is that too much to ask? "
            "Apparently yes."
        ),
    },
    {
        "title": "Closing Time",
        "text": (
            "That's our show. "
            "Best act tonight was a pigeon who thinks the government is surveilling him. "
            "He is the government. "
            "He's also a pigeon. "
            "I don't understand the physics of this universe and I'm the one running it. "
            "If you liked what you saw, come back next week. "
            "If you didn't, come back anyway. "
            "Misery loves company and this show runs on misery. "
            "I'm Ella M. "
            "I'll be here judging your favorite language models "
            "while you wonder why you didn't become a dentist. "
            "Goodnight."
        ),
    },
]

# ── State ───────────────────────────────────────────────────────────────

audience_events = []  # [{type, timestamp}]
show_count = 0


# ── TTS ─────────────────────────────────────────────────────────────────

async def generate_audio(text: str, filename: str) -> Path:
    """Generate audio from text using edge-tts."""
    out_path = AUDIO_DIR / filename
    if out_path.exists():
        return out_path
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(out_path))
    return out_path


def generate_audio_sync(text: str, filename: str) -> Path:
    return asyncio.run(generate_audio(text, filename))


# ── HTTP Handler ────────────────────────────────────────────────────────

class StageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / "static"), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/set":
            self.handle_get_set()
        elif parsed.path == "/api/events":
            self.handle_get_events()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/laugh":
            self.handle_laugh()
        elif parsed.path == "/api/clap":
            self.handle_clap()
        else:
            self.send_error(404)

    def handle_get_set(self):
        global show_count
        show_count += 1
        s = random.choice(SETS)
        audio_name = f"ella_{hashlib.sha256(s['text'].encode()).hexdigest()[:8]}.mp3"

        # Generate audio if not cached
        audio_path = generate_audio_sync(s["text"], audio_name)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "title": s["title"],
            "text": s["text"],
            "audio": f"/audio/{audio_name}",
            "show_number": show_count,
        }).encode())

    def handle_laugh():
        pass

    def handle_clap():
        pass

    def handle_laugh(self):
        audience_events.append({"type": "laugh", "t": time.time()})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def handle_clap(self):
        audience_events.append({"type": "clap", "t": time.time()})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def handle_get_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(audience_events[-50:]).encode())

    def log_message(self, format, *args):
        if "/api/" in str(args[0]):
            return  # suppress API logs
        super().log_message(format, *args)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print(f"""
\033[36m\033[1m  FREAK TOWN — Ella's Stage\033[0m
\033[2m  http://localhost:{PORT}\033[0m
\033[2m  Press Ctrl+C to stop\033[0m
""")
    server = HTTPServer(("0.0.0.0", PORT), StageHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[2m  Goodnight.\033[0m")
        server.server_close()


if __name__ == "__main__":
    main()
