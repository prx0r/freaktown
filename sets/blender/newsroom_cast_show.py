"""A multi-character show: each cast member reads in their own skin, on one programme clock with one audio master.

    python3 sets/blender/newsroom_cast_show.py --script sets/blender/episodes/cast-proof/script.json \
        --out sets/blender/episodes/cast-proof

Script (JSON):

    {"title": "...", "date": "25 October 2026",
     "segments": [
       {"cast": "house", "skin": "goodnight", "intro_ms": 4500,             # the first segment carries the title sequence
        "lines": [{"kind": "open", "text": "Good evening ...", "emotion": ["happy", 0.6],
                   "gestures": [{"word": "whole", "kind": "browflash"}]}]},
       {"cast": "vivi", "skin": "galactic", "open_shot": "CAM_MEDIUM",      # mid-show segments cut straight in
        "story": {"title": "Probe wakes up", "source": "Mission control"},
        "lines": [{"kind": "body", "text": "...", "emotion": ["surprised", 0.7]}]},
       ...
       {"cast": "seed", "skin": "goodnight", "outro_ms": 4000, "lines": [{"kind": "close", ...}]}]}

Per segment: the cast member's PUBLIC Fish voice on s2.1-pro-free only (newsroom_show.fish_tts refuses anything
else), faster-whisper word timings, newsroom_programme.layout on the segment's own clock, the line's emotion as the
mood, word-anchored gestures (wink | dart | browflash | smirk), a name lower third, the skin's wall cards, and the
mouth drive (env.json: the segment's VO loudness per frame, normalised per voice). Each segment is an ordinary
episode directory (segNN-<cast>/) that newsroom_episode.py renders unchanged (the director runs per segment; the
segments hard-cut into each other). The whole show gets ONE audio master: the VO of every segment on the show clock,
audiopost (room, breaths, the first skin's procedural sting + bed, -14 LUFS / -1.5 dBTP).

Writes: cast_episode.json (segments, frame offsets, voices, loudness), vo_dry.wav, master.wav, env.json (show clock),
segNN-<cast>/{programme,align,env,episode}.json + cards/.
"""
import argparse, hashlib, json, os, pathlib, re, shutil, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "packages/audiopost"))
import newsroom_programme as P  # noqa: E402
import newsroom_gfx as G  # noqa: E402
import newsroom_show as S  # noqa: E402
import news_cast as NC  # noqa: E402
import face_express as FX  # noqa: E402

GESTURE_MS = {"wink": 750, "dart": 900, "browflash": 520, "smirk": 1300}


def frame_ms(ms, fps):
    """Round a duration up to a whole frame so segment boundaries land on frames (audio and picture stay locked)."""
    f = 1000.0 / fps
    return int(-(-ms // f) * f + 0.5)


def env_for(vo, fps, sr):
    import numpy as np
    hop = sr // fps
    rms = np.array([np.sqrt(np.mean(vo[i:i + hop] ** 2) + 1e-12) for i in range(0, len(vo), hop)])
    ref = np.percentile(rms[rms > 1e-4], 95) if (rms > 1e-4).any() else 1.0
    return np.clip(rms / ref, 0, 1.2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--tts-cache", default=str(pathlib.Path.home() / ".cache/newsroom-tts"))
    ap.add_argument("--tts-seed", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    out = pathlib.Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(pathlib.Path(a.script).read_text())
    if pathlib.Path(a.script).resolve() != (out / "script.json").resolve():
        shutil.copy(a.script, out / "script.json")
    cache = pathlib.Path(a.tts_cache)
    cache.mkdir(parents=True, exist_ok=True)
    segs, show_t, all_lines, vo_parts = [], 0, [], []
    nseg = len(script["segments"])
    for si, seg in enumerate(script["segments"]):
        cast = NC.load(seg["cast"])
        names, nodes = FX.glb_names(cast["model_path"])
        chk = FX.check_face(names, nodes)
        if chk["level"] == "fail":
            raise SystemExit(f"CAST REFUSED: {cast['id']} cannot express ({chk['missingCore']})")
        skin = G.load_skin(seg["skin"])
        voice = cast["voice"]["id"]
        speed = float(seg.get("speed", cast["voice"].get("speed", 0.9)))
        sdir = out / f"seg{si:02d}-{cast['id']}"
        sdir.mkdir(exist_ok=True)
        story = seg.get("story")
        rds, wavs, durs, tts_log = [], {}, {}, []
        for li, ln in enumerate(seg["lines"]):
            kind = ln.get("kind", "body")
            rid = f"{cast['id']}#{li + 1}"
            text = ln["text"].replace("*", "")
            rds.append({"id": rid, "kind": kind, "story": 0 if story and kind in ("tee", "body") else None, "text": text,
                        "emotion": ln.get("emotion"), "gestures": ln.get("gestures", [])})
            k = S.tts_key(S.FREE_MODEL, voice, speed, text)
            w = cache / f"{k}.wav"
            src = "cache"
            if not w.exists() and a.tts_seed and (pathlib.Path(a.tts_seed) / f"{k}.wav").exists():
                shutil.copy(pathlib.Path(a.tts_seed) / f"{k}.wav", w)
                src = "seed-cache"
            if not w.exists():
                S.fish_tts(text, voice, speed, str(w))
                src = "fish " + S.FREE_MODEL
            wavs[rid], durs[rid] = w, S.wav_dur_ms(w)
            tts_log.append({"id": rid, "key": k, "source": src, "dur_ms": durs[rid], "voice": voice, "speed": speed})
            print(f"[tts] seg{si} {rid} {durs[rid]} ms ({src}) voice {cast['voice'].get('name')}", flush=True)
        alf = sdir / "align.json"
        if alf.exists() and not a.force:
            al = json.loads(alf.read_text())
        else:
            al = {}
            for r in rds:
                ws, c = S.align(wavs[r["id"]], r["text"])
                al[r["id"]] = {"words": ws, "coverage": round(c, 3)}
                print(f"[align] {r['id']} coverage {c:.1%}", flush=True)
            alf.write_text(json.dumps(al, indent=1))
        words = {k: v["words"] for k, v in al.items()}
        intro = int(seg.get("intro_ms", 0))
        outro = int(seg.get("outro_ms", 0))
        sc = {"title": script.get("title", ""), "date": script.get("date", ""), "stories": [story] if story else []}
        prog = P.layout(rds, durs, words, sc, skin, intro, outro, lead_ms=None if intro else int(seg.get("lead_ms", 350)))
        prog["duration_ms"] = frame_ms(prog["duration_ms"] + int(seg.get("tail_ms", 0 if outro else 450)), a.fps)
        if not intro:
            prog["open_shot"] = seg.get("open_shot", "CAM_MEDIUM")
        # moods: the script's emotion per line (falls back to the skin's tone per kind)
        moods = []
        for ln, r in zip(prog["lines"], rds):
            if r.get("emotion"):
                moods.append({"t_ms": ln["start_ms"], "dur_ms": ln["end_ms"] - ln["start_ms"], "emotion": r["emotion"][0],
                              "intensity": float(r["emotion"][1])})
            else:
                moods += [m for m in prog["moods"] if m["t_ms"] == ln["start_ms"]]
        prog["moods"] = moods
        # gestures anchored to a word (first match after the read starts) or to an offset in the read
        gest = []
        for ln, r in zip(prog["lines"], rds):
            for g in r.get("gestures", []):
                t = None
                if "word" in g:
                    want = re.sub(r"[^a-z0-9]", "", g["word"].lower())
                    t = next((w["start_ms"] for w in ln["words"] if re.sub(r"[^a-z0-9]", "", w["word"].lower()) == want), None)
                elif "at_ms" in g:
                    t = ln["start_ms"] + int(g["at_ms"])
                elif g.get("after"):
                    t = ln["end_ms"] + int(g.get("after_ms", 150))
                if t is None:
                    print(f"  gesture {g} not placed (word not found)", flush=True)
                    continue
                gest.append({"t_ms": max(0, t - 80), "dur_ms": int(g.get("dur_ms", GESTURE_MS.get(g["kind"], 700))),
                             "kind": g["kind"], **{k: g[k] for k in ("x", "y", "side") if k in g}})
        prog["gestures"] = gest
        # wall: the segment's story card when framed whole, else ambient; title only under the opening segment
        cards = [c for c in prog["cards"] if c["card"] in ("ambient", "title") and c["t_ms"] < max(1, intro)] if intro else []
        cards.append({"t_ms": prog["lines"][0]["start_ms"] if intro else 0, "card": "story0" if story else "ambient"})
        if any(r["kind"] == "close" for r in rds):
            cards.append({"t_ms": max(0, next(ln["start_ms"] for ln in prog["lines"] if ln["kind"] == "close") - 600), "card": "signoff"})
        if outro:
            cards.append({"t_ms": prog["duration_ms"] - outro + 600, "card": "title"})
        prog["cards"] = sorted(cards, key=lambda c: c["t_ms"])
        # lower thirds: who is reading (cast name / the skin's show), then the story strap
        t0 = prog["lines"][0]["start_ms"]
        lowers = [{"t_ms": t0 + 250, "dur_ms": min(3600, prog["lines"][-1]["end_ms"] - t0), "kind": "name",
                   "title": cast.get("name", cast["id"]), "sub": skin["brand"]["title"]}]
        if story and prog["lines"][-1]["end_ms"] - t0 > 6500:
            lowers.append({"t_ms": t0 + 4100, "dur_ms": 3600, "kind": "story", "title": story["title"], "sub": story.get("source", "")})
        prog["lowers"] = lowers
        prog["segment"] = {"index": si, "of": nseg, "cast": cast["id"], "name": cast.get("name"), "skin": skin["id"]}
        (sdir / "programme.json").write_text(json.dumps(prog, indent=1))
        G.write_cards(skin, sdir / "cards", {**prog, "stories": sc["stories"], "date": script.get("date", "")})
        # segment VO on its own clock + its mouth drive
        n = int(prog["duration_ms"] / 1000 * S.SR)
        vo = np.zeros(n)
        for ln in prog["lines"]:
            x, sr = sf.read(str(wavs[ln["id"]]), always_2d=True)
            x = x.mean(1)
            if sr != S.SR:
                x = resample_poly(x, S.SR, sr)
            i = int(ln["start_ms"] / 1000 * S.SR)
            m = min(len(x), n - i)
            vo[i:i + m] += x[:m]
        env = env_for(vo, a.fps, S.SR)
        frames = int(round(prog["duration_ms"] / 1000 * a.fps))
        env = list(env[:frames]) + [0.0] * max(0, frames - len(env))
        (sdir / "env.json").write_text(json.dumps({"fps": a.fps, "env": [round(float(e), 4) for e in env]}))
        meta = {"skin": skin["id"], "anchor": cast["id"], "cast": cast["id"], "fps": a.fps, "frames": frames,
                "duration_ms": prog["duration_ms"], "show_t0_ms": show_t,
                "tts": {"model": S.FREE_MODEL, "voice": voice, "voice_name": cast["voice"].get("name"), "speed": speed, "reads": tts_log},
                "align_coverage": {k: v["coverage"] for k, v in al.items()}, "facecheck": chk}
        (sdir / "episode.json").write_text(json.dumps(meta, indent=1))
        segs.append({"dir": sdir.name, "cast": cast["id"], "name": cast.get("name"), "skin": skin["id"], "t0_ms": show_t,
                     "duration_ms": prog["duration_ms"], "frames": frames, "voice": voice, "voice_name": cast["voice"].get("name"),
                     "lines": [ln["text"] for ln in prog["lines"]], "emotions": [m["emotion"] for m in moods],
                     "gestures": [g["kind"] for g in gest]})
        vo_parts.append(vo)
        for ln in prog["lines"]:
            all_lines.append({**ln, "start_ms": ln["start_ms"] + show_t, "end_ms": ln["end_ms"] + show_t,
                              "words": [{**w, "start_ms": w["start_ms"] + show_t, "end_ms": w["end_ms"] + show_t} for w in ln["words"]]})
        show_t += prog["duration_ms"]
    # one master for the show
    vo = np.concatenate(vo_parts)
    sf.write(str(out / "vo_dry.wav"), vo.astype("float32"), S.SR)
    first, last = script["segments"][0], script["segments"][-1]
    intro, outro = int(first.get("intro_ms", 0)), int(last.get("outro_ms", 0))
    show = {"duration_ms": show_t, "intro_ms": intro, "outro_ms": outro, "lines": all_lines,
            "stings": [{"t_ms": 0, "kind": "open", "dur_ms": max(intro, 1500)},
                       {"t_ms": show_t - outro - 200, "kind": "close", "dur_ms": max(outro, 1500)}]}
    plan = P.audiopost_plan(show)
    plan["story_starts"] = [s["t0_ms"] / 1000 for s in segs[1:]]
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    if not (out / "master.wav").exists() or a.force:
        from audiopost import process
        pre = process.load_preset("goodnight-studio")
        pre["music"].update({k: v for k, v in G.load_skin(first["skin"]).get("music", {}).items() if k in ("key", "style", "bar_s")})
        process.run(str(out / "vo_dry.wav"), plan, pre, 7, str(out / "post"), sr=S.SR)
        shutil.copy(out / "post" / "master.wav", out / "master.wav")
        for junk in ("stem_vo_post.wav", "stem_bed.wav", "stem_jingles.wav", "stem_roomtone.wav", "stem_foley.wav"):
            p = out / "post" / junk
            if p.exists():
                p.unlink()
    loud = S.measure_lufs(out / "master.wav")
    env = []
    for s in segs:
        env += json.loads((out / s["dir"] / "env.json").read_text())["env"]
    (out / "env.json").write_text(json.dumps({"fps": a.fps, "env": env}))
    f0 = 0
    for s in segs:
        s["frame0"] = f0
        f0 += s["frames"]
    meta = {"title": script.get("title"), "date": script.get("date"), "fps": a.fps, "frames": f0, "duration_ms": show_t,
            "segments": segs, "loudness": loud, "tts_model": S.FREE_MODEL}
    (out / "cast_episode.json").write_text(json.dumps(meta, indent=1))
    print(f"[cast show] {len(segs)} segments, {show_t / 1000:.1f} s, {f0} frames, master {loud}", flush=True)
    print("CAST EPISODE", out)


if __name__ == "__main__":
    main()
