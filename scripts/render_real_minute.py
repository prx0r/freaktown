#!/usr/bin/env python3
"""Render a REAL comedian minute (Louis c04) into a funnier freak pack.

Source: /root/characters voicelab louis_decomp (text + technique + laugh
flags) + timing_profile Louis pause ladder (setup 0.7 / pre-punch 1.7 /
tag 1.0). Fish s2.1-pro-free renders per beat with expression cues.
Output: freaks/louis-c04/{delivery.json,set.wav,set.mp3,meta.json}.

Fish spend: ~190 words, fractions of a cent (owner-instructed render).

  FISH_API_KEY=... /usr/bin/python3 scripts/render_real_minute.py
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/root/characters/audition")
import fish_tts

TECH_EXPR = {"audience_address": "grin", "literalize": "deadpan",
             "self_deprecation": "exhausted", "escalation": "manic"}
PAUSE_AFTER = {"opener": 700, "setup": 700, "punchline": 1700,
               "tag": 1000, "closer": 1500}


def main():
    if not fish_tts.get_key():
        print("REFUSING: FISH_API_KEY missing.", file=sys.stderr)
        return 2
    d = json.loads(open("/root/characters/audition/voicelab/"
                        "louis_decomp_louis_c04.json").read())
    rows = d["rows"]
    beats = []
    for i, r in enumerate(rows):
        tech = r.get("technique", "")
        if i == 0:
            bt = "opener"
        elif i == len(rows) - 1:
            bt = "closer"
        elif tech in ("escalation", "literalize"):
            bt = "punchline"
        elif tech == "self_deprecation":
            bt = "tag"
        else:
            bt = "setup"
        beats.append({
            "id": f"b{i + 1}", "type": bt, "text": r["text"],
            "performance": {"expression":
                            TECH_EXPR.get(tech, "neutral")},
            "speech": {"emphasis": 0.9 if bt in ("punchline", "closer") else 0.5},
            "pause_after_ms": PAUSE_AFTER[bt],
        })
    out = BASE / "freaks" / "louis-c04"
    out.mkdir(parents=True, exist_ok=True)
    parts = []
    tmp = out / "_beats"
    tmp.mkdir(exist_ok=True)
    for b in beats:
        r = fish_tts.render_beat("louis-c04", b)
        mp3 = Path(r["path"])
        w = tmp / (b["id"] + ".wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-i", str(mp3), str(w)], check=True)
        parts.append(w)
        parts.append(fish_tts.silence_wav(b["pause_after_ms"]))
    for f in tmp.glob("*.wav"):
        pass
    fish_tts.stitch_wav(parts, out / "set.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(out / "set.wav"), str(out / "set.mp3")],
                   check=True)
    (out / "delivery.json").write_text(json.dumps(
        {"version": 1, "beats": beats}, indent=2))
    (out / "meta.json").write_text(json.dumps(
        {"comedian": "louis (text+timing; voice: fish default, no CK clone exists)",
         "source": "characters voicelab louis_decomp_louis_c04",
         "beats": len(beats)}, indent=2))
    (out / "character.json").write_text(json.dumps(
        {"name": "louis-c04", "premise": "broke — real Louis minute"}, indent=2))
    print(f"louis-c04: {len(beats)} beats, "
          f"{(out/'set.wav').stat().st_size//1024}KB wav + mp3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
