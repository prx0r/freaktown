#!/usr/bin/env python3
"""LiveKit adapter: roles, tokens, graceful degradation."""

import os

import livekit_adapter as LK


class TestLiveKit:
    def test_room_names_safe(self):
        assert LK.room_name("evt 123/abc!") == "freaktown-evt-123-abc"
        assert LK.room_name("") == "freaktown-lobby"

    def test_unconfigured_never_raises(self):
        for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
            os.environ.pop(k, None)
        assert LK.configured() is False
        try:
            LK.mint_token("x", "r")
            assert False, "should raise"
        except RuntimeError:
            pass

    def test_token_grants_per_role(self):
        os.environ.update({"LIVEKIT_URL": "wss://test.example",
                           "LIVEKIT_API_KEY": "key", "LIVEKIT_API_SECRET": "secret"})
        import jwt as _jwt  # noqa
        h = LK.mint_token("tom", "freaktown-x", "human")
        assert h["token"].count(".") == 2 and h["url"].startswith("wss://")
        # decode payload without verifying (structure check only)
        import base64, json
        pay = json.loads(base64.urlsafe_b64decode(h["token"].split(".")[1] + "=="))
        grants = pay.get("video", {})
        assert "CAMERA" in str(grants.get("canPublishSources", grants))
        p = LK.mint_token("caller", "freaktown-x", "phone")
        pay2 = json.loads(base64.urlsafe_b64decode(p["token"].split(".")[1] + "=="))
        assert "CAMERA" not in str(pay2["video"])
        try:
            LK.mint_token("x", "r", role="ghost")
            assert False
        except ValueError:
            pass
        for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
            os.environ.pop(k, None)
