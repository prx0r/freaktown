#!/usr/bin/env python3
"""Build one character set end-to-end (audio side): lines -> delivery.v1
-> TTS -> composed WAV -> timeline -> mouth cues.

Two inputs (FT-01: one canonical SetPlan, no copied text):
  --character ID   lines/voice/profile from p0-sets.json (rehearsal path)
  --setplan FILE   pog.setplan.v2 {character_id, approved_lines[], voice,
                   profile, premise, mechanism, status}; status must be
                   SCRIPT_APPROVED or the build refuses.

Timing authority (FT-03): the timeline is derived from the compositor's
measured spans, never predicted from raw TTS durations.

Usage:
  PYTHONPATH=. python3 scripts/build_set.py --character pog.doug-deadline --outdir data/p0/doug
  PYTHONPATH=. python3 scripts/build_set.py --setplan takes/kyle.plan.json --outdir data/takes/kyle
"""
import argparse
import asyncio
import json
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comedy.director import compile_delivery, validate  # noqa: E402
from puppet_qa import envelope_cues  # noqa: E402
from tts_provider import AudioChunk, AudioCompositor, get_provider  # noqa: E402


def load_source(a):
    if a.setplan:
        plan = json.load(open(a.setplan))
        if plan.get("schema") != "pog.setplan.v2":
            raise SystemExit("setplan schema must be pog.setplan.v2")
        if plan.get("status") != "SCRIPT_APPROVED":
            raise SystemExit(f"refusing: setplan status is {plan.get('status')}, need SCRIPT_APPROVED")
        return {"lines": plan["approved_lines"],
                "voice": plan.get("voice", "en-US-AriaNeural"),
                "profile": plan.get("profile", {"energy": 0.7, "pace": 0.95,
                                                "punchline_hold_ms": 850}),
                "premise": plan.get("premise", ""),
                "mechanism": plan.get("mechanism", plan.get("primary_mechanism", "escalation")),
                "intent": plan.get("audience_model", {}),
                "character": plan["character_id"], "mesh": plan.get("mesh", ""),
                "priors": {}, "source": {"setplan": a.setplan,
                                         "script_revision": plan.get("script_revision")}}
    sets = json.load(open("assets/character-meshes/cast/p0-sets.json"))["sets"]
    s = next(x for x in sets if x["character"] == a.character)
    life = json.load(open("assets/character-meshes/cast/lifecycle.json"))["characters"]
    entry = next(c for c in life if c["id"] == s["character"])
    cast = json.load(open("assets/character-meshes/cast/%s" % entry["cast"]))
    return {"lines": s["lines"], "voice": s["voice"], "profile": s["profile"],
            "premise": s["premise"], "mechanism": s["mechanism"],
            "intent": s["intent"], "character": s["character"],
            "mesh": entry["mesh"],
            "priors": cast.get("comedy", {}).get("operator_priors", {}),
            "source": {"p0-sets": a.character}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", default="")
    ap.add_argument("--setplan", default="")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    if bool(a.character) == bool(a.setplan):
        raise SystemExit("pass exactly one of --character / --setplan")
    os.makedirs(a.outdir, exist_ok=True)
    s = load_source(a)
    delivery = compile_delivery(s["lines"], profile=s["profile"],
                                voice_id="edge:x", mechanism=s["mechanism"])
    errs = validate(delivery)
    if errs:
        raise SystemExit(f"delivery invalid: {errs}")
    prov = get_provider("edge")
    chunks = []
    for b in delivery["beats"]:
        audio = asyncio.run(prov.generate(b["text"], s["voice"]))
        chunks.append(AudioChunk(audio=audio, beat_id=b["id"], beat_type=b["type"],
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
    open(os.path.join(a.outdir, "set.wav"), "wb").write(wav)
    with wave.open(os.path.join(a.outdir, "set.wav"), "rb") as w:
        total_ms = int(w.getnframes() / w.getframerate() * 1000)
    json.dump(timeline, open(os.path.join(a.outdir, "timeline.json"), "w"), indent=1)
    json.dump({"schema": "pog.setplan.v1", "character_id": s["character"],
               "mesh": s["mesh"], "premise": s["premise"],
               "mechanisms": s["priors"], "comic_intent": s["intent"],
               "delivery": delivery, "lines": s["lines"], "built_from": s["source"]},
              open(os.path.join(a.outdir, "set_plan.json"), "w"), indent=1)
    cues = envelope_cues(os.path.join(a.outdir, "set.wav"))
    json.dump(cues, open(os.path.join(a.outdir, "mouth_cues.json"), "w"), indent=1)
    print(f"BUILT {s['character']}: {total_ms/1000:.1f}s {len(cues)} cues -> {a.outdir}")


if __name__ == "__main__":
    main()
