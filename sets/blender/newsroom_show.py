"""Script in -> episode out: the one command for a newsroom show.

    python3 sets/blender/newsroom_show.py --script my_script.json --skin goodnight \
        --anchor static/avatars/default-v1.vrm --out sets/blender/episodes/my-episode [--render local|ci|none]

Stages (each writes into --out, the episode directory, and is skipped when its output already exists unless --force):

    1 script   newsroom_programme.load_script: engine script.json, or tagged plain text ([open] [tee] [body] [close],
               "## title | source" per story); consecutive open/close lines become one read
    2 tts      Fish Audio s2.1-pro-free ONLY (any other model is refused in code), one wav per read, cached by
               sha1(model|voice|speed|text) so a re-run is free; --tts-seed DIR reuses an existing cache
    3 align    faster-whisper word timestamps per read, mapped onto the SCRIPT words (difflib), monotone repaired
    4 timeline newsroom_programme.layout: intro sting, reads with the show's gaps, outro; wall-card schedule, lower
               thirds, moods -> programme.json; the director runs inside Blender on the anchor's re-solved kit
    5 cards    newsroom_gfx: the skin's wall cards (title, every story, ambient, sign-off) and desk band -> cards/
    6 audio    the dry VO on the programme clock (vo_dry.wav), VO loudness per frame (env.json, drives the jaw),
               audiopost (packages/audiopost: room, mic drift, breaths, foley, the skin's ORIGINAL procedural sting +
               bed with ducking, -14 LUFS / -1.5 dBTP master) -> master.wav, post_report.json
    7 render   local: Blender 5.2 renders the chunks (newsroom_episode.py) and newsroom_finish.py composites the
               graphics, grain and audio into episode.mp4. ci: commit the episode directory and dispatch the
               "blender newsroom studio" workflow (episode=<dir name>, chunks, samples); free GitHub runners render it.

Characters and skins swap independently: --skin picks the studio filter, --anchor the VRM/GLB (checked with
checkFace before anything renders).
"""
import argparse, difflib, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "packages/audiopost"))
import newsroom_programme as P  # noqa: E402
import newsroom_gfx as G  # noqa: E402

FREE_MODEL = "s2.1-pro-free"
VOICE = "63d5460e91e2411fa2e6bf95e7456f03"          # the Goodnight voice (public, used on the free model)
SR = 48000


# ---- TTS ------------------------------------------------------------------------------------------------------------
def tts_key(model, voice, speed, text):
    return hashlib.sha1(f"{model}|{voice}|{speed}|{text}".encode()).hexdigest()[:16]


def fish_tts(text, voice, speed, out, model=FREE_MODEL):
    """Fish Audio TTS on the FREE model only. Key: FISH_API_KEY, or a gateway that injects it for api.fish.audio."""
    if model != FREE_MODEL:
        raise SystemExit(f"paid TTS is never used (got {model!r})")
    body = json.dumps({"text": text, "format": "wav", "reference_id": voice, "normalize": True, "latency": "normal",
                       "prosody": {"speed": speed}}).encode()
    hdr = {"Content-Type": "application/json", "model": model}
    if os.environ.get("FISH_API_KEY"):
        hdr["Authorization"] = f"Bearer {os.environ['FISH_API_KEY']}"
    for att in range(6):
        try:
            req = urllib.request.Request("https://api.fish.audio/v1/tts", data=body, headers=hdr)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if len(data) < 2000:
                raise RuntimeError(f"short body {len(data)}")
            pathlib.Path(out).write_bytes(data)
            return out
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 402, 403):
                raise SystemExit(f"Fish HTTP {e.code}: {e.read()[:200]!r} (free model only; nothing is ever paid for)")
        except Exception as e:
            print("  tts retry", att, e, flush=True)
        time.sleep(3 * 2 ** att)
    raise SystemExit("Fish TTS gave up")


def wav_dur_ms(path):
    import soundfile as sf
    i = sf.info(str(path))
    return int(round(i.frames / i.samplerate * 1000))


# ---- alignment --------------------------------------------------------------------------------------------------------
_W = None


def align(wav, text):
    """faster-whisper word timings mapped onto the script words; unmatched words interpolated."""
    global _W
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    if _W is None:
        from faster_whisper import WhisperModel
        _W = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=2)
    x, sr = sf.read(str(wav), always_2d=True)
    x = x.mean(1)
    if sr != 16000:
        x = resample_poly(x, 16000, sr)
    dur = len(x) / 16000
    segs, _ = _W.transcribe(x.astype("float32"), word_timestamps=True, language="en", beam_size=1,
                            condition_on_previous_text=False, vad_filter=False)
    ww = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words if w.start < dur - 0.02]
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    toks = text.split()
    sm = difflib.SequenceMatcher(a=[norm(t) for t in toks], b=[norm(w[2]) for w in ww], autojunk=False)
    st, en = [None] * len(toks), [None] * len(toks)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            st[blk.a + k], en[blk.a + k] = ww[blk.b + k][0], ww[blk.b + k][1]
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "replace":
            for k in range(a0, a1):
                j = b0 + int((k - a0) * (b1 - b0) / max(1, a1 - a0))
                if j < b1:
                    st[k], en[k] = ww[j][0], ww[j][1]
    matched = sum(x is not None for x in st)
    idx = [i for i, v in enumerate(st) if v is not None]
    for i in range(len(toks)):
        if st[i] is None:
            lo = max([j for j in idx if j < i], default=None)
            hi = min([j for j in idx if j > i], default=None)
            t_lo = en[lo] if lo is not None else 0.0
            t_hi = st[hi] if hi is not None else dur
            run = [j for j in range(i, len(toks)) if st[j] is None and (hi is None or j < hi)]
            n = len(run) or 1
            pos = run.index(i) if i in run else 0
            st[i], en[i] = t_lo + (t_hi - t_lo) * pos / n, t_lo + (t_hi - t_lo) * (pos + 1) / n
    words = []
    for i, t in enumerate(toks):
        s0 = int(round(st[i] * 1000))
        e0 = int(round(min(max(en[i], st[i] + 0.02), dur) * 1000))
        if words and s0 < words[-1]["start_ms"]:
            s0 = words[-1]["start_ms"]
        words.append({"word": t, "start_ms": s0, "end_ms": max(e0, s0 + 20)})
    return words, matched / max(1, len(toks))


# ---- audio ------------------------------------------------------------------------------------------------------------
def build_audio(out, prog, wavs, skin, fps, seed=7, preset="goodnight-studio"):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    n = int(prog["duration_ms"] / 1000 * SR) + SR
    vo = np.zeros(n)
    for ln in prog["lines"]:
        x, sr = sf.read(str(wavs[ln["id"]]), always_2d=True)
        x = x.mean(1)
        if sr != SR:
            x = resample_poly(x, SR, sr)
        i = int(ln["start_ms"] / 1000 * SR)
        m = min(len(x), n - i)
        vo[i:i + m] += x[:m]
    vo = vo[:int(prog["duration_ms"] / 1000 * SR)]
    sf.write(str(out / "vo_dry.wav"), vo.astype("float32"), SR)
    # loudness per frame (RMS over the frame, normalised to the speech's 95th percentile) -> the jaw
    hop = SR // fps
    rms = np.array([np.sqrt(np.mean(vo[i:i + hop] ** 2) + 1e-12) for i in range(0, len(vo), hop)])
    ref = np.percentile(rms[rms > 1e-4], 95) if (rms > 1e-4).any() else 1.0
    env = np.clip(rms / ref, 0, 1.2)
    (out / "env.json").write_text(json.dumps({"fps": fps, "env": [round(float(e), 4) for e in env]}))
    plan = P.audiopost_plan(prog)
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    from audiopost import process
    pre = process.load_preset(preset)
    pre["music"].update({k: v for k, v in skin.get("music", {}).items() if k in ("key", "style", "bar_s")})
    rep = process.run(str(out / "vo_dry.wav"), plan, pre, seed, str(out / "post"), sr=SR)
    shutil.copy(out / "post" / "master.wav", out / "master.wav")
    return rep


def measure_lufs(wav):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(wav), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return {"lufs_i": float(m[-1]) if m else None, "true_peak_dbfs": float(p[-1]) if p else None}


# ---- main -------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True)
    ap.add_argument("--skin", default="goodnight")
    ap.add_argument("--anchor", default="static/avatars/default-v1.vrm",
                    help="a cast id (sets/blender/news_cast/<id>.json: model, voice, face overrides) or a VRM/GLB path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default="")
    ap.add_argument("--voice", default="", help="Fish voice id (default: the cast member's voice, else the Goodnight voice)")
    ap.add_argument("--speed", type=float, default=0.75)
    ap.add_argument("--tts-cache", default=str(pathlib.Path.home() / ".cache/newsroom-tts"))
    ap.add_argument("--tts-seed", default="", help="an existing TTS cache dir (<key>.wav) to reuse")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--intro-ms", type=int, default=6000)
    ap.add_argument("--outro-ms", type=int, default=5000)
    ap.add_argument("--render", default="none", choices=["none", "local", "ci"])
    ap.add_argument("--blender", default=os.environ.get("BLENDER", "blender"))
    ap.add_argument("--chunks", type=int, default=1)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    skin = G.load_skin(a.skin)
    # refuse an anchor that cannot express before spending anything
    import face_express as FX
    import news_cast as NC
    model, cast = NC.resolve(a.anchor)
    a.voice = a.voice or (cast.get("voice") or {}).get("id") or VOICE
    names, nodes = FX.glb_names(model)
    chk = FX.check_face(names, nodes)
    if chk["level"] == "fail":
        raise SystemExit(f"ANCHOR REFUSED: {a.anchor} cannot express (no {', '.join(chk['missingCore'])} channel)")
    script = P.load_script(a.script)
    if a.date:
        script["date"] = a.date
    rds = P.reads(script)
    print(f"[1 script] {len(script['lines'])} lines -> {len(rds)} reads, {len(script['stories'])} stories", flush=True)
    cache = pathlib.Path(a.tts_cache)
    cache.mkdir(parents=True, exist_ok=True)
    wavs, durs, words, cov = {}, {}, {}, {}
    tts_log = []
    for r in rds:
        k = tts_key(FREE_MODEL, a.voice, a.speed, r["text"])
        w = cache / f"{k}.wav"
        src = "cache"
        if not w.exists() and a.tts_seed and (pathlib.Path(a.tts_seed) / f"{k}.wav").exists():
            shutil.copy(pathlib.Path(a.tts_seed) / f"{k}.wav", w)
            src = "seed-cache"
        if not w.exists():
            fish_tts(r["text"], a.voice, a.speed, str(w))
            src = "fish " + FREE_MODEL
        wavs[r["id"]] = w
        durs[r["id"]] = wav_dur_ms(w)
        tts_log.append({"id": r["id"], "key": k, "source": src, "dur_ms": durs[r["id"]]})
        print(f"[2 tts] {r['id']} {durs[r['id']]} ms ({src})", flush=True)
    alf = out / "align.json"
    if alf.exists() and not a.force:
        al = json.loads(alf.read_text())
    else:
        al = {}
        for r in rds:
            ws, c = align(wavs[r["id"]], r["text"])
            al[r["id"]] = {"words": ws, "coverage": round(c, 3)}
            print(f"[3 align] {r['id']} coverage {c:.1%}", flush=True)
        alf.write_text(json.dumps(al, indent=1))
    words = {k: v["words"] for k, v in al.items()}
    prog = P.layout(rds, durs, words, script, skin, a.intro_ms, a.outro_ms)
    (out / "programme.json").write_text(json.dumps(prog, indent=1))
    print(f"[4 timeline] {prog['duration_ms'] / 1000:.1f} s, {len(prog['lines'])} reads, {len(prog['cards'])} card cues", flush=True)
    G.write_cards(skin, out / "cards", prog)
    print("[5 cards]", ", ".join(sorted(json.loads((out / 'cards' / 'cards.json').read_text()))), flush=True)
    if not (out / "master.wav").exists() or a.force:
        rep = build_audio(out, prog, wavs, skin, a.fps)
    loud = measure_lufs(out / "master.wav")
    print(f"[6 audio] master {loud}", flush=True)
    anchor_rel = cast["id"] if (NC.CAST_DIR / f"{cast['id']}.json").exists() else \
        os.path.relpath(pathlib.Path(model).resolve(), ROOT) if str(pathlib.Path(model).resolve()).startswith(str(ROOT)) else model
    meta = {"skin": skin["id"], "anchor": anchor_rel, "fps": a.fps, "frames": int(round(prog["duration_ms"] / 1000 * a.fps)),
            "duration_ms": prog["duration_ms"], "tts": {"model": FREE_MODEL, "voice": a.voice, "speed": a.speed, "reads": tts_log},
            "align_coverage": {k: v["coverage"] for k, v in al.items()}, "loudness": loud, "facecheck": chk,
            "script": os.path.basename(a.script)}
    (out / "episode.json").write_text(json.dumps(meta, indent=1))
    for junk in ("post/stem_vo_post.wav", "post/stem_bed.wav", "post/stem_jingles.wav", "post/stem_roomtone.wav", "post/stem_foley.wav"):
        p = out / junk
        if p.exists():
            p.unlink()
    if a.render == "local":
        frames = out / "frames"
        for k in range(a.chunks):
            subprocess.run([a.blender, "-b", "--factory-startup", "--python", str(HERE / "newsroom_episode.py"), "--",
                            "--skill", os.environ.get("V2B_SKILL", ""), "--episode", str(out), "--frames", str(frames),
                            "--chunk", f"{k}/{a.chunks}", "--samples", str(a.samples), "--keys", str(frames / "keys.json")],
                           check=True)
        subprocess.run([sys.executable, str(HERE / "newsroom_finish.py"), "--episode", str(out), "--frames", str(frames),
                        "--out", str(out / "episode.mp4")], check=True)
    elif a.render == "ci":
        print(f"[7 render] commit {out} and dispatch .github/workflows/blender-newsroom-studio.yml with "
              f"episode={out.name} (free x86 runners render it; the encode job uploads episode.mp4)")
    print("EPISODE", out)


if __name__ == "__main__":
    main()
