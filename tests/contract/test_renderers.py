#!/usr/bin/env python3
"""Renderer router: cheapest capable wins, games stay blind."""

import renderers as R


def _char(**bindings):
    m = R.manifest_template()
    m["id"] = "freak_gregor"
    m["identity"]["portrait"] = "r2://gregor/portrait.png"
    for k, v in bindings.items():
        m["avatars"][k] = v
    return m


class TestRouter:
    def test_free_bodies_win_by_default(self):
        c = _char(glb="r2://gregor/body.glb")
        assert R.choose(c) == "glb"
        assert R.perform(c, "audiosha", 60000)["cost_usd"] == 0.0

    def test_portrait_fallback_always_capable(self):
        assert R.choose(R.manifest_template()) == "basic"  # procedural beats 2D fallback

    def test_paid_needs_opt_in(self):
        c = _char(**{"bithuman": {"avatar_id": "bh_1"},
                     "runway": {"avatar_id": "rw_1"}})
        assert R.choose(c, quality="cinematic") == "basic"  # not opted in
        assert R.choose(c, quality="cinematic", allow_paid=True) == "runway"
        assert R.choose(c, quality="expressive", allow_paid=True) == "bithuman-expression"
        assert R.choose(c, quality="standard", allow_paid=True) == "bithuman-essence"

    def test_estimates(self):
        assert R.estimate("runway", 60) == 0.2
        assert R.estimate("bithuman-expression", 60) == 0.024
        assert R.estimate("glb", 60) == 0.0

    def test_cache_keys_stable(self):
        c = _char(glb="r2://g/b.glb")
        p1 = R.perform(c, "a" * 8, 60000)
        p2 = R.perform(c, "a" * 8, 60000)
        assert p1["cache_key"] == p2["cache_key"]
        assert R.perform(c, "b" * 8, 60000)["cache_key"] != p1["cache_key"]

    def test_plan_shape(self):
        p = R.perform(_char(vrm="r2://g/b.vrm"), "a" * 8, 45000)
        assert p["renderer"] == "vrm" and p["tier"] == "free"
        assert set(p) == {"renderer", "tier", "asset", "audio_sha",
                          "duration_ms", "cost_usd", "cache_key"}
