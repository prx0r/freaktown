import json
import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

import server


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = server.SessionStore(Path(self.tmp.name))
        self.performer = {
            "name": "Test Freak",
            "slug": "test-freak",
            "premise": "Testing the stage",
            "minute": "A short test set.",
            "voice": "test",
            "avatar_url": "https://three.ws/avatars/michelle.glb",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_reactions_are_set_relative_and_session_scoped(self):
        first = self.store.create(self.performer, None, "browser")
        second = self.store.create(self.performer, None, "browser")
        self.store.record_reaction(first["session_id"], "laugh", 3.25, "tom")
        self.store.record_reaction(first["session_id"], "clap", 9.5, "tom")
        self.assertEqual(len(self.store.get(first["session_id"])["events"]), 2)
        self.assertEqual(len(self.store.get(second["session_id"])["events"]), 0)
        self.assertEqual(self.store.get(first["session_id"])["events"][0]["set_time_seconds"], 3.25)

    def test_completion_persists_structured_json(self):
        session = self.store.create(self.performer, None, "browser")
        sid = session["session_id"]
        self.store.record_reaction(sid, "laugh", 1.0)
        self.store.record_reaction(sid, "laugh", 6.0)
        self.store.record_reaction(sid, "clap", 6.2)
        done = self.store.complete(sid, 12.0)
        self.assertEqual(done["schema_version"], "freaktown.set.v1")
        self.assertEqual(done["summary"]["reaction_counts"], {"laugh": 2, "clap": 1, "total": 3})
        self.assertEqual(done["summary"]["active_5s_bins"], 2)
        saved = Path(self.tmp.name) / f"{sid}.json"
        self.assertTrue(saved.exists())
        self.assertEqual(json.loads(saved.read_text())["session_id"], sid)

    def test_invalid_reaction_is_rejected(self):
        session = self.store.create(self.performer, None, "browser")
        with self.assertRaises(ValueError):
            self.store.record_reaction(session["session_id"], "boo", 5)


class StaticContractTests(unittest.TestCase):
    def test_frontend_contains_three_ws_and_reaction_contract(self):
        html = (ROOT / "web" / "static" / "index.html").read_text()
        self.assertIn("three.ws/agent-3d/1.5.2/agent-3d.js", html)
        self.assertIn("/api/reaction", html)
        self.assertIn("set_time_seconds", html)
        self.assertIn("/api/complete", html)


if __name__ == "__main__":
    unittest.main()
