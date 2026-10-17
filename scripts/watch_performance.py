#!/usr/bin/env python3
"""Watch a live performance like an SDK: screenshot on interval, Jev judges.

Endgame: an agent that WATCHES the show. Loop (from browser-use/jev-ultrafast,
adapted for a canvas stage where the screenshot IS the state):
  observe (CDP screenshot) -> decide (ONE Jev request, noul battery + Box)
  -> log events -> verify in code (never trust a DONE).

Box questions locate things (performer, mic, error banner) with coordinates;
noul questions judge state. ~$0.0001 per cycle. OPENROUTER_API_KEY = Jev only.

  OPENROUTER_API_KEY=... /usr/bin/python3 scripts/watch_performance.py <url> [--frames N] [--every SEC]
"""
import base64
import datetime
import json
import os
import sys
import urllib.request

MODEL = "typesafe/jev-1.14"
QUESTIONS = {
    "room_rendered": {"type": "noul",
                      "instructions": "Does the frame show a rendered 3D room interior?"},
    "performer_on_stage": {"type": "noul",
                           "instructions": "Is a performer character (person, creature, or avatar) on the stage?"},
    "page_error": {"type": "noul",
                   "instructions": "Is any error message visible?"},
    "performer_box": {"type": "box",
                      "instructions": "The performer character on the stage."},
    "mic_box": {"type": "box",
                "instructions": "The microphone stand."},
}


def cycle(pg, key, outdir, i):
    import base64 as _b64
    try:
        pg.screenshot(path=str(outdir / f"w{i}.png"), timeout=15000)
    except Exception:
        cdp = pg.context.new_cdp_session(pg)
        res = cdp.send("Page.captureScreenshot", {"format": "png"})
        (outdir / f"w{i}.png").write_bytes(_b64.b64decode(res["data"]))
    img = _b64.b64encode((outdir / f"w{i}.png").read_bytes()).decode()
    body = json.dumps({
        "model": MODEL,
        "state": [f"Live venue frame {i}:",
                  {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{img}"}}],
        "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/alpha/decisions", data=body,
        method="POST", headers={"Authorization": f"Bearer {key}",
                                 "Content-Type": "application/json",
                                 "HTTP-Referer": "https://funnier.si/",
                                 "X-Title": "freaktown-watch"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    ev = {"t": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "frame": i, "model": d.get("model"),
          "cost_usd": (d.get("usage") or {}).get("cost"),
          "answers": {k: v.get("noul", v.get("box"))
                      for k, v in d.get("answers", {}).items()}}
    return ev


def main():
    from pathlib import Path
    if len(sys.argv) < 2:
        print("usage: watch_performance.py <url> [--frames N] [--every SEC]",
              file=sys.stderr)
        return 2
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("REFUSING: OPENROUTER_API_KEY missing.", file=sys.stderr)
        return 2
    url, n, every = sys.argv[1], 3, 10
    for i, a in enumerate(sys.argv):
        if a == "--frames":
            n = int(sys.argv[i + 1])
        if a == "--every":
            every = int(sys.argv[i + 1])
    from playwright.sync_api import sync_playwright
    outdir = Path("/tmp/watch") / datetime.datetime.now().strftime("%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)
    log = outdir / "events.jsonl"
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox",
                                    "--use-gl=swiftshader",
                                    "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(15000)
        with open(log, "a") as f:
            for i in range(n):
                ev = cycle(pg, key, outdir, i)
                f.write(json.dumps(ev) + "\n")
                f.flush()
                a = ev["answers"]
                print(f"frame {i}: room={a.get('room_rendered')} "
                      f"performer={a.get('performer_on_stage')} "
                      f"error={a.get('page_error')} "
                      f"perf_box={a.get('performer_box')} "
                      f"cost=${ev['cost_usd']}")
                if i < n - 1:
                    pg.wait_for_timeout(every * 1000)
        b.close()
    print(f"log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
