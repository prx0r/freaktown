"""Finish a rendered newsroom episode: graphics + grain over every frame, encode with the master, check it.

    python3 sets/blender/newsroom_finish.py --episode <episode dir> --frames <dir with f_NNNN.png> --out episode.mp4

    overlays   newsroom_gfx.Overlay (bug, lower thirds, the intro title sequence, the outro card) in the skin's style
    grain      seeded luminance grain per frame (amount from the skin's look.grain, default 0.018)
    encode     H.264 limited-range BT.709 yuv420p + the -14 LUFS master (AAC), +faststart
    checks     ffmpeg blackdetect (black stretches are listed; the outro's planned fade is expected), frame count vs
               programme, a 24-frame sample sheet (sheet.jpg), throughput summary from the chunks' stats_*.json
"""
import argparse, glob, json, pathlib, re, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import newsroom_gfx as G  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--crf", type=int, default=20)
    a = ap.parse_args()
    ep = pathlib.Path(a.episode)
    fr = pathlib.Path(a.frames)
    prog = json.loads((ep / "programme.json").read_text())
    meta = json.loads((ep / "episode.json").read_text())
    skin = G.load_skin(meta["skin"])
    files = sorted(fr.glob("f_*.png"))
    n = len(files)
    want = int(round(prog["duration_ms"] / 1000 * a.fps))
    print(f"frames {n} (programme {want})")
    if not n:
        raise SystemExit("no frames")
    W, H = Image.open(files[0]).size
    ov = G.Overlay(skin, prog, W, H)
    grain = float(skin.get("look", {}).get("grain", 0.018))
    done = fr / "final"
    done.mkdir(exist_ok=True)
    for i, f in enumerate(files):
        k = int(re.findall(r"\d+", f.stem)[0])
        t = (k - 1) * 1000.0 / a.fps
        im = Image.open(f).convert("RGB")
        x = np.asarray(im).astype(np.float32) / 255.0
        rng = np.random.default_rng(k)
        g = rng.normal(0.0, grain, (H, W, 1)).astype(np.float32)
        lum = x.mean(axis=2, keepdims=True)
        x = np.clip(x + g * (0.35 + 0.65 * (1 - np.abs(lum - 0.5) * 2)), 0, 1)
        im = Image.fromarray((x * 255 + 0.5).astype(np.uint8)).convert("RGBA")
        im.alpha_composite(ov.frame(t))
        im.convert("RGB").save(done / f"f_{k:04d}.jpg", quality=94)
    first = int(re.findall(r"\d+", files[0].stem)[0])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-start_number", str(first), "-i", str(done / "f_%04d.jpg"),
           "-i", str(ep / "master.wav"), "-map", "0:v", "-map", "1:a", "-shortest",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-crf", str(a.crf),
           "-preset", "slow", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    bd = subprocess.run(["ffmpeg", "-i", a.out, "-vf", "blackdetect=d=0.1:pix_th=0.06", "-an", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bd)
    lo = subprocess.run(["ffmpeg", "-nostats", "-i", a.out, "-vn", "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)
    # sample sheet: 24 frames evenly spaced
    pick = [files[int(i * (n - 1) / 23)] for i in range(24)] if n >= 24 else files
    tw, th = 320, 180
    sheet = Image.new("RGB", (6 * tw, 4 * th))
    for i, f in enumerate(pick):
        k = int(re.findall(r"\d+", f.stem)[0])
        sheet.paste(Image.open(done / f"f_{k:04d}.jpg").resize((tw, th)), ((i % 6) * tw, (i // 6) * th))
    sheet.save(pathlib.Path(a.out).with_name("sheet.jpg"), quality=88)
    st = [json.loads(open(p).read()) for p in sorted(glob.glob(str(fr / "stats_*.json")))]
    summ = {"frames": n, "programme_frames": want, "black": [[float(x), float(y)] for x, y in blacks],
            "lufs_i": float(lufs[-1]) if lufs else None}
    if st:
        full_f, full_s = sum(s["full_frames"] for s in st), sum(s["full_s"] for s in st)
        an_f, an_s = sum(s["anchor_frames"] for s in st), sum(s["anchor_s"] for s in st)
        pl_n, pl_s = sum(s["plates"] for s in st), sum(s["plate_s"] for s in st)
        tot = sum(s["render_s"] for s in st)
        summ.update({"chunks": len(st), "runner_render_s": round(tot, 1), "s_per_frame_all_in": round(tot / max(1, n), 2),
                     "full_frames": full_f, "full_s_per_frame": round(full_s / full_f, 2) if full_f else None,
                     "anchor_frames": an_f, "anchor_s_per_frame": round(an_s / an_f, 2) if an_f else None,
                     "plates": pl_n, "plate_s_each": round(pl_s / pl_n, 1) if pl_n else None,
                     "slowest_chunk_s": max(s["render_s"] for s in st), "width": st[0]["width"], "samples": st[0]["samples"],
                     "cpus": sorted({s.get("cpu", "?") for s in st})})
    pathlib.Path(a.out).with_name("finish.json").write_text(json.dumps(summ, indent=1))
    print("FINISH", json.dumps(summ))


if __name__ == "__main__":
    main()
