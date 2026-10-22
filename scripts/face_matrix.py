#!/usr/bin/env python3
"""Face matrix: render each emotion recipe, have Qwen judge what it sees.

The agents-see-what-humans-see loop:
  EXPRESSION_INTENTS -> expression_morphs -> Blender GLB render ->
  Qwen Omni vision -> {primary, intensity} vs intended.

Usage: python3 scripts/face_matrix.py [--emotions happy,sad,...]
       [--size 512] [--outdir /tmp/opencode/faces] [--render-only]
       [--judge-only]
Needs: blender, the RPM template GLB, QWEN_API_KEY (judge step only).

QWEN_API_KEY='...' python3 scripts/face_matrix.py
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from face_profiles import expression_morphs  # noqa: E402

GLB = ("/home/ubuntu/pogtown/pogtown-mvp/.cache/upstreams/"
       "three-ws/workers/avatar-reconstruction/templates/default.glb")
EMOTIONS = ["neutral", "happy", "sad", "angry", "surprised", "afraid",
            "disgust", "contempt", "grin"]


def render_one(emotion, weights, outdir, size):
    dest = os.path.join(outdir, emotion + ".png")
    cmd = ["blender", "-b", "--python",
           os.path.join(HERE, "scripts", "render_face.py"), "--",
           "--glb", GLB, "--out", dest,
           "--weights", json.dumps(weights), "--size", str(size),
           "--side", "FRONT"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = os.path.exists(dest) and os.path.getsize(dest) > 10000
    line = [l for l in (p.stdout + p.stderr).splitlines()
            if "FACE-RENDER" in l]
    print(("OK " if ok else "FAIL ") + emotion + " " +
          (line[-1] if line else ""), flush=True)
    return dest if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emotions", default=",".join(EMOTIONS))
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--outdir", default="/tmp/opencode/faces")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--judge-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    emos = [e.strip() for e in a.emotions.split(",") if e.strip()]
    paths = {}
    if not a.judge_only:
        for emo in emos:
            weights = dict(expression_morphs(emo, 1.0))
            paths[emo] = render_one(emo, weights, a.outdir, a.size)
    else:
        for emo in emos:
            p = os.path.join(a.outdir, emo + ".png")
            if os.path.exists(p):
                paths[emo] = p
    if a.render_only:
        return
    from backend.services.funnier.see_face import see_face
    report = {}
    for emo, path in paths.items():
        if not path:
            report[emo] = {"error": "no render"}
            continue
        r = see_face(path, intended=emo)
        report[emo] = r
        print("%-10s -> %-10s (%.2f) match=%s %s" % (
            emo, r["primary"], r["intensity"] or 0, r["matches"],
            ("artifacts=" + str(r["artifacts"])) if r["artifacts"]
            else ""), flush=True)
    rep_path = os.path.join(a.outdir, "matrix_report.json")
    json.dump(report, open(rep_path, "w"), indent=1)
    hits = sum(1 for e, r in report.items()
               if r.get("matches") is True)
    print("score: %d/%d looking_at_camera=%s" % (
        hits, len(report),
        all(r.get("looking_at_camera") for r in report.values()
            if "error" not in r)))
    print("report:", rep_path)


if __name__ == "__main__":
    main()
