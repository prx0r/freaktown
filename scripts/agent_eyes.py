#!/usr/bin/env python3
"""Agent eyes: screenshot any local page, judge it with Jev ($0.0001).

Pipeline: Playwright (chromium, --no-sandbox, CDP capture fallback) -> PNG
-> typesafe/jev-1.14 via OpenRouter Decisions API -> calibrated noul
probabilities. OPENROUTER_API_KEY is used for JEV ONLY per owner rule.

  OPENROUTER_API_KEY=... /usr/bin/python3 scripts/agent_eyes.py <url>
"""
import base64
import json
import os
import sys
import urllib.request

MODEL = "typesafe/jev-1.14"
QUESTIONS = {
    "room_visible": {"type": "noul",
                     "instructions": "Does the screenshot show a rendered 3D room interior?"},
    "performer_visible": {"type": "noul",
                          "instructions": "Is a performer character (person, creature, or avatar) visible in the room?"},
    "error_visible": {"type": "noul",
                      "instructions": "Is any error message visible on the page?"},
    "mic_visible": {"type": "noul",
                    "instructions": "Is a microphone stand visible?"},
}


def shoot(url, out="/tmp/eyes.png"):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox",
                                    "--use-gl=swiftshader",
                                    "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(15000)
        try:
            pg.screenshot(path=out, timeout=15000)
        except Exception:
            cdp = pg.context.new_cdp_session(pg)
            res = cdp.send("Page.captureScreenshot", {"format": "png"})
            open(out, "wb").write(base64.b64decode(res["data"]))
        b.close()
    return out


def judge(png_path, key):
    img = base64.b64encode(open(png_path, "rb").read()).decode()
    body = json.dumps({
        "model": MODEL,
        "state": ["Page screenshot:",
                  {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{img}"}}],
        "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/alpha/decisions", data=body,
        method="POST", headers={"Authorization": f"Bearer {key}",
                                 "Content-Type": "application/json",
                                 "HTTP-Referer": "https://funnier.si/",
                                 "X-Title": "freaktown-jev-eyes"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    if len(sys.argv) < 2:
        print("usage: agent_eyes.py <url>", file=sys.stderr)
        return 2
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("REFUSING: OPENROUTER_API_KEY missing.", file=sys.stderr)
        return 2
    url = sys.argv[1]
    png = shoot(url)
    d = judge(png, key)
    print(json.dumps({"url": url, "model": d.get("model"), "shot": png,
                      "cost_usd": (d.get("usage") or {}).get("cost"),
                      "answers": {k: v.get("noul") for k, v in
                                  d.get("answers", {}).items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
