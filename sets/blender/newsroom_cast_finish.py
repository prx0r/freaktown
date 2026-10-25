"""Finish a rendered cast show (newsroom_cast_show.py): every segment's graphics in its own skin, one encode, checks.

    python3 sets/blender/newsroom_cast_finish.py --episode sets/blender/episodes/cast-proof --frames dl/frames \
        --out final/cast_proof.mp4 [--max-mb 20]

frames/<segNN-cast>/f_NNNN.png (+ stats_K.json, keys.json) as the CI chunks upload them. Per segment: the skin's
overlays (bug, the name/story lower thirds, the intro title sequence on the first, the outro card on the last) and
grain, on the show clock; then H.264 with the show's -14 LUFS master. Checks written to finish.json:

    frames      rendered vs programme, per segment (a missing frame is listed, never papered over)
    black       ffmpeg blackdetect stretches (the outro's planned fade is expected)
    loudness    integrated LUFS and true peak of the encoded file (ebur128 peak=true)
    lipsync     Pearson r of the baked mouth-open curve against the VO loudness per frame, per segment and overall,
                on the frames where the read is on (keys.json from the bake: "mouth" and "env" per frame)
    throughput  s/frame from the chunks' stats_*.json, plates, CPU models
    size        the MP4 is re-encoded at a higher CRF until it is under --max-mb (it says which CRF it used)
"""
import argparse, glob, json, math, pathlib, re, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import newsroom_gfx as G  # noqa: E402


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() < 1e-9 or b.std() < 1e-9:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def lipsync(keys):
    """r(mouth, env) over speech frames, plus the best r within +-3 frames of lag (a lag != 0 means the mouth leads or
    trails the voice)."""
    fr = keys["frames"]
    m = [r["mouth"] for r in fr]
    e = [r.get("env", 0.0) for r in fr]
    on = [i for i, r in enumerate(fr) if r.get("vis") or r.get("env", 0) > 0.03]
    if len(on) < 10:
        return None
    r0 = pearson([m[i] for i in on], [e[i] for i in on])
    lags = {}
    for L in range(-3, 4):
        idx = [i for i in on if 0 <= i + L < len(m)]
        lags[L] = pearson([m[i + L] for i in idx], [e[i] for i in idx])
    best = max((k for k in lags if lags[k] is not None), key=lambda k: lags[k])
    return {"r": round(r0, 3) if r0 is not None else None, "frames": len(on), "best_lag_frames": best,
            "r_best_lag": round(lags[best], 3), "mouth_mean": round(float(np.mean([m[i] for i in on])), 3)}


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crf", type=int, default=21)
    ap.add_argument("--max-mb", type=float, default=20.0)
    a = ap.parse_args()
    ep, fr, outp = pathlib.Path(a.episode), pathlib.Path(a.frames), pathlib.Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    meta = json.loads((ep / "cast_episode.json").read_text())
    fps = meta["fps"]
    done = outp.parent / "jpg"
    done.mkdir(exist_ok=True)
    summ = {"segments": [], "frames": 0, "programme_frames": meta["frames"], "missing": []}
    stats, all_m, all_e = [], [], []
    last = None
    for s in meta["segments"]:
        sd = ep / s["dir"]
        prog = json.loads((sd / "programme.json").read_text())
        skin = G.load_skin(s["skin"])
        fdir = fr / s["dir"]
        files = {int(re.findall(r"\d+", p.stem)[0]): p for p in fdir.glob("f_*.png")}
        W, H = Image.open(next(iter(files.values()))).size if files else (1280, 720)
        ov = G.Overlay(skin, prog, W, H)
        grain = float(skin.get("look", {}).get("grain", 0.018))
        miss = []
        for k in range(1, s["frames"] + 1):
            g_idx = s["frame0"] + k
            p = files.get(k)
            if p is None:
                miss.append(k)
                if last is None:
                    continue
                im = last                        # hold the previous frame so the encode keeps sync; reported below
            else:
                x = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255.0
                rng = np.random.default_rng(g_idx)
                gr = rng.normal(0.0, grain, (H, W, 1)).astype(np.float32)
                lum = x.mean(axis=2, keepdims=True)
                x = np.clip(x + gr * (0.35 + 0.65 * (1 - np.abs(lum - 0.5) * 2)), 0, 1)
                im = Image.fromarray((x * 255 + 0.5).astype(np.uint8)).convert("RGBA")
                im.alpha_composite(ov.frame((k - 1) * 1000.0 / fps))
                im = im.convert("RGB")
                last = im
            im.save(done / f"f_{g_idx:05d}.jpg", quality=93)
        st = [json.loads(open(p).read()) for p in sorted(glob.glob(str(fdir / "stats_*.json")))]
        for x in st:
            x["segment"] = s["dir"]
        stats += st
        ls = None
        kp = fdir / "keys.json"
        if kp.exists():
            keys = json.loads(kp.read_text())
            ls = lipsync(keys)
            on = [r for r in keys["frames"] if r.get("vis") or r.get("env", 0) > 0.03]
            all_m += [r["mouth"] for r in on]
            all_e += [r.get("env", 0.0) for r in on]
        summ["segments"].append({"dir": s["dir"], "cast": s["cast"], "skin": s["skin"], "frames": len(files),
                                 "programme_frames": s["frames"], "missing": miss[:50], "missing_n": len(miss), "lipsync": ls})
        summ["frames"] += len(files)
        if miss:
            summ["missing"].append([s["dir"], len(miss)])
    first = min(int(re.findall(r"\d+", p.stem)[0]) for p in done.glob("f_*.jpg"))

    def encode(crf, path):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-start_number", str(first), "-i", str(done / "f_%05d.jpg"),
               "-i", str(ep / "master.wav"), "-map", "0:v", "-map", "1:a", "-shortest",
               "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-crf", str(crf),
               "-preset", "medium", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(path)]
        subprocess.run(cmd, check=True)
        return path.stat().st_size / 1e6
    crf = a.crf
    mb = encode(crf, outp)
    while mb > a.max_mb and crf < 32:
        crf += 2
        mb = encode(crf, outp)
    summ.update({"crf": crf, "size_mb": round(mb, 2), "duration_s": round(probe_dur(outp), 2),
                 "programme_s": round(meta["duration_ms"] / 1000, 2)})
    bd = subprocess.run(["ffmpeg", "-i", str(outp), "-vf", "blackdetect=d=0.1:pix_th=0.06", "-an", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    summ["black"] = [[float(x), float(y)] for x, y in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bd)]
    lo = subprocess.run(["ffmpeg", "-nostats", "-i", str(outp), "-vn", "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    li, tp = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo), re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)
    summ["lufs_i"] = float(li[-1]) if li else None
    summ["true_peak_dbfs"] = float(tp[-1]) if tp else None
    r_all = pearson(all_m, all_e)
    summ["lipsync_r_all"] = round(r_all, 3) if r_all is not None else None
    jp = sorted(done.glob("f_*.jpg"))
    n = len(jp)
    pick = [jp[int(i * (n - 1) / 23)] for i in range(24)] if n >= 24 else jp
    tw, th = 320, 180
    sheet = Image.new("RGB", (6 * tw, 4 * th))
    for i, f in enumerate(pick):
        sheet.paste(Image.open(f).resize((tw, th)), ((i % 6) * tw, (i // 6) * th))
    sheet.save(outp.with_name("sheet.jpg"), quality=88)
    if stats:
        full_f, full_s = sum(s["full_frames"] for s in stats), sum(s["full_s"] for s in stats)
        an_f, an_s = sum(s["anchor_frames"] for s in stats), sum(s["anchor_s"] for s in stats)
        pl_n, pl_s = sum(s["plates"] for s in stats), sum(s["plate_s"] for s in stats)
        tot = sum(s["render_s"] for s in stats)
        summ.update({"chunks": len(stats), "runner_render_s": round(tot, 1), "s_per_frame_all_in": round(tot / max(1, summ["frames"]), 2),
                     "full_frames": full_f, "full_s_per_frame": round(full_s / full_f, 2) if full_f else None,
                     "anchor_frames": an_f, "anchor_s_per_frame": round(an_s / an_f, 2) if an_f else None,
                     "plates": pl_n, "plate_s_each": round(pl_s / pl_n, 1) if pl_n else None,
                     "slowest_chunk_s": max(s["render_s"] for s in stats), "width": stats[0]["width"], "samples": stats[0]["samples"],
                     "cpus": sorted({s.get("cpu", "?") for s in stats})})
    outp.with_name("finish.json").write_text(json.dumps(summ, indent=1))
    print("FINISH", json.dumps({k: v for k, v in summ.items() if k != "segments"}))
    for s in summ["segments"]:
        print("SEGMENT", json.dumps(s))


if __name__ == "__main__":
    main()
