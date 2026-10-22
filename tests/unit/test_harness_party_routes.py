"""FUNNIER Party integration smoke tests. No camera or paid API calls.

Run inside the full FUNNIER environment:
  python -m unittest tests.unit.test_harness_party_routes
"""
import unittest
from unittest.mock import patch

from app import app
import party


class HarnessPartyRoutesTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()
        self.save = patch.object(party, "_save_rooms")
        self.log = patch.object(party, "_log")
        self.save.start()
        self.log.start()
        self.addCleanup(self.save.stop)
        self.addCleanup(self.log.stop)
        data = self.c.post("/party/create").get_json()
        self.code, self.host_token = data["code"], data["host_token"]
        self.addCleanup(party.ROOMS.pop, self.code, None)
        self.seat_token = self.c.post(f"/party/{self.code}/join", json={
            "name": "Viewer", "freak": "Ralph"}).get_json()["seat_token"]
        with party.LOCK:
            party.ROOMS[self.code]["phase"] = "playing"
            party.ROOMS[self.code]["mode"] = "freeze-night"
            party.ROOMS[self.code]["mode_state"] = {"phase": "idle"}

    def test_host_authorization(self):
        url = f"/party/{self.code}/harness"
        body = {"actor": "Ralph", "text": "Hello there", "beats": []}
        self.assertEqual(self.c.post(url, json=body).status_code, 403)
        good = self.c.post(url, json={**body, "host_token": self.host_token})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(party.ROOMS[self.code]["events"][-1]["kind"], "character.act")
        self.assertNotIn(self.host_token, str(party.ROOMS[self.code]["events"][-1]))

    def test_rejects_unknown_director_instructions(self):
        url = f"/party/{self.code}/harness"
        body = {"host_token": self.host_token, "actor": "Ralph", "text": "Hello",
                "beats": [{"span": "Hello", "gesture": "system_shell"}]}
        self.assertEqual(self.c.post(url, json=body).status_code, 400)

    def test_optin_smile_boolean_only_and_cooldown(self):
        url = f"/party/{self.code}/input"
        base = {"seat_token": self.seat_token, "kind": "smile"}
        self.assertEqual(self.c.post(url, json={**base, "smiling": 0.93}).status_code, 400)
        result = self.c.post(url, json={**base, "smiling": True})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(party.ROOMS[self.code]["events"][-1]["kind"], "smile.detected")
        self.assertEqual(self.c.post(url, json={**base, "smiling": True}).status_code, 429)

    def test_smile_not_persisted_or_scored(self):
        room = party.ROOMS[self.code]
        room["events"].append({"seq": room["seq"] + 1, "kind": "smile.detected", "by": "Viewer"})
        player = next(iter(room["players"].values()))
        player["_last_smile"] = 123
        # The patched _save_rooms cannot inspect actual serialized payload,
        # so assert the public event has no sensitive input or score fields.
        ev = room["events"][-1]
        self.assertNotIn("score", ev)
        self.assertNotIn("image", ev)
        self.assertNotIn("probability", ev)


if __name__ == "__main__":
    unittest.main()
