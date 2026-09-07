#!/usr/bin/env python3
"""Freak Town MCP server — Black Room tools.

The LLM driver writes the comedy. MCP does the stage work:
- detect_beats: split a minute into beats with pauses
- compose_minute: TTS each beat + exact silence -> WAV
- judge_minute: deterministic rubric score (no API key)
- list_voices / list_comedians / get_inspiration

Run via opencode MCP config (stdio):
  command: ["/root/freaktown/.venv/bin/python", "/root/freaktown/mcp_server.py"]

No API keys required. edge-tts is free. Timing is owned by the compositor.
"""

import asyncio
import hashlib
import io
import json
import random
import re
import struct
import subprocess
import wave
from pathlib import Path

from mcp.server.mcpserver import MCPServer

BASE = Path(__file__).parent
AUDIO_DIR = BASE / "audio_output"
AUDIO_DIR.mkdir(exist_ok=True)

server = MCPServer("freaktown")


# ── Beat detection (same rules as black_room.py) ────────────────────

def _detect_beats(text: str) -> list[dict]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    beats: list[dict] = []
    for i, sent in enumerate(sentences):
        wc = len(sent.split())
        btype, pause = "setup", 300
        if i > 0 and wc < 8 and len(sentences[i - 1].split()) > 15:
            btype, pause = "punchline", 800
        if i == len(sentences) - 1:
            btype = "closer"
            pause = 1200 if wc < 10 else 600
        if i > 0 and beats and beats[-1]["type"] == "punchline" and wc < 12:
            btype, pause = "tag", 400
        beats.append({
            "id": f"b{i + 1}",
            "type": btype,
            "text": sent,
            "pause_after_ms": pause,
            "word_count": wc,
        })
    return beats


# ── Deterministic rubric (no LLM) ───────────────────────────────────

def _judge(text: str) -> dict:
    words = text.split()
    wc = len(words)
    score = {"opening_hook": 1, "escalation": 1, "specificity": 1, "closer": 1, "voice": 1}

    first = text.split(".")[0] if "." in text else text[:80]
    if any(w in first.lower() for w in ["so i", "um", "like", "you know"]):
        score["opening_hook"] = 0
    elif first.strip()[:1].isupper() and len(first.split()) <= 15:
        score["opening_hook"] = 2

    if wc > 100:
        score["escalation"] = 2
    elif wc > 60:
        score["escalation"] = 1
    else:
        score["escalation"] = 0

    if any(c.isdigit() for c in text):
        score["specificity"] = 2
    elif wc > 50:
        score["specificity"] = 1
    else:
        score["specificity"] = 0

    sents = [s.strip() for s in text.split(".") if s.strip()]
    if sents:
        last_wc = len(sents[-1].split())
        score["closer"] = 2 if last_wc <= 10 else (1 if last_wc <= 20 else 0)

    score["voice"] = 2 if "you" in text.lower() else 1

    total = sum(score.values())
    verdict = str(min(5, max(1, total // 2)))
    notes = []
    if score["opening_hook"] == 0:
        notes.append("weak opener — start with a specific line, not filler")
    if score["closer"] == 2:
        notes.append("sharp closer")
    if score["specificity"] == 2:
        notes.append("concrete details land")
    if not notes:
        notes.append(f"fallback rubric ({total}/10)")
    return {**score, "total": total, "verdict": verdict, "notes": "; ".join(notes)}


# ── TTS + compositor ────────────────────────────────────────────────

async def _tts_wav(text: str, voice: str) -> bytes:
    import edge_tts

    tag = hashlib.sha256(f"{voice}:{text}".encode()).hexdigest()[:10]
    mp3 = AUDIO_DIR / f"_mcp_{tag}.mp3"
    wav_p = AUDIO_DIR / f"_mcp_{tag}.wav"
    await edge_tts.Communicate(text, voice).save(str(mp3))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", "-f", "wav", str(wav_p)],
        capture_output=True, timeout=15,
    )
    data = wav_p.read_bytes() if wav_p.exists() else b""
    mp3.unlink(missing_ok=True)
    wav_p.unlink(missing_ok=True)
    return data


def _wav_to_samples(wav_bytes: bytes) -> list[int]:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            frames = w.readframes(w.getnframes())
            return list(struct.unpack(f"<{len(frames) // 2}h", frames))
    except Exception:
        return []


def _samples_to_wav(samples: list[int], sr: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buf.getvalue()


VOICES = [
    {"id": "en-US-AriaNeural", "name": "Ella", "use": "host / female lead"},
    {"id": "en-US-GuyNeural", "name": "ChatGPT", "use": "guest judge"},
    {"id": "en-US-ChristopherNeural", "name": "Claude", "use": "guest judge"},
    {"id": "en-US-SamanthaNeural", "name": "Siri", "use": "robot stats"},
    {"id": "en-US-JoannaNeural", "name": "Alexa", "use": "accidentally helpful"},
]


# ── Tools ───────────────────────────────────────────────────────────

@server.tool()
def detect_beats(text: str) -> dict:
    """Split a comedy minute into beats (setup/punchline/tag/closer) with pause timings.
    Use this after writing or editing a minute, before composing audio."""
    beats = _detect_beats(text)
    total_ms = sum(b["pause_after_ms"] for b in beats) + len(beats) * 2000
    return {
        "beats": beats,
        "count": len(beats),
        "words": sum(b["word_count"] for b in beats),
        "estimated_ms": total_ms,
    }


@server.tool()
async def compose_minute(text: str, voice: str = "en-US-AriaNeural", pauses_json: str = "") -> dict:
    """TTS each beat then join with EXACT silence. Returns the WAV path and timing.
    pauses_json (optional): e.g. '{"b3": 1200}' to override pause_after_ms per beat.
    Freak Town owns timing — TTS only speaks the chunks."""
    beats = _detect_beats(text)
    if pauses_json.strip():
        try:
            overrides = json.loads(pauses_json)
            for b in beats:
                if b["id"] in overrides:
                    b["pause_after_ms"] = max(0, int(overrides[b["id"]]))
        except Exception:
            pass

    sr = 24000
    samples: list[int] = []
    for b in beats:
        wav = await _tts_wav(b["text"], voice)
        samples.extend(_wav_to_samples(wav))
        samples.extend([0] * int(sr * b["pause_after_ms"] / 1000))

    out = AUDIO_DIR / f"mcp_{hashlib.sha256(text.encode()).hexdigest()[:10]}.wav"
    out.write_bytes(_samples_to_wav(samples, sr))
    return {
        "audio_path": str(out),
        "duration_s": round(len(samples) / sr, 1),
        "beats": [{"id": b["id"], "type": b["type"], "pause_ms": b["pause_after_ms"]} for b in beats],
        "voice": voice,
    }


@server.tool()
def judge_minute(text: str) -> dict:
    """Score a minute on the 5-dimension rubric (hook/escalation/specificity/closer/voice).
    Deterministic, no API key. verdict maps to Kill Tony 1-5 scale."""
    return _judge(text)


@server.tool()
def list_voices() -> dict:
    """List TTS voices for host and guest judges."""
    return {"voices": VOICES}


@server.tool()
def list_comedians() -> dict:
    """List the 5 seed comedians with premise and voice."""
    import sys
    sys.path.insert(0, str(BASE))
    from comedians import ALL_COMEDIANS
    return {
        "comedians": [
            {"name": c["name"], "slug": c["slug"], "premise": c["premise"],
             "body": c["body"], "voice": c.get("voice", "")}
            for c in ALL_COMEDIANS
        ]
    }


@server.tool()
def get_inspiration() -> dict:
    """Random Ella set excerpt + one Kill Tony timing tip. Use when stuck."""
    import random as _r
    path = BASE / "ella_sets.md"
    text = path.read_text() if path.exists() else ""
    blocks = re.split(r"## \d+\.", text)[1:]
    pick = ""
    title = ""
    if blocks:
        b = _r.choice(blocks)
        lines = b.strip().split("\n")
        title = lines[0].strip().strip('"')
        body = [ln.strip() for ln in lines[1:]
                if ln.strip() and not ln.startswith(("---", ">", "Topics:"))]
        pick = " ".join(body)[:400]
    tips = [
        "5/5 sets average 2.82 words/sec — slower reads funnier than rushing.",
        "55% of 5/5 closers are under 8 words. End sharp.",
        "5/5 sets use ~3x more dashes/pauses than 1/5 sets.",
        "20% of 5/5 sets open with 'I' — personal beats abstract.",
        "First line IS the joke. No warmup.",
    ]
    return {"ella_excerpt_title": title, "ella_excerpt": pick, "timing_tip": _r.choice(tips)}


if __name__ == "__main__":
    server.run()
