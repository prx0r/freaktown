"""Render plan for a cast show: split every segment into chunks of at most --max-frames frames (GitHub matrix JSON).

    python3 sets/blender/newsroom_cast_plan.py sets/blender/episodes/cast-proof --max-frames 46
    -> {"include": [{"seg": "seg00-house", "k": 0, "n": 7, "frames": 307}, ...]}

Chunk size is the lever on wall time: measured 15-32 s/frame on a 4-vCPU runner (CPU model dependent) plus ~4 min of
setup per job, so 46 frames keeps every job far inside the 150-minute timeout even on the slow EPYC 7763.
"""
import argparse, json, math, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("episode")
ap.add_argument("--max-frames", type=int, default=46)
a = ap.parse_args()
meta = json.loads((pathlib.Path(a.episode) / "cast_episode.json").read_text())
inc = []
for s in meta["segments"]:
    n = max(1, math.ceil(s["frames"] / a.max_frames))
    inc += [{"seg": s["dir"], "k": k, "n": n, "frames": s["frames"]} for k in range(n)]
print(json.dumps({"include": inc}, separators=(",", ":")))
