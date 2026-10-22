"""Agents see what humans see: Qwen Omni vision judges face renders.

Takes a rendered face PNG, asks qwen3.8-omni-flash what expression it
shows, returns structured JSON. This is the perceptual check behind
every recipe: no human in the loop, same eyes as the audience.

Key from QWEN_API_KEY env only. Images go as base64 data URLs (the
endpoint rejects external URLs). Never raises; unparsable replies
return matches=False with the raw text for diagnosis.
"""

import base64
import json
import os
import urllib.request

BASE_URL = "https://ws-h6o7g3oq9mc7u24u.ap-southeast-1.maas.aliyuncs.com"
MODEL = "qwen3.8-omni-flash"

EMOTIONS = ["happy", "sad", "angry", "surprised", "afraid", "disgust",
            "contempt", "neutral", "grin", "smirk", "confused", "love"]


def see_face(png_path, intended=None, timeout=90, model=MODEL,
             base_url=None, api_key=None):
    """Render -> Qwen's reading. Returns {"seen": [...], "primary",
    "intensity", "looking_at_camera", "artifacts", "matches",
    "raw"}. matches compares primary against intended (None skips)."""
    blank = {"seen": [], "primary": None, "intensity": None,
             "looking_at_camera": None, "artifacts": [],
             "matches": None, "raw": ""}
    key = api_key or os.environ.get("QWEN_API_KEY", "")
    if not key:
        blank["raw"] = "no key"
        return blank
    try:
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        blank["raw"] = "unreadable: %s" % (e,)
        return blank
    prompt = (
        "You see a 3D avatar face render (Workbench MATCAP, grey). "
        "Reply with ONE JSON object only, no other text: "
        '{"primary": the ONE dominant emotion you see (one of: %s), '
        '"intensity": 0-1, "seen": [any other emotions visible], '
        '"looking_at_camera": true/false, '
        '"artifacts": [visible glitches, e.g. clipped geometry, '
        "asymmetry, dead eyes]}." % ", ".join(EMOTIONS))
    body = {"model": model, "max_tokens": 300, "messages": [{
        "role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + b64}}]}]}
    base = (base_url or os.environ.get("QWEN_BASE_URL", "") or BASE_URL)
    req = urllib.request.Request(
        base.rstrip("/") + "/compatible-mode/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode())
        text = (((resp.get("choices") or [{}])[0].get("message") or {})
                .get("content") or "")
    except Exception as e:
        blank["raw"] = "request failed: %s" % (str(e)[:120],)
        return blank
    return _parse(text, intended)


def _parse(text, intended=None):
    blank = {"seen": [], "primary": None, "intensity": None,
             "looking_at_camera": None, "artifacts": [],
             "matches": None, "raw": str(text)[:500]}
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        obj = json.loads(text[start:end])
    except Exception:
        return blank
    if not isinstance(obj, dict):
        return blank
    out = dict(blank)
    prim = str(obj.get("primary") or "").lower() or None
    out["primary"] = prim
    try:
        if obj.get("intensity") is not None:
            out["intensity"] = max(0.0, min(1.0,
                                           float(obj["intensity"])))
    except Exception:
        pass
    seen = obj.get("seen")
    if isinstance(seen, list):
        out["seen"] = [str(s).lower() for s in seen
                       if isinstance(s, str)][:6]
    if isinstance(obj.get("looking_at_camera"), bool):
        out["looking_at_camera"] = obj["looking_at_camera"]
    arts = obj.get("artifacts")
    if isinstance(arts, list):
        out["artifacts"] = [str(a)[:80] for a in arts
                            if isinstance(a, str)][:6]
    if intended:
        out["matches"] = (prim == str(intended).lower())
    return out
