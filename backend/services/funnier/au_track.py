"""Audio prosody -> upper-face AU timeline (the speech-sync layer).

AUBlendNet's usable insight (ICCV'25, MIT; model itself needs 11 GB
VRAM + Baidu dataset, so not run here): drive the face in AU space,
not emotion-word space. This module is the honest subset runnable on
any CPU, stdlib only:

  - accent  (energy onsets ~ pitch accents) -> AU1+AU2 brow flash.
    Eyebrow flashes align with pitch accents in co-speech behaviour;
    this is timing, not mind-reading.
  - arousal (RMS energy)                   -> AU5 eye widening.
  - phrase  (low-energy gaps)              -> AU45 blink + decay to rest.

Mouth stays with visemes (TalkingHead-en/Rhubarb timelines); this
module never writes mouth morphs, so the two channels can't fight.
Output frames feed ExpressionLayer.setProsody per clock tick — small
additive offsets UNDER beat/reactor emotions (beats win ties).

Pure functions + one wav reader. Tested with synthetic envelopes.
"""

import math
import struct
import wave

FRAME_MS = 40  # AU timeline resolution
ONSET_WIN_MS = 120  # onset detection window
PHRASE_GAP_MS = 350  # silence that ends a phrase


def read_mono(wav_path, target_rate=16000):
    """WAV -> (samples in [-1, 1], rate). Mono-mixes; resamples linearly
    only when needed (keeps common 16k/24k/48k cheap)."""
    with wave.open(wav_path, "rb") as w:
        sr, n, sw, ch = (w.getframerate(), w.getnframes(),
                         w.getsampwidth(), w.getnchannels())
        raw = w.readframes(n)
    fmt = {1: "b", 2: "h", 4: "i"}[sw]
    count = len(raw) // sw
    smp = struct.unpack("<%d%s" % (count, fmt), raw)
    if ch == 2:
        smp = smp[0::2]
    peak = float(2 ** (8 * sw - 1))
    norm = [x / peak for x in smp]
    if sr == target_rate:
        return norm, sr
    ratio = sr / target_rate
    n_out = int(len(norm) / ratio)
    return [norm[int(i * ratio)] for i in range(n_out)], target_rate


def rms_envelope(samples, rate, win_ms=FRAME_MS):
    win = max(1, int(rate * win_ms / 1000))
    out = []
    for i in range(0, len(samples), win):
        seg = samples[i:i + win]
        if not seg:
            break
        out.append(math.sqrt(sum(x * x for x in seg) / len(seg)))
    return out


def prosody_track(samples, rate=16000, frame_ms=FRAME_MS):
    """Envelope -> per-frame {t_ms, accent, arousal, phrase_end}.

    Absolute (dB-anchored) scales, so a whisper take reads calm and a
    shout reads hot — no per-track normalization that would force every
    take to full arousal:
    - accent: fast absolute energy rise 0-1 (onsets ~ pitch accents).
    - arousal: RMS mapped (-42..-12 dB) -> 0-1 (loud passages widen eyes).
    - phrase_end: 1 on the single frame a >=PHRASE_GAP_MS near-silence
      (<0.02 RMS) closes, i.e. blink + decay to rest.
    Never raises; empty audio gives empty frames."""
    try:
        env = rms_envelope(samples, rate, win_ms=frame_ms)
    except Exception:
        return []
    if not env:
        return []
    frames = []
    run, silence = 0.0, 0
    gap_frames = max(1, int(PHRASE_GAP_MS / frame_ms))
    for i, v in enumerate(env):
        run += (v - run) * 0.25
        onset = max(0.0, v - run)
        accent = max(0.0, min(1.0, (onset - 0.03) / 0.15))
        try:
            db = 20 * math.log10(v + 1e-9)
        except Exception:
            db = -180.0
        arousal = max(0.0, min(1.0, (db + 42.0) / 30.0))
        silence = silence + 1 if v < 0.02 else 0
        phrase_end = 1 if silence == gap_frames else 0
        frames.append({"t_ms": i * frame_ms, "accent": round(accent, 3),
                       "arousal": round(arousal, 3),
                       "phrase_end": phrase_end})
    return frames


def build_aus(wav_path, rate=16000):
    """Take wav -> AU prosody frames. File-level entry point."""
    try:
        samples, sr = read_mono(wav_path, target_rate=rate)
    except Exception:
        return []
    return prosody_track(samples, rate=sr)
