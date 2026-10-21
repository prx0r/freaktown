/**
 * ProsodyTrack — AU-prosody timeline sampled on the media clock.
 *
 * Mirrors MouthTrack: same clock, same binary-search sampling, opposite
 * channel. MouthTrack drives the mouth from phonemes; this drives brows
 * (accent), eyes (arousal) and blinks (phrase end) from aus.json
 * (backend/services/freaktown/au_track.py). Beats still decide emotion;
 * prosody only lifts where they're quiet.
 */

export interface ProsodyFrame {
  t_ms: number;
  accent: number; // 0-1 brow flash (AU1+AU2)
  arousal: number; // 0-1 eye widening (AU5)
  phrase_end: number; // 1 = blink + decay (AU45)
}

export interface ProsodySample {
  brow: number; // 0-1
  eye: number; // 0-1
  blink: number; // 0-1 pulse
}

const BLINK_MS = 150;

export class ProsodyTrack {
  private frames: ProsodyFrame[];

  constructor(frames: ProsodyFrame[] = []) {
    this.frames = [...frames].sort((a, b) => a.t_ms - b.t_ms);
  }

  get present(): boolean {
    return this.frames.length > 0;
  }

  sample(t: number): ProsodySample {
    const out: ProsodySample = { brow: 0, eye: 0, blink: 0 };
    const fs = this.frames;
    if (!fs.length) return out;
    let lo = 0, hi = fs.length - 1, idx = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (fs[mid].t_ms <= t) { idx = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    if (idx < 0) return out;
    const f = fs[idx];
    const age = t - f.t_ms;
    if (age > 400) return out; // stale frame: rest, don't freeze
    out.brow = Math.min(0.4, f.accent * 0.45);
    out.eye = Math.min(0.4, f.arousal * 0.3);
    if (f.phrase_end && age < BLINK_MS) out.blink = 1 - age / BLINK_MS;
    return out;
  }
}
