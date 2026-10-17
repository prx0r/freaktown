#!/usr/bin/env python3
"""Gate-check concept frames against the venue truth ($0, CF neurons + PIL).

Technical (PIL, offline): dims, size, mean/max luminance (near-dark room
with one hard spot = low mean + high max), border check, sharpness proxy.
Content (llava-1.5-7b, free): person? window? mic stand? furniture/curtains?
Writes results into the sidecar .json as "gates" with a pass/fail verdict.

Shell frames must be bare (no mic/furniture/curtains/people/windows).
Dressed frames must have no people/windows.

  source /root/.r2-env && /usr/bin/python3 scripts/validate_concepts.py [shot ...]
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "concepts"
VISION = "@cf/llava-hf/llava-1.5-7b-hf"

QUESTIONS = (
    "Look at this comedy-club room photo. Answer each on its own line as "
    "Q: YES or NO.\n"
    "1. Does it show any human person or face?\n"
    "2. Does it show any window or daylight?\n"
    "3. Does it show a microphone or mic stand?\n"
    "4. Does it show furniture (tables/chairs/stools) or curtains?"
)


def tech(path):
    from PIL import Image, ImageStat, ImageFilter
    im = Image.open(path).convert("RGB")
    w, h = im.size
    gray = im.convert("L")
    st = ImageStat.Stat(gray)
    edge = gray.filter(ImageFilter.FIND_EDGES)
    sharp = ImageStat.Stat(edge).var[0]
    # border: mean abs diff between 6px edge strip and center crop
    ew, eh = max(w // 20, 6), max(h // 20, 6)
    border = ImageStat.Stat(gray.crop((0, 0, w, eh))).mean[0]
    center = ImageStat.Stat(
        gray.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))).mean[0]
    return {"dims": [w, h], "kb": path.stat().st_size // 1024,
            "mean_lum": round(st.mean[0], 1), "max_lum": gray.getextrema()[1],
            "sharpness": round(sharp, 1),
            "border_flat": abs(border - center) < 4}


def ask_vision(img_bytes, token, acct):
    body = json.dumps({"prompt": QUESTIONS,
                       "image": list(img_bytes)}).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{VISION}",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        d = json.loads(r.read().decode())
    txt = (d.get("result") or {}).get("response", "") or str(d.get("result"))
    out = {}
    for i, key in enumerate(("person", "window", "micstand", "furniture"), 1):
        out[key] = None
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith(str(i)) and "YES" in s.upper():
                out[key] = True
            elif s.startswith(str(i)) and "NO" in s.upper():
                out[key] = False
    out["_raw"] = txt[:400]
    return out


def main():
    token = os.environ.get("CF_API_TOKEN", "")
    acct = os.environ.get("CF_ACCOUNT_ID", "")
    if not token or not acct:
        print("REFUSING: CF creds not in environment.", file=sys.stderr)
        return 2
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = sorted(OUT.glob("*.json"))
    if want:
        files = [f for f in files if f.stem in want]
    for jf in files:
        m = json.loads(jf.read_text())
        imgf = OUT / m.get("file", "")
        if not imgf.exists():
            print(f"SKIP {jf.stem}: image missing"); continue
        t = tech(imgf)
        try:
            v = ask_vision(imgf.read_bytes(), token, acct)
        except Exception as e:
            print(f"FAIL {jf.stem}: vision error {e}"); continue
        reasons = []
        if v.get("person"):
            reasons.append("people present")
        if v.get("window"):
            reasons.append("window/daylight")
        shell = jf.stem.startswith("shell-")
        if shell and v.get("micstand"):
            reasons.append("mic stand in SHELL frame")
        if shell and v.get("furniture"):
            reasons.append("furniture/curtains in SHELL frame")
        if t["max_lum"] < 120:
            reasons.append("no bright spot (too flat-dark)")
        if t["sharpness"] < 20:
            reasons.append("blurry")
        verdict = "fail" if reasons else "pass"
        m["gates"] = {"tech": t,
                      "vision": {k: v.get(k) for k in
                                 ("person", "window", "micstand", "furniture")},
                      "verdict": verdict, "reasons": reasons}
        jf.write_text(json.dumps(m, indent=2) + "\n")
        print(f"{verdict.upper():4} {jf.stem}: "
              f"{'; '.join(reasons) if reasons else 'clean'}")
    print("done — $0 spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
