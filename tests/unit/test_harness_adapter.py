"""Offline contract tests for the Mutuals-style acting adapter."""
import unittest
from harness_adapter import compile_harness_beats, party_reaction


class HarnessAdapterTests(unittest.TestCase):
    def setUp(self):
        self.text = "The humans were the resources."
        self.words = [
            {"word": "The", "start_ms": 0, "end_ms": 150},
            {"word": "humans", "start_ms": 200, "end_ms": 500},
            {"word": "were", "start_ms": 520, "end_ms": 730},
            {"word": "the", "start_ms": 740, "end_ms": 840},
            {"word": "resources.", "start_ms": 900, "end_ms": 1250},
        ]

    def test_measured_punchline_timing(self):
        result = compile_harness_beats(self.text, [
            {"span": "The", "emotion": "neutral"},
            {"span": "resources.", "emotion": "deadpan", "camera": "push-in"},
        ], self.words)
        self.assertEqual(result["camera"], [{"at_ms": 900, "camera": "COMIC_CLOSE"}])
        self.assertEqual(result["motion"][1]["at_ms"], 900)
        self.assertEqual(result["timing"], "provided-word-offsets")

    def test_no_unavailable_body_gestures(self):
        result = compile_harness_beats(self.text, [
            {"span": "humans", "emotion": "happy", "gesture": "wave"}
        ], self.words, {"humanoid": False, "expressions": ["sad"]})
        self.assertEqual(result["motion"], [])
        self.assertEqual(len(result["warnings"]), 2)

    def test_fails_closed_on_word_drift(self):
        with self.assertRaisesRegex(ValueError, "alignment mismatch"):
            compile_harness_beats(self.text, [{"span": "resources"}], self.words[:-1])
        with self.assertRaisesRegex(ValueError, "span missing"):
            compile_harness_beats(self.text, [{"span": "imaginary words"}], self.words)

    def test_repeated_span_is_resolved_forward(self):
        text = "no no no"
        words = [{"word": "no", "start_ms": i*300, "end_ms": i*300 + 180}
                 for i in range(3)]
        result = compile_harness_beats(text, [
            {"span": "no", "gesture": "nod"},
            {"span": "no", "gesture": "nod"},
            {"span": "no", "gesture": "nod"},
        ], words)
        self.assertEqual([x["at_ms"] for x in result["motion"]], [0, 300, 600])

    def test_party_reaction_never_sets_score(self):
        self.assertIsNone(party_reaction("vote.accepted"))
        reply = party_reaction("smile.detected", smiling=True)
        self.assertEqual(reply["emotion"], "happy")
        self.assertNotIn("score", reply)


if __name__ == "__main__":
    unittest.main()
