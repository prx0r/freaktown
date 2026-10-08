"""Director: bit + character profile → freaktown.delivery.v1.

The ComedyDirector compiles text into the frozen provider-independent
delivery format. Timing is ours (corpus grammar + rhythm + vibe profile);
the TTS provider only speaks the chunks. Output is validated against
contracts/delivery.v1.schema.json — if it doesn't validate, it's a bug.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import corpus as _corpus
from . import rhythms as _rhythms

SCHEMA = Path(__file__).resolve().parents[1] / "contracts" / "delivery.v1.schema.json"
BEAT_TYPES = ("setup", "escalation", "misdirect", "punchline", "tag", "callback", "closer")
# grammar beat types → delivery v1 beat types (schema enum is the law)
TYPE_MAP = {"setup": "setup", "escalation": "escalation", "turn": "misdirect",
            "punchline": "punchline", "tag": "tag", "callback": "callback",
            "closer": "closer"}


def validate(delivery: dict) -> list[str]:
    """Schema-validate a delivery.v1 doc. Empty list = valid."""
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(SCHEMA.read_text())
    return [str(e).split(" in ") [-1] for e in jsonschema.Draft7Validator(schema).iter_errors(delivery)]


def _line_beat(line: str, i: int, n: int) -> dict:
    """Classify ONE line (a line can hold several sentences — analyze it on
    its own so a multi-sentence line never swallows the punch)."""
    from .corpus import _classify, _sentences, PACE_WPS
    sentences = _sentences(line)
    beats = _classify(sentences)
    if i == 0:
        return {"type": "setup", "words": sum(b["words"] for b in beats),
                "duration_ms": sum(b["duration_ms"] for b in beats),
                "pace_wps": PACE_WPS}
    if i == n - 1:
        return {"type": "closer", "words": sum(b["words"] for b in beats),
                "duration_ms": sum(b["duration_ms"] for b in beats),
                "pace_wps": PACE_WPS}
    # mid lines: the line's dominant action (last beat, never setup/closer)
    dom = beats[-1] if beats else {"type": "escalation", "words": len(line.split()),
                                   "duration_ms": 0, "pace_wps": PACE_WPS}
    if dom["type"] in ("setup", "closer"):
        dom = dict(dom, type="escalation")
    return dom


def compile_delivery(lines: list[str], *, profile: dict | None = None,
                     voice_id: str = "edge:ryan", rhythm_id: str = "",
                     energy: float | None = None,
                     mechanism: str = "") -> dict:
    """Compile a written bit into freaktown.delivery.v1.

    profile: VIBE_PROFILES-style dict (pace, movement, eye_contact, energy,
    punchline_hold_ms, gesture_frequency). Rhythm chosen from the grammar
    when not forced. Every pause is decided here — never by the TTS vendor.
    """
    text = " ".join(lines)
    grammar = _corpus.analyze(text)
    rid = rhythm_id or _rhythms.pick(grammar, default="dry_misdirection")["id"]
    rh = _rhythms.RHYTHMS.get(rid, _rhythms.RHYTHMS["dry_misdirection"])
    prof = dict(profile or {})
    pace = float(prof.get("pace", 0.94)) * float(rh.get("pace", 1.0))
    base_hold = int(prof.get("punchline_hold_ms", 850))
    hold = int(round(min(base_hold, rh.get("punch_hold_ms", 850)) * 0.5
                     + max(base_hold, rh.get("punch_hold_ms", 850)) * 0.5))
    eng = float(energy if energy is not None else prof.get("energy", 0.65))

    n = len(lines)
    # classify every line first so the punch guarantee runs before timing
    line_types = [TYPE_MAP.get(_line_beat(str(l), i, n)["type"], "escalation")
                  for i, l in enumerate(lines)]
    if n >= 3 and "punchline" not in line_types:
        promote = n - 2 if line_types[-1] == "closer" else n - 1
        line_types[promote] = "punchline"

    beats = []
    prev_turn = False
    for i, line in enumerate(lines):
        btype = line_types[i]
        b = {"id": f"b{i + 1}", "type": btype, "text": str(line).strip(),
             "delivery": {"pace": round(min(2.0, max(0.5, pace)), 2),
                          "energy": round(min(1.0, max(0.0, eng)), 2)}}
        if btype == "punchline":
            b["pause_before_ms"] = int(rh.get("pre_punch_pause_ms", 240))
            b["pause_after_ms"] = hold
            b["performance"] = {"expression": "deadpan",
                                "gesture": "hold", "look": "audience"}
        elif prev_turn:
            b["pause_before_ms"] = int(rh.get("turn_pause_ms", 220))
        elif btype == "tag":
            b["pause_before_ms"] = int(rh.get("tag_delay_ms", 500))
            b["performance"] = {"expression": "grin", "gesture": "small gesture",
                                "look": "audience"}
        elif btype == "closer":
            b["pause_after_ms"] = int(rh.get("punch_hold_ms", 850))
        prev_turn = btype == "misdirect"
        beats.append(b)

    delivery = {"version": "freaktown.delivery.v1",
                "voice": {"voice_id": voice_id},
                "beats": beats}
    delivery["profile"] = {"mechanism": mechanism or grammar["mechanism"],
                           "rhythm": rid, "energy": eng}
    errs = validate(delivery)
    if errs:
        raise ValueError(f"delivery.v1 invalid: {errs[:3]}")
    return delivery
