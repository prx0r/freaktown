#!/usr/bin/env python3
"""Record a venue set server-side, publish to /takes ($0).

Headless Chromium plays the set (?nobg=1 for speed) while Playwright
records page video. Output: static/takes/take-<slug>-<ts>.webm + sidecar.
Watch at /takes on any phone — zero GPU needed on the viewer.

  /usr/bin/python3 scripts/record_set.py [venue] [set-slug]
"""
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "takes"


def main():
    venue = sys.argv[1] if len(sys.argv) > 1 else "tavern-test"
    body = ""
    for i, a in enumerate(sys.argv):
        if a == "--body" and i + 1 < len(sys.argv):
            body = sys.argv[i + 1]
    tag = "".join(c if c.isalnum() else "" for c in body.split("/")[-1].split(".")[0]) or "vrm"
    set_slug = "biscuit-4cb995"
    for i, a in enumerate(sys.argv):
        if a == "--set" and i + 1 < len(sys.argv):
            set_slug = sys.argv[i + 1]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%m%d-%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox",
                                    "--use-gl=swiftshader",
                                    "--enable-unsafe-swiftshader",
                                    "--autoplay-policy=no-user-gesture-required"])
        ctx = b.new_context(viewport={"width": 1280, "height": 800},
                            record_video_dir=str(OUT),
                            record_video_size={"width": 1280, "height": 800})
        pg = ctx.new_page()
        url = ("http://127.0.0.1:8090/venue/" + venue + "?style=mesh&set="
               + set_slug + ("&body=" + body if body else ""))
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(12000)
        t0 = time.time()
        pg.evaluate('document.getElementById("play").click()')
        click_lag = time.time() - t0
        # video record starts at page creation (~before goto returns);
        # audio starts at click. Offset audio back by the gap so mouths match.
        gap = 12.0 + click_lag
        dur = pg.evaluate('new Promise(res => { const a = new Audio("/freaks/' + set_slug + '/set.wav"); a.onloadedmetadata = () => res(a.duration); })')
        print(f"set {dur:.1f}s — recording…", flush=True)
        pg.wait_for_timeout((dur + 5) * 1000)
        print("audioOn:", pg.evaluate("window.__venueDbg.audioOn"),
              "| t:", round(pg.evaluate("window.__venueDbg.audioT"), 1))
        pg.close()
        b.close()
    vids = sorted(OUT.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    if not vids:
        print("NO VIDEO produced", file=sys.stderr)
        return 1
    raw = vids[-1]
    final = OUT / f"take-{venue}-{set_slug.split(chr(45))[0]}-{stamp}.webm"
    # mux the set audio under the silent page video (approx sync via gap).
    mixed = OUT / f"take-{venue}-{set_slug.split(chr(45))[0]}-{stamp}.mix.webm"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-i", str(raw), "-itsoffset", f"{gap:.2f}",
                        "-i", str(BASE / f"freaks/{set_slug}/set.mp3"),
                        "-c:v", "copy", "-c:a", "libvorbis",
                        "-shortest", str(mixed)])
    if r.returncode == 0 and mixed.stat().st_size > 100000:
        raw.unlink()
        mixed.rename(final)
        print(f"take+audio: {final.name} ({final.stat().st_size // 1024}KB)")
    else:
        raw.rename(final)
        print(f"take (silent fallback): {final.name}")
    final.with_suffix(".json").write_text(json.dumps({
        "take": final.name, "venue": venue, "set": "biscuit-4cb995",
        "recorded_at": stamp, "cost": "$0",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
