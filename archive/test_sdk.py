#!/usr/bin/env python3
"""SDK: the game sees contestants, never minds."""

import asyncio
from pathlib import Path

from format_runtime import load_format
from sdk import (Action, AgentController, Character, CopilotController,
                 FormatContext, HumanController, Participant, ScriptedController,
                 run_match)

MANIFEST = load_format(Path(__file__).parent.parent.parent
                       / "formats" / "comedy.open-mic")
CTX = FormatContext("comedy.open-mic", "open", ["a", "b"])


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


class TestParticipantBlindness:
    def test_swap_controllers_same_receipt(self):
        def seats(ctrl_a, ctrl_b):
            return [Participant(Character("a", "A"), ctrl_a),
                    Participant(Character("b", "B"), ctrl_b),
                    Participant(Character("c", "C"), ScriptedController())]
        scores = {"open": {"contestant:a": 8.0, "contestant:b": 7.0,
                           "contestant:c": 6.0},
                  "final": {"contestant:a": 9.0, "contestant:b": 8.0}}
        r1 = run_match(MANIFEST, seats(ScriptedController(), ScriptedController()),
                       scores, event_id="e")["receipt"]
        r2 = run_match(MANIFEST, seats(
            AgentController(lambda p: {"kind": "submit"}, label="x"),
            HumanController()), scores, event_id="e")["receipt"]
        assert r1["results"] == r2["results"]
        assert r1["event_log_root"] == r2["event_log_root"]

    def test_receipt_leaks_no_minds(self):
        seats = [Participant(Character("a", "A"),
                             AgentController(lambda p: {}, label="Claude")),
                 Participant(Character("b", "B"), HumanController()),
                 Participant(Character("c", "C"), ScriptedController())]
        out = run_match(MANIFEST, seats,
                        {"open": {"contestant:a": 8.0, "contestant:b": 7.0,
                                  "contestant:c": 6.0},
                         "final": {"contestant:a": 9.0, "contestant:b": 8.0}},
                        event_id="e")
        blob = str(out["receipt"]) + str(out["events"])
        for word in ("Claude", "Human", "Scripted", "Agent", "controller"):
            assert word not in blob


class TestControllers:
    def test_human_queue_order(self):
        h = HumanController()
        h.push(Action("vote", {"for": "x"}))
        out = _run(Participant(Character("h", "H"), h).perform(
            Action("submit", {}), CTX))
        assert out["action"] == {"kind": "vote", "payload": {"for": "x"}}

    def test_agent_merges_payload(self):
        a = AgentController(lambda p: {"kind": "submit", "payload": {"score": 9}},
                            label="t")
        out = _run(Participant(Character("a", "A"), a).perform(
            Action("submit", {"round": "open"}), CTX))
        assert out["action"] == {"kind": "submit",
                                 "payload": {"round": "open", "score": 9}}

    def test_agent_exception_falls_back(self):
        def boom(prompt):
            raise RuntimeError("brain offline")
        a = AgentController(boom, label="t")
        out = _run(Participant(Character("a", "A"), a).perform(
            Action("submit", {"x": 1}), CTX))
        assert out["action"]["kind"] == "submit"

    def test_copilot_approval_wins(self):
        cop = CopilotController(
            AgentController(lambda p: {"kind": "submit", "payload": {"score": 1}}),
            HumanController())
        cop.human.push(Action("submit", {"score": 10}))
        out = _run(Participant(Character("c", "C"), cop).perform(
            Action("submit", {}), CTX))
        assert out["action"]["payload"] == {"score": 10}

    def test_copilot_timeout_approves_draft(self):
        cop = CopilotController(
            AgentController(lambda p: {"kind": "submit", "payload": {"score": 5}}),
            HumanController())
        out = _run(Participant(Character("c", "C"), cop).perform(
            Action("submit", {}), CTX))
        assert out["action"]["payload"] == {"score": 5}


class TestCharacter:
    def test_from_bundle(self):
        c = Character.from_bundle(
            "peg-1a2b3c",
            {"name": "Peg", "premise": "paranoid pigeon", "species": "pigeon",
             "vibe": "paranoid", "voice": "en-US-GuyNeural"},
            {"appearance": {"runtime": {"uri": "/freaks/x/avatar.glb",
                                        "format": "glb"}}})
        assert c.id == "peg-1a2b3c" and c.appearance["format"] == "glb"
        assert c.fingerprint() == c.fingerprint()

    def test_control_modes(self):
        assert Character("x", "X", control_mode="HUMAN").control_mode == "HUMAN"
        assert Character("y", "Y").control_mode == "AUTONOMOUS"


class TestMusicReading:
    def test_describe_matches_render(self):
        import sound_synth
        r = {"genre": "funk", "mood": "paranoid", "energy": "high",
             "shape": "hit", "duration": 10, "mode": "melody"}
        d = sound_synth.describe(r, 7)
        assert set(d["motif_sounded"]) <= set(d["motif"])
        assert len(d["motif"]) == 8 and len(d["motif_sounded"]) == 6
        assert d["bass_root"] == d["motif"][0]
        assert "118 BPM" in d["text"] and "Locrian" in d["text"]

    def test_event_shape(self):
        import sound_synth
        ev = sound_synth.music_event({"mood": "confident"}, seed=1)
        assert ev["type"] == "music.started"
        assert ev["payload"]["kind"] == "riff-groove"  # default mode

    def test_pattern_mode_described(self):
        import sound_synth
        d = sound_synth.describe({"genre": "funk", "mood": "absurd"}, 3)
        assert d["kind"] == "riff-groove" and "118 BPM" in d["text"]
