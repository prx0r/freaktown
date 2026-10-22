"""Build a club performance clip (audio + timeline) from a /characters3 set: Fish TTS per line, measured word timings,
procedural crowd laughs, one mixed track and the timeline the Blender bake (club_perform.py) keys from.

    python3 sets/blender/club_clip.py --set <set.json> [--sketch <set.sketch.json>] --lines l1-l8,l10-l14 \
        --out sets/blender/perform/<clip-id> [--voice <fish reference id>] [--fps 25]

Steps (each cached in <out>/work so a rerun is free):
  1. TTS: one request per line to Fish s2.1-pro-free (the free model; nothing else is ever called). The delivery
     becomes an inline direction tag ([dry, deadpan], [calm, measured], ...). Key comes from $FISH_API_KEY or a
     gateway that injects it.
  2. Word timings: faster-whisper (base.en, word_timestamps) on each line, matched back to the script words.
  3. Layout: the set's own pause_ms before a line and hold_ms after a punch/tag; a laugh fills each hold (punches
     get at least 1.9 s, tags 1.3 s) and the next line may start under the laugh's tail.
  4. Mix: comic VO (light room reverb) + procedural crowd laughs (voiced "ha" pulses through vowel formants plus
     breath noise, 24-40 voices, the same idea as packages/stage-runtime/src/SfxSynth.ts laugh, $0, no assets) +
     a quiet room tone. 48 kHz stereo WAV and AAC m4a.
  5. timeline.json: lines (absolute word spans, role, delivery, emotion, emphasis/hit word), laughs, looks,
     gestures, and env[]: the comic VO's loudness per video frame (0..1), which the bake multiplies into the
     mouth so the jaw follows the real audio.
"""
import argparse, json, math, os, pathlib, re, subprocess, sys, urllib.request

SR = 48000
TAG = {"warm": "[warm, gently amused]", "deliberate": "[calm, measured]", "deadpan": "[dry, deadpan]",
       "manic": "[excited, breathless, fast]"}
DEFAULT_VOICE = "32e344f53f114cfcbb7ed086f10f2403"   # public Fish voice "british female": calm, measured, crisp


def parse_ids(spec, lines):
    ids = [l["id"] for l in lines]
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += ids[ids.index(a): ids.index(b) + 1]
        else:
            out.append(part)
    return out


def tts(text, delivery, voice, out):
    if out.exists():
        return
    body = {"text": f"{TAG.get(delivery, '')} {text}".strip(), "reference_id": voice, "format": "wav",
            "latency": "normal", "normalize": True, "prosody": {"speed": 0.97}}
    hdr = {"Content-Type": "application/json", "model": "s2.1-pro-free"}   # the free model, always
    if os.environ.get("FISH_API_KEY"):
        hdr["Authorization"] = "Bearer " + os.environ["FISH_API_KEY"]
    req = urllib.request.Request("https://api.fish.audio/v1/tts", data=json.dumps(body).encode(), headers=hdr)
    with urllib.request.urlopen(req, timeout=180) as r:
        out.write_bytes(r.read())


def load(path, sr=SR):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


_MODEL = None


def words_of(path, text):
    """Measured word spans (ms from the start of the line), re-labelled with the script's own words."""
    global _MODEL
    from faster_whisper import WhisperModel
    if _MODEL is None:
        _MODEL = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=2)
    segs, _ = _MODEL.transcribe(load(path, 16000), word_timestamps=True, beam_size=5, language="en")
    heard = [{"word": w.word.strip(), "start_ms": round(w.start * 1000), "end_ms": round(w.end * 1000)} for s in segs for w in s.words]
    script = re.findall(r"[A-Za-z0-9']+", text.replace("-", " "))
    if not heard:
        return [], script
    # map script words onto the heard spans proportionally by character count (ASR merges "Leather bound" etc.)
    t0, t1 = heard[0]["start_ms"], heard[-1]["end_ms"]
    hc = [max(1, len(re.sub(r"\W", "", h["word"]))) for h in heard]
    sc = [max(1, len(w)) for w in script]
    # cumulative character positions -> time through the heard words (piecewise linear inside each heard word)
    hpos = [0]
    for c in hc:
        hpos.append(hpos[-1] + c)
    def at(frac):
        x = frac * hpos[-1]
        for i, h in enumerate(heard):
            if x <= hpos[i + 1]:
                u = (x - hpos[i]) / hc[i]
                return h["start_ms"] + u * (h["end_ms"] - h["start_ms"])
        return t1
    out, acc, tot = [], 0, sum(sc)
    for w, c in zip(script, sc):
        a, b = at(acc / tot), at((acc + c) / tot)
        out.append({"word": w, "start_ms": round(a), "end_ms": round(max(a + 60, b))})
        acc += c
    return out, script


def bandpass(x, f0, q, sr=SR):
    """FFT band-pass (Gaussian in log-frequency), good enough for formants and noise colour."""
    import numpy as np
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    bw = f0 / q
    X *= np.exp(-0.5 * ((f - f0) / bw) ** 2)
    return np.fft.irfft(X, n)


def laugh(dur_s, size, rng):
    """A crowd laugh: many voices of voiced 'ha' pulses (glottal saw through /a/ formants) + breath noise."""
    import numpy as np
    n = int((dur_s + 1.2) * SR)
    out = np.zeros(n, np.float32)
    voices = int(18 + 22 * size)
    t = np.arange(n) / SR
    for v in range(voices):
        start = rng.uniform(0.0, 0.45) + (0.0 if v < voices * 0.6 else rng.uniform(0.2, 0.6))
        rate = rng.uniform(3.8, 6.2)
        pitch = rng.choice([rng.uniform(95, 150), rng.uniform(170, 280)])
        length = dur_s * rng.uniform(0.55, 1.05)
        jitter = 1 + 0.03 * np.sin(2 * np.pi * rng.uniform(3, 7) * t + rng.uniform(0, 6))
        glide = 1 + 0.25 * np.exp(-np.maximum(0, t - start) / max(0.3, length * 0.6))
        ph = np.cumsum(pitch * jitter * glide / SR)
        saw = (ph % 1.0) * 2 - 1
        pulse_ph = (t - start) * rate
        gate = np.where((t >= start) & (t < start + length), np.clip(np.sin(np.pi * (pulse_ph % 1.0)), 0, 1) ** 1.6, 0.0)
        env = np.clip(1 - (t - start) / max(0.1, length), 0, 1) ** 0.7
        voiced = saw * gate * env
        f1, f2 = rng.uniform(650, 900), rng.uniform(1100, 1500)
        sig = bandpass(voiced, f1, 4) * 1.0 + bandpass(voiced, f2, 5) * 0.55
        breath = bandpass(rng.standard_normal(n).astype(np.float32) * gate * env, rng.uniform(1500, 2600), 1.6) * 0.35
        out += ((sig + breath) * rng.uniform(0.5, 1.0)).astype(np.float32)
    out /= max(1e-6, np.abs(out).max())
    return out * (0.35 + 0.25 * size)


def reverb(x, rt=0.55, mix=0.18, rng=None):
    import numpy as np
    n = int(rt * SR)
    ir = (rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)).astype(np.float32)
    ir = bandpass(ir, 1800, 0.6)
    ir /= np.abs(ir).sum() ** 0.5 * 6
    m = len(x) + n
    nfft = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return (x + mix * wet / max(1e-6, np.abs(wet).max()) * np.abs(x).max()).astype(np.float32)


def main():
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--sketch", default="")
    ap.add_argument("--lines", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--lead-ms", type=int, default=900)
    ap.add_argument("--tail-ms", type=int, default=600)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    S = json.loads(pathlib.Path(a.set).read_text())
    emo = {}
    looks_before, gestures_before = {}, {}
    if a.sketch:
        sk = json.loads(pathlib.Path(a.sketch).read_text())
        pending_look, pending_gest = None, None
        for sc in sk["scenes"]:
            for b in sc["beats"]:
                for it in b["items"]:
                    if it["type"] == "look":
                        pending_look = it
                    elif it["type"] == "gesture":
                        pending_gest = it
                    elif it["type"] == "line":
                        emo[it["id"]] = it.get("emotion", "neutral")
                        if pending_look:
                            looks_before[it["id"]] = pending_look
                        if pending_gest:
                            gestures_before[it["id"]] = pending_gest
                        pending_look = pending_gest = None
    by = {l["id"]: l for l in S["lines"]}
    ids = parse_ids(a.lines, S["lines"])
    out = pathlib.Path(a.out)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    t = a.lead_ms
    vo_parts, lines, laughs, looks, gestures = [], [], [], [], []
    prev_hold_end = None
    for i, lid in enumerate(ids):
        l = by[lid]
        wav = work / f"{lid}.wav"
        tts(l["text"], l["delivery"], a.voice, wav)
        x = load(wav)
        words, _ = words_of(wav, l["text"])
        pause = l.get("pause_ms", 0) if i else 0
        if prev_hold_end is not None:
            t = max(t, prev_hold_end - 350)        # start under the tail of the laugh
        t += pause
        # trim leading silence measured by the ASR (keep 40 ms)
        lead = max(0, (words[0]["start_ms"] - 40) if words else 0)
        x = x[int(lead * SR / 1000):]
        words = [{**w, "start_ms": w["start_ms"] - lead, "end_ms": w["end_ms"] - lead} for w in words]
        dur = round(len(x) / SR * 1000)
        speech_end = words[-1]["end_ms"] if words else dur
        if lid in looks_before:
            lk = looks_before[lid]
            looks.append({"t_ms": round(t - max(450, min(900, pause))), "dur_ms": lk.get("ms", 900) + 400, "at": lk.get("at", "camera"), "line": lid})
        if lid in gestures_before:
            g = gestures_before[lid]
            gestures.append({"t_ms": round(t - 120), "kind": g.get("kind", "open"), "intensity": g.get("intensity", 0.8), "dur_ms": speech_end + 300, "line": lid})
        hit = None
        if l.get("emphasis"):
            for w in words:
                if w["word"].lower().strip("'") == l["emphasis"][0].lower():
                    hit = t + w["start_ms"]
        lines.append({"id": lid, "role": l["role"], "delivery": l["delivery"], "emotion": emo.get(lid, "neutral"),
                      "text": l["text"], "t_ms": round(t), "dur_ms": round(speech_end), "hit_ms": hit,
                      "emphasis": l.get("emphasis", []),
                      "words": [{"word": w["word"], "start_ms": round(t + w["start_ms"]), "end_ms": round(t + w["end_ms"])} for w in words]})
        vo_parts.append((t, x))
        t += speech_end
        prev_hold_end = None
        if l.get("hold_ms"):
            ld = max(l["hold_ms"], 1900 if l["role"] in ("punch", "callback", "closer") else 1300) / 1000
            size = 1.0 if l["role"] in ("punch", "callback") else 0.6
            lt = t + 180
            laughs.append({"t_ms": round(lt), "dur_ms": round(ld * 1000), "size": size, "after": lid})
            prev_hold_end = lt + ld * 1000
            t = lt + ld * 1000 * 0.9
    end = max(t, prev_hold_end or 0) + a.tail_ms
    n = int(end / 1000 * SR)
    vo = np.zeros(n, np.float32)
    for st, x in vo_parts:
        s = int(st / 1000 * SR)
        vo[s: s + len(x)] += x[: max(0, n - s)]
    vo = vo / max(1e-6, np.abs(vo).max()) * 0.85
    crowd = np.zeros(n, np.float32)
    for lg in laughs:
        y = laugh(lg["dur_ms"] / 1000, lg["size"], rng)
        s = int(lg["t_ms"] / 1000 * SR)
        crowd[s: s + len(y)] += y[: max(0, n - s)]
    room = bandpass(rng.standard_normal(n).astype(np.float32), 400, 0.5)
    room = room / max(1e-6, np.abs(room).max()) * 0.012
    vo_wet = reverb(vo, rng=rng)
    crowd_wet = reverb(crowd, rt=0.9, mix=0.35, rng=rng)
    mix_l = vo_wet + crowd_wet * 0.9 + room
    mix_r = vo_wet + np.roll(crowd_wet, int(0.011 * SR)) * 0.9 + np.roll(room, 977)
    peak = max(np.abs(mix_l).max(), np.abs(mix_r).max())
    st = np.stack([mix_l, mix_r], 1) / peak * 0.89
    (out / "vo.f32").write_bytes(st.astype(np.float32).tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(out / "vo.f32"),
                    "-c:a", "aac", "-b:a", "192k", str(out / "vo.m4a")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(out / "vo.f32"),
                    str(work / "mix.wav")], check=True)
    (out / "vo.f32").unlink()
    # loudness envelope of the dry comic VO per video frame (RMS over a 40 ms window, normalised to the 95th pct)
    hop = SR // a.fps
    nf = int(math.ceil(end / 1000 * a.fps))
    rms = np.array([math.sqrt(float(np.mean(vo[max(0, k * hop - hop // 2): k * hop + hop // 2] ** 2) or 0.0)) for k in range(nf)])
    ref = np.percentile(rms[rms > 1e-4], 95) if (rms > 1e-4).any() else 1.0
    env = np.clip(rms / ref, 0, 1.2)
    crowd_rms = np.array([math.sqrt(float(np.mean(crowd[max(0, k * hop - hop // 2): k * hop + hop // 2] ** 2) or 0.0)) for k in range(nf)])
    cref = crowd_rms.max() or 1.0
    tl = {"schema": "funnier.club-clip/v1", "set": S["id"], "character": S.get("character"), "character_name": S.get("character_name"),
          "fps": a.fps, "duration_ms": round(end), "voice": {"provider": "fish", "model": "s2.1-pro-free", "reference_id": a.voice},
          "lines": lines, "laughs": laughs, "looks": looks, "gestures": gestures,
          "env": [round(float(v), 3) for v in env], "crowd_env": [round(float(v / cref), 3) for v in crowd_rms]}
    (out / "timeline.json").write_text(json.dumps(tl, indent=1))
    (out / "clip.json").write_text(json.dumps({"set": S["id"], "lines": ids, "duration_ms": round(end), "fps": a.fps,
                                               "frames": nf}, indent=1))
    print(f"CLIP {out}: {len(ids)} lines, {len(laughs)} laughs, {end / 1000:.2f} s, {nf} frames")


if __name__ == "__main__":
    main()
