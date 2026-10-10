#!/usr/bin/env python3
"""A01 bridge: characters-foundry delivery.json -> P0-style audio take.

Input:  a foundry freak dir (delivery.json + character.json + meta.json),
        validated against freaktown.delivery.v1 upstream by hand.
Output: outdir with set.wav, timeline.json, mouth_cues.json, take_manifest.json
        (same shape scripts/build_set.py emits, so render/QA/mux/studio work).

Nothing here invents timing: TTS is measured, the compositor owns silence
(with edge-trim, see tts_provider.AudioCompositor). Usage:
  PYTHONPATH=. python3 scripts/delivery_to_take.py \\
      --freak /home/ubuntu/characters/freaks/kappa-kyle-cucumber-debt \\
      --outdir data/takes/kappa-kyle-cucumber-debt
"""
import argparse
import asyncio
import json
import os
import sys
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from tts_provider import AudioChunk, AudioCompositor, get_provider  # noqa: E402
from puppet_qa import envelope_cues  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freak", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    delivery = json.load(open(os.path.join(a.freak, "delivery.json")))
    character = json.load(open(os.path.join(a.freak, "character.json")))
    meta = json.load(open(os.path.join(a.freak, "meta.json")))
    voice = delivery.get("voice", {}).get("voice_id", "en-US-AriaNeural")
    prov = get_provider("edge")
    chunks = []
    for b in delivery["beats"]:
        audio = asyncio.run(prov.generate(b["text"], voice))
        chunks.append(AudioChunk(audio=audio, beat_id=b["id"],
                                beat_type=b.get("type", "setup"),
                                pause_after_ms=int(b.get("pause_after_ms", 300) or 0),
                                pause_before_ms=int(b.get("pause_before_ms", 0) or 0)))
    comp = AudioCompositor(sample_rate=24000)
    wav, spans = comp.compose_with_spans(chunks)
    by_id = {b["id"]: b for b in delivery["beats"]}
    timeline = [{"beat_id": sp["beat_id"], "type": by_id[sp["beat_id"]].get("type", "setup"),
                 "start_ms": sp["start_ms"], "dur_ms": sp["dur_ms"], "end_ms": sp["end_ms"],
                 "pause_before_ms": sp["pause_before_ms"], "pause_after_ms": sp["pause_after_ms"],
                 "text": by_id[sp["beat_id"]]["text"],
                 "performance": by_id[sp["beat_id"]].get("performance", {})}
                for sp in spans]
    wav_path = os.path.join(a.outdir, "set.wav")
    open(wav_path, "wb").write(wav)
    with wave.open(wav_path, "rb") as w:
        total_ms = int(w.getnframes() / w.getframerate() * 1000)
    json.dump(timeline, open(os.path.join(a.outdir, "timeline.json"), "w"), indent=1)
    cues = envelope_cues(wav_path)
    json.dump(cues, open(os.path.join(a.outdir, "mouth_cues.json"), "w"), indent=1)
    json.dump({"take": "foundry-ingest-v1",
               "character": character.get("name", meta.get("slug")),
               "canon_root": (meta.get("lineage") or {}).get("root"),
               "voice": voice, "beats": len(timeline),
               "duration_s": round(total_ms / 1000, 1), "mouth_cues": len(cues)},
              open(os.path.join(a.outdir, "take_manifest.json"), "w"), indent=1)
    print(f"BUILT {meta.get('slug')}: {total_ms/1000:.1f}s {len(cues)} cues -> {a.outdir}")


if __name__ == "__main__":
    main()
