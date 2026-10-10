#!/usr/bin/env python3
"""Premise-to-lines adapter v2: theory operates, then lines exist.

Planner -> Writer (best-of-N) -> pregates -> Reflector (one repair)
-> Judge (closed vocab) -> director compile + validate.
Follows the RAGthoven shape (fixed path, no branching sprawl) and the
mined shelf (operators-v2, gtvh-fields, taboo-gates, scene-pregate,
judge-protocol). Delivery.v1 stays frozen; drafts stay drafts.

  PYTHONPATH=. python3 scripts/premise_to_lines.py --character pog.doug-deadline \\
      --premise "Laundry as a quarterly review." --mechanism snowball_chain [--polish]
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from comedy.director import compile_delivery, validate  # noqa: E402
from comedy.corpus import _classify  # noqa: E402
from comedy.evaluator import predict as e_predict  # noqa: E402
from comedy.gates import taboo_check, pregate  # noqa: E402

MINED = os.path.join(HERE, "comedy", "theory", "mined")
_OPS_DOC = json.load(open(os.path.join(MINED, "operators-v2.json")))
OPS = {o["id"]: o for o in _OPS_DOC.get("new_operators", []) + _OPS_DOC.get("refinements", [])}
MECH_ALIAS = {"escalation": "snowball_chain", "rigidify": "register_transpose",
              "rigidity": "register_transpose", "status_reversal": "inversion_recoil",
              "misdirection": "displace_emphasis", "callback": "repeat_variation",
              "irony": "represent_opposite", "deadpan": "register_transpose"}


def cast_spec(character):
    for f in glob.glob(os.path.join(HERE, "assets", "character-meshes", "cast", "*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("id") == character:
            return d
    sys.exit("no cast spec for " + character)


def _engines(spec):
    c = [(x.get("engine") or "") for x in spec.get("contradictions", [])]
    while len(c) < 3:
        c.append("it gets worse in exactly the expected way")
    return c[:3]


def _hook(spec):
    hooks = spec.get("callback_hooks", []) or ["the incident (never discussed)"]
    h = hooks[0]
    return h[0].upper() + h[1:]


# Operator shapers: mechanism instruction -> 6 ordered lines.
def _snowball(spec, premise):
    e = _engines(spec)
    return [f"Good evening. Tonight: {premise} {spec.get('name','')} presiding, feelings will be minuted.",
            f"First: {e[0]} Logged.",
            f"Then: {e[1]} Which caused the first thing, again, but bigger.",
            f"Finally: {e[2]} Full circle. The policy now requires itself.",
            "And yet I remain the reasonable one here. That is the tragedy.",
            f"We adjourn. {_hook(spec)}. Goodnight."]


def _register(spec, premise):
    e = _engines(spec)
    return [f"Notice of proceedings: {premise} Matter ref 11:59.",
            f"Finding one. {e[0]} Entered into the record.",
            f"Finding two. {e[1]} Cross-filed under feelings, subsection C.",
            f"Finding three. {e[2]} No further correspondence will be entered into.",
            "The procedure is disappointed in all of us, but mostly in you.",
            f"Hearing closed. {_hook(spec)}. Costs awarded against the room."]


def _inversion(spec, premise):
    e = _engines(spec)
    return [f"Tonight I am the audience and you are the {premise} Frankly you look tired.",
            f"Exhibit one. {e[0]} How does it feel from that side?",
            f"Exhibit two. {e[1]} Still funny? Nod for the minutes.",
            f"Ruling. {e[2]} The trap has recoiled. The trap always recoils.",
            "I take no pleasure in this. The minutes will show otherwise.",
            f"Adjourned. {_hook(spec)}. Somebody fetch my gavel."]


def _repeat(spec, premise):
    e = _engines(spec)
    return [f"Three identical evenings. First: {premise} Doors at seven.",
            f"Second evening, lower key. {e[0]} Same combination, fresh faces.",
            f"Third evening, basement. {e[1]} You laughed before you meant to.",
            f"Encore, unasked. {e[2]} Recognition, then the break.",
            "You see the pattern. The pattern sees you.",
            f"Curfew. {_hook(spec)}. Never the words, always the combination."]


def _sideways(spec, premise):
    e = _engines(spec)
    return [f"You asked about {premise} Lovely question. Next question.",
            f"Beside the point entirely: {e[0]} Moving on.",
            f"Adjacent matter: {e[1]} Which answers everything except what you asked.",
            f"Footnote to the margin: {e[2]} The direct version would have been flat.",
            "I have answered with great precision. Precision adjacent.",
            f"Correspondence ends. {_hook(spec)}. Directness is for the brave."]


def _opposite(spec, premise):
    e = _engines(spec)
    return [f"{premise} Flawless. A triumph. No notes. None.",
            f"Praise item one. {e[0]} Magnificent in its way.",
            f"Praise item two. {e[1]} If ugliness were currency, we are rich.",
            f"Commendation. {e[2]} Cleanliness of this order convicts us all.",
            "I love it here. The record will show love.",
            f"Ceremony ends. {_hook(spec)}. Ugliness praised, duty done."]


def _coincide(spec, premise):
    e = _engines(spec)
    return [f"Two plans tonight. Mine: {premise} Yours: unknown. Coincidence scheduled.",
            f"Series A: {e[0]} Perfectly innocent.",
            f"Series B: {e[1]} Also innocent. Separately.",
            f"Coincidence: both readings true at once. {e[2]} Each of us sees one.",
            "You heard a confession. I gave directions. Both happened.",
            f"Scene ends. {_hook(spec)}. Same words, two verdicts."]


def _fuse(spec, premise):
    e = _engines(spec)
    return [f"One word tonight covers everything: {premise} I have fused it. You are welcome.",
            f"Compound one. {e[0]} Compressed.",
            f"Compound two. {e[1]} The compression is the joke. Say it fast.",
            f"Compound three. {e[2]} Shorter still. Meaning now dense as fruitcake.",
            "Unpack that and it dies. So don't.",
            f"Dictionary closed. {_hook(spec)}. One word covered it all."]


def _double(spec, premise):
    e = _engines(spec)
    return [f"{premise} Means one thing. Also means the other. Both intended.",
            f"Reading one, innocent. {e[0]} A clean minute.",
            f"Reading two, less innocent. {e[1]} Same words. Your mind did that.",
            f"Both readings live. {e[2]} Kinship of senses, certified.",
            "I said what I said. You heard what you heard. We are both correct.",
            f"Hearing adjourned. {_hook(spec)}. The pun stands as read."]


def _repartee(spec, premise):
    e = _engines(spec)
    return [f"An attack arrived regarding {premise} I accept it. Same coin ready.",
            f"Their charge: {e[0]} Noted.",
            f"My change: {e[1]} Same frame. Same coin.",
            f"Counter: {e[2]} Paid back exactly. No new topic required.",
            "Tu quoque, with receipts. The room keeps the change.",
            f"Bout over. {_hook(spec)}. Attack and defense shared the frame."]


def _facade(spec, premise):
    e = _engines(spec)
    return [f"Logic tonight, rigorous. Premise: {premise} Conclusion: inevitable.",
            f"Step one, sound. {e[0]} Granted.",
            f"Step two, load-bearing. {e[1]} Do not inspect step two.",
            f"Therefore: {e[2]} The facade held. The flaw held more.",
            "Expose the flaw and the moral remains. That was the trick.",
            f"QED. {_hook(spec)}. Flaw survivable only while distracted."]


def _allude(spec, premise):
    e = _engines(spec)
    return [f"On {premise} I cite only the classics. Nonsense, but cited.",
            f"As the saying goes: {e[0]} Source: trust me.",
            f"Further: {e[1]} Allusion does the ridiculing so I don't have to.",
            f"Finally: {e[2]} The direct statement would have been flat.",
            "I have criticized nothing. The citation did it.",
            f"Session cited. {_hook(spec)}. Indirection bribed your criticism."]


SHAPERS = {"snowball_chain": _snowball, "register_transpose": _register,
           "inversion_recoil": _inversion, "repeat_variation": _repeat,
           "displace_emphasis": _sideways, "represent_opposite": _opposite,
           "interference_coincide": _coincide, "condense_composite": _fuse,
           "multiple_use": _double, "unify_repartee": _repartee,
           "faulty_syllogism_facade": _facade, "absurd_allusion": _allude}


def plan_so(spec, premise, op):
    contra = (spec.get("contradictions") or [{}])[0]
    return {"text_specific": [contra.get("a", "order"), contra.get("b", "collapse")],
            "overlap_span": premise,
            "operator": op, "operator_instruction": OPS[op]["instruction"]}


def draft_features(lines):
    beats = _classify(lines)
    types = [b["type"] for b in beats]
    return {"beats": beats, "has_turn": "turn" in types,
            "has_punch": "punchline" in types,
            "words": sum(b["words"] for b in beats)}


def judge_draft(lines, mechanism):
    """Closed-vocab scoring: structure + mechanism + diagnostic. Deterministic."""
    feats = draft_features(lines)
    grammar = {"beats": feats["beats"], "total_words": feats["words"],
               "mechanism": {"snowball_chain": "escalation",
                             "repeat_variation": "callback",
                             "displace_emphasis": "misdirection"}.get(mechanism, "absurd")}
    pred = e_predict(grammar)
    score = pred["predicted_laugh"]
    fail = []
    if not feats["has_punch"]:
        fail.append("weak_punchline")
    if feats["words"] > 240:
        fail.append("overexplained")
    if feats["words"] < 60:
        fail.append("weak_punchline")
    return {"score": round(score, 2), "fail": fail,
            "mechanisms": [grammar["mechanism"]],
            "delivery": ["conciseness" if feats["words"] <= 180 else "overexplained",
                         "escalation" if mechanism == "snowball_chain" else "framing_commitment"]}


def reflect(lines):
    """One repair pass: trim the longest non-punch beat, nothing cleverer."""
    beats = _classify(lines)
    if sum(b["words"] for b in beats) <= 200 and any(b["type"] == "punchline" for b in beats):
        return lines, False
    out, trimmed = [], False
    for i, line in enumerate(lines):
        words = line.split()
        if len(words) > 30 and i < len(lines) - 2 and not trimmed:
            out.append(" ".join(words[:24]) + ".")
            trimmed = True
        else:
            out.append(line)
    return out, trimmed


def critic_elements(lines, mechanism):
    """Losing-draft explanation units: <=25 words, one fact, never bundled."""
    els, kinds = [], ["implication", "norm_violation", "reference", "wordplay"]
    for i, line in enumerate(lines[:4]):
        w = line.split()
        els.append({"element_id": f"DRAFT-E{i+1}",
                    "statement": " ".join(w[:22]),
                    "type": kinds[i % len(kinds)],
                    "mechanism": mechanism})
    return els


def polish(lines, spec):
    prompt = ("Rewrite these %d stand-up lines in the voice of %s. Keep exactly %d lines, "
              "same order and roles. Make no new factual claims. Reply with the lines only, "
              "one per line.\n\n%s"
              % (len(lines), spec.get("name", ""), len(lines),
                 "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))))
    r = subprocess.run(["ollama", "run", "hermes3:8b", prompt],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return lines, False
    out = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    if len(out) != len(lines):
        return lines, False
    return out, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--premise", required=True)
    ap.add_argument("--mechanism", default="snowball_chain")
    ap.add_argument("--drafts", type=int, default=3)
    ap.add_argument("--polish", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    op = MECH_ALIAS.get(a.mechanism, a.mechanism)
    if op not in OPS:
        sys.exit(f"unknown mechanism {a.mechanism} (have: {sorted(OPS)})")
    spec = cast_spec(a.character)
    so = plan_so(spec, a.premise, op)
    shaper = SHAPERS.get(op, _snowball)
    # Writer: best-of-N (rotate which contradiction leads)
    candidates = []
    for n in range(max(1, a.drafts)):
        rot = dict(spec)
        rot["contradictions"] = (spec.get("contradictions", []) or [])[n:] + \
            (spec.get("contradictions", []) or [])[:n] or spec.get("contradictions", [])
        candidates.append(shaper(rot, a.premise))
    # Pregates: taboo vetoes + play-mirth (turn detected = playful turn evidence)
    scene_base = {"motive_consistency_0_9": 6, "target_stance": "lateral",
                  "motive_type": "reward", "familiarity_0_1": 0.3}
    judged = []
    for lines in candidates:
        feats = draft_features(lines)
        scene = dict(scene_base, playful_turn=feats["has_turn"] or feats["has_punch"])
        pg = pregate(scene)
        vetoes = taboo_check({"lines": lines, "target": None, "stance": "neutral",
                              "punch_direction": "lateral", "technique": op})
        judged.append({"lines": lines, "pregate": pg["verdict"], "vetoes": vetoes})
    alive = [j for j in judged if j["pregate"] == "PASS" and not j["vetoes"]]
    pool = alive or [j for j in judged if j["pregate"] in ("PASS", "REFRAME")]
    if not pool:
        print(json.dumps({"verdict": "ALL-DROPPED", "detail": judged}, indent=1)[:1500])
        sys.exit("every draft dropped at the pregate — premise or stance needs rework")
    # Judge (closed vocab) + one reflector repair on the winner
    scored = [(judge_draft(j["lines"], op)["score"], j) for j in pool]
    scored.sort(key=lambda x: -x[0])
    winner = scored[0][1]
    Repaired, fixed = reflect(winner["lines"])
    winner["lines"] = Repaired
    wscore = judge_draft(winner["lines"], op)
    losers = [carbon for _, carbon in scored[1:]]
    lines = winner["lines"]
    polished = False
    if a.polish:
        lines, polished = polish(lines, spec)
    profile = {"energy": 0.7, "pace": 0.95, "punchline_hold_ms": 850}
    delivery = compile_delivery(lines, profile=profile, voice_id="edge:x", mechanism=op)
    errs = validate(delivery)
    doc = {"character": a.character, "premise": a.premise, "mechanism": op,
           "script_opposition": so, "polished": polished, "repaired": fixed,
           "pregate": winner["pregate"],
           "judge": {"winner_score": wscore["score"], "winner_mechanisms": wscore["mechanisms"],
                     "winner_delivery": wscore["delivery"], "winner_fail": wscore["fail"],
                     "losers": len(losers)},
           "critic_elements": [e for L in losers for e in critic_elements(L["lines"], op)],
           "lines": lines, "delivery_beats": len(delivery.get("beats", [])),
           "validation": errs}
    if a.out:
        json.dump(doc, open(a.out, "w"), indent=1)
    print(json.dumps({k: doc[k] for k in ("mechanism", "pregate", "judge", "polished",
                                          "repaired", "delivery_beats", "validation")}))
    print("VERDICT:", "DRAFT-OK" if not errs else "NEEDS-WORK",
          "- review aloud before p0-sets", file=sys.stderr)


if __name__ == "__main__":
    main()
