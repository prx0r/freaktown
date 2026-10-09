#!/usr/bin/env python3
"""Build one character set end-to-end (audio side): lines -> delivery.v1
-> TTS -> composed WAV -> timeline -> mouth cues.

Usage:
  python3 scripts/build_set.py --character pog.doug-deadline --outdir data/p0/doug

Reads lines/voice/profile from assets/character-meshes/cast/p0-sets.json
(voice verified against edge-tts). Writes set_plan.json, set.wav,
timeline.json, mouth_cues.json. No audience, no scores — rehearsal only.
"""
import argparse
import asyncio
import io
import json
import os
import wave

from comedy.director import compile_delivery, validate
from puppet_qa import envelope_cues
from tts_provider import AudioChunk, AudioCompositor, get_provider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    sets = json.load(open("assets/character-meshes/cast/p0-sets.json"))["sets"]
    s = next(x for x in sets if x["character"] == a.character)
    life = json.load(open("assets/character-meshes/cast/lifecycle.json"))["characters"]
    entry = next(c for c in life if c["id"] == s["character"])
    cast = json.load(open("assets/character-meshes/cast/%s" % entry["cast"]))
    delivery = compile_delivery(s["lines"], profile=s["profile"],
                                voice_id="edge:x", mechanism=s["mechanism"])
    errs = validate(delivery)
    if errs:
        raise SystemExit(f"delivery invalid: {errs}")
    prov = get_provider("edge")
    chunks, timeline, t = [], [], 0
    for b in delivery["beats"]:
        audio = asyncio.run(prov.generate(b["text"], s["voice"]))
        with wave.open(io.BytesIO(audio)) as w:
            ms = int(w.getnframes() / w.getframerate() * 1000)
        pb, pa = b.get("pause_before_ms", 0), b.get("pause_after_ms", 300)
        timeline.append({"beat_id": b["id"], "type": b["type"], "start_ms": t + pb,
                         "dur_ms": ms, "end_ms": t + pb + ms, "pause_after_ms": pa,
                         "text": b["text"], "performance": b.get("performance", {})})
        t += pb + ms + pa
        chunks.append(AudioChunk(audio=audio, beat_id=b["id"], beat_type=b["type"],
                                pause_after_ms=pa, pause_before_ms=pb))
    wav = AudioCompositor(sample_rate=24000).compose(chunks)
    open(os.path.join(a.outdir, "set.wav"), "wb").write(wav)
    json.dump(timeline, open(os.path.join(a.outdir, "timeline.json"), "w"), indent=1)
    json.dump({"schema": "pog.setplan.v1", "character_id": s["character"],
               "mesh": entry["mesh"],
               "premise": s["premise"],
               "mechanisms": cast.get("comedy", {}).get("operator_priors", {}),
               "comic_intent": s["intent"], "delivery": delivery, "lines": s["lines"]},
              open(os.path.join(a.outdir, "set_plan.json"), "w"), indent=1)
    cues = envelope_cues(os.path.join(a.outdir, "set.wav"))
    json.dump(cues, open(os.path.join(a.outdir, "mouth_cues.json"), "w"), indent=1)
    print(f"BUILT {a.character}: {t/1000:.1f}s {len(cues)} cues -> {a.outdir}")


main()
