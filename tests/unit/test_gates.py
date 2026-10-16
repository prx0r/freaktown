"""Gates + theory-driven adapter: vetoes fire, pregate routes, drafts validate."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from comedy.gates import taboo_check, pregate
from comedy.director import validate
import premise_to_lines as adapter

SPEC = {"id": "pog.test", "name": "Testfinch",
        "contradictions": [{"engine": "counts everything twice"},
                           {"engine": "loses the list"},
                           {"engine": "audits the applause"}],
        "callback_hooks": ["the ledger incident"],
        "voice": {"cadence": " brisk "}}


def test_taboo_blocks_down_punch_mock():
    v = taboo_check({"lines": ["you people are idiots"], "target": None,
                     "stance": "mock", "punch_direction": "down"})
    assert any("power_direction" in x for x in v)


def test_taboo_blocks_child_target():
    v = taboo_check({"lines": ["kids these days"], "target": "kids",
                     "stance": "mock", "punch_direction": "lateral",
                     "technique": "x"})
    assert any("smut_check" in x for x in v)


def test_taboo_passes_clean_lateral():
    v = taboo_check({"lines": ["the committee adjourned early"], "target": None,
                     "stance": "neutral", "punch_direction": "lateral",
                     "technique": "snowball_chain"})
    assert v == []


def test_pregate_drop_without_turn():
    assert pregate({"playful_turn": False, "motive_consistency_0_9": 7})["verdict"] == "DROP"


def test_pregate_reframe_marginal():
    assert pregate({"playful_turn": True, "motive_consistency_0_9": 5})["verdict"] == "REFRAME"


def test_pregate_pass():
    assert pregate({"playful_turn": True, "motive_consistency_0_9": 7})["verdict"] == "PASS"


def test_every_operator_builds_valid_delivery():
    from comedy.director import compile_delivery
    premise = "Laundry as a quarterly review."
    for op in ("snowball_chain", "register_transpose", "inversion_recoil",
               "repeat_variation", "displace_emphasis", "represent_opposite",
               "interference_coincide", "condense_composite", "multiple_use",
               "unify_repartee", "faulty_syllogism_facade", "absurd_allusion"):
        lines = adapter.SHAPERS[op](dict(SPEC), premise)
        assert len(lines) == 6, op
        d = compile_delivery(lines, profile={"energy": 0.7, "pace": 0.95,
                                             "punchline_hold_ms": 850},
                             voice_id="edge:x", mechanism=op)
        assert validate(d) == [], op
        assert len(d["beats"]) == 6, op


def test_judge_rejects_punchless():
    s = adapter.judge_draft(["one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"] * 6,
                            "snowball_chain")
    assert "weak_punchline" in s["fail"] or s["score"] < 0.8


def test_reflect_trims_bloated():
    long_lines = ["word " * 40 for _ in range(6)]
    out, fixed = adapter.reflect(long_lines)
    assert fixed and sum(len(l.split()) for l in out) < sum(len(l.split()) for l in long_lines)


def test_critic_elements_bounded():
    els = adapter.critic_elements(["alpha beta gamma"] * 6, "snowball_chain")
    assert els and all(len(e["statement"].split()) <= 25 for e in els)
