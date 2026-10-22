/**
 * Neutral-face calibration + fairness.
 *
 * At join the player holds a neutral face for ~3 s; we take the smile score
 * samples (smileFusion of their blendshapes) and record a personal baseline.
 * Every later sample is scored RELATIVE to that baseline, so a resting smiler
 * (whose neutral face already reads 0.3) is not eliminated for having a face:
 *
 *   adjusted = clamp01((raw - baseline) / (1 - baseline))
 *
 * A baseline above `restingSmileMax` flags the player as a resting smiler —
 * the UI says so, and the fairness check in the rules keeps the same hold
 * time for everyone (no extra penalty, no extra leniency beyond the offset).
 * Noisy calibrations (moving, talking, bad light) are rejected and retried.
 */
import { clamp01, round3 } from './rng';

export interface CalibrationResult {
  ok: boolean;
  baseline: number;
  spread: number;
  samples: number;
  restingSmiler: boolean;
  /** Why it failed (when !ok). */
  reason?: 'too-few-samples' | 'too-noisy' | 'already-smiling';
}

export interface CalibrationOptions {
  minSamples?: number;
  maxSpread?: number;
  restingSmileMax?: number;
  /** A "neutral" face above this is not neutral: ask again. */
  maxBaseline?: number;
}

const median = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export function calibrateNeutral(samples: number[], o: CalibrationOptions = {}): CalibrationResult {
  const minSamples = o.minSamples ?? 20;
  const maxSpread = o.maxSpread ?? 0.12;
  const restingSmileMax = o.restingSmileMax ?? 0.3;
  const maxBaseline = o.maxBaseline ?? 0.6;
  const xs = samples.filter((x) => Number.isFinite(x)).map(clamp01);
  if (xs.length < minSamples) return { ok: false, baseline: 0, spread: 0, samples: xs.length, restingSmiler: false, reason: 'too-few-samples' };
  const base = median(xs);
  // robust spread: median absolute deviation, scaled to ~stdev
  const spread = median(xs.map((x) => Math.abs(x - base))) * 1.4826;
  if (spread > maxSpread) return { ok: false, baseline: round3(base), spread: round3(spread), samples: xs.length, restingSmiler: false, reason: 'too-noisy' };
  if (base > maxBaseline) return { ok: false, baseline: round3(base), spread: round3(spread), samples: xs.length, restingSmiler: true, reason: 'already-smiling' };
  return { ok: true, baseline: round3(base), spread: round3(spread), samples: xs.length, restingSmiler: base > restingSmileMax };
}

/** Raw smile score → score relative to the player's own neutral face. */
export function adjustSmile(raw: number, baseline: number): number {
  const b = clamp01(baseline);
  return round3(clamp01((clamp01(raw) - b) / Math.max(0.2, 1 - b)));
}

/** Mean luma (0..1) of an RGBA buffer; the lighting check samples every 16th pixel. */
export function lumaOf(rgba: ArrayLike<number>, stride = 16): number {
  let sum = 0, n = 0;
  for (let i = 0; i + 2 < rgba.length; i += 4 * stride) {
    sum += (0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2]) / 255;
    n++;
  }
  return n ? round3(sum / n) : 0;
}
