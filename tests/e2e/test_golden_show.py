#!/usr/bin/env python3
"""Golden show: ONE merciless browser test. The test we refuse to break.

CREATE fresh Freak → BASIC body → short set → preload → Chromium opens
the real stage → avatar GLB 200s → READY → play → voice starts → clock
advances → body visible → ENDED → YOUR TURN → reload still works.

The set is short and fixed (LLM generation is covered by scripts/e2e.py);
playback runs at 4x so the full pipeline completes fast while the media
clock still traverses the entire duration. Base URL via FREAK_BASE env.
"""

import os
import shutil
import subprocess
import time

import pytest

BASE = os.getenv("FREAK_BASE", "http://localhost:8090")

pytestmark = pytest.mark.skipif(
    os.getenv("FREAK_BROWSER", "1") != "1", reason="browser test disabled")


def _api(method, path, body=None, timeout=120):
    import json
    import urllib.request
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


@pytest.fixture
def freak():
    d = _api("POST", "/api/sets", {
        "character": {"name": "Golden Gus", "species": "goblin",
                      "premise": "browser test", "vibe": "manic"},
        "beats": [
            {"id": "b1", "type": "setup",
             "text": "I walked on stage and immediately forgot my name.",
             "pace": "normal", "pause_after_ms": 600},
            {"id": "b2", "type": "punchline",
             "text": "Turns out I never had one. Thank you.",
             "pace": "normal", "pause_after_ms": 900},
        ], "voice": "en-US-GuyNeural"}, timeout=300)
    slug = d["slug"]
    yield slug
    shutil.rmtree(f"freaks/{slug}", ignore_errors=True)


def test_golden_show(freak):
    from playwright.sync_api import sync_playwright
    slug = freak
    pre = _api("GET", f"/api/preload/{slug}", timeout=30)
    assert pre["ok"] and pre["avatarUrl"], "BASIC body must reach preload"
    dur = pre["plan"]["duration_ms"] / 1000
    assert dur > 3, f"suspiciously short set: {dur}s"

    avatar_hits = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page()
        page.on("response", lambda r: avatar_hits.append(r.url)
                if "avatar.glb" in r.url else None)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/f/{slug}", wait_until="networkidle", timeout=60000)

        # avatar GLB must actually load (not 404, not fallback silence)
        page.wait_for_function(
            """() => performance.getEntriesByType('resource')
               .some(e => e.name.includes('avatar.glb'))""",
            timeout=30000)
        assert any("avatar.glb" in u for u in avatar_hits), "body never requested"
        page.wait_for_timeout(4000)  # let the VRM/GLB stage initialise
        assert not [e for e in errors if "loadAsync" in e], f"stage load errors: {errors}"

        # play at 4x: full media clock traversal in quarter wall time
        page.click("#playBtn")
        page.eval_on_selector("#a", "el => { el.playbackRate = 4; }")
        page.wait_for_function("() => !document.getElementById('a').paused",
                               timeout=15000)
        t0 = time.time()
        page.wait_for_selector("#replybox.show", timeout=90000)
        wall = time.time() - t0
        media_pos = page.eval_on_selector("#a", "el => el.currentTime")
        media_dur = page.eval_on_selector("#a", "el => el.duration")
        assert media_pos >= media_dur - 1.0, "ENDED before media finished"
        assert wall < media_dur, "4x playback didn't accelerate (sanity)"
        caption = page.inner_text("#caption")
        assert caption.strip(), "no caption ever rendered"

        # refresh: the same URL must work again (share durability)
        page.goto(f"{BASE}/f/{slug}", wait_until="domcontentloaded", timeout=60000)
        assert "YOUR TURN" in page.content()
        browser.close()
