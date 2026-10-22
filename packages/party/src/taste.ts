/**
 * Agent taste model + HONEST simulated smile.
 *
 * Agents have no faces to measure. Their "smile" is a scripted probability:
 *   rating   = how funny THIS agent finds THIS joke (taste weights × joke
 *              mechanisms + the writer's quality estimate + seeded noise,
 *              minus fatigue for repeated mechanisms)
 *   p(crack) = sigmoid((rating - composure) × steepness)
 * One seeded draw decides crack / hold. The result is a smile CURVE (0..1 over
 * time) that is fed to the same rules engine as a human's measured samples,
 * flagged `simulated: true`, and shown on the agent's face via face.expression.
 * The UI labels every agent meter "simulated".
 */
import { clamp01, round3, sigmoid, type Rng } from './rng';
import { MECHANISMS, type Joke, type Mechanism } from './jokes';

export interface TasteModel {
  /** -1..1 per mechanism: how much this agent likes it. */
  weights: Partial<Record<Mechanism, number>>;
  /** 0..1: how hard this agent is to crack. */
  composure: number;
  /** 0..0.3: randomness in its rating. */
  volatility: number;
  /** Reaction latency after the punch (ms). */
  reaction_ms: number;
}

export const NEUTRAL_TASTE: TasteModel = { weights: {}, composure: 0.6, volatility: 0.1, reaction_ms: 350 };

export interface Rating { rating: number; pCrack: number }

export function rateJoke(taste: TasteModel, joke: Joke, rng: Rng, seenMechanisms: Mechanism[] = []): Rating {
  let affinity = 0;
  for (const t of joke.tags) affinity += taste.weights[t] ?? 0;
  affinity /= Math.max(1, joke.tags.length);
  const fatigue = joke.tags.reduce((n, t) => n + seenMechanisms.filter((m) => m === t).length, 0) * 0.03;
  const noise = (rng() * 2 - 1) * taste.volatility;
  const rating = clamp01(0.25 + 0.35 * affinity + 0.45 * joke.quality + noise - fatigue);
  const pCrack = sigmoid((rating - taste.composure) * 9);
  return { rating: round3(rating), pCrack: round3(pCrack) };
}

export interface SmileCurve {
  cracked: boolean;
  rating: number;
  pCrack: number;
  /** Peak smile level (0..1) and timing relative to the punchline (ms). */
  peak: number;
  onset_ms: number;
  hold_ms: number;
  release_ms: number;
}

/** Decide (seeded) whether the agent cracks, and shape the smile it shows. */
export function reactToJoke(taste: TasteModel, joke: Joke, rng: Rng, seen: Mechanism[] = []): SmileCurve {
  const { rating, pCrack } = rateJoke(taste, joke, rng, seen);
  const cracked = rng() < pCrack;
  const onset = taste.reaction_ms + Math.round(rng() * 250);
  if (cracked) {
    return { cracked, rating, pCrack, peak: round3(0.65 + 0.3 * rng()), onset_ms: onset, hold_ms: 700 + Math.round(rng() * 900), release_ms: 500 };
  }
  // a fought-off twitch: visible, stays under threshold
  return { cracked, rating, pCrack, peak: round3(0.12 + 0.3 * rating * rng()), onset_ms: onset, hold_ms: 250 + Math.round(rng() * 200), release_ms: 300 };
}

/** Smile level at `ms` after the punch for a curve (ramp up 200 ms, hold, release). */
export function curveAt(c: SmileCurve, ms: number): number {
  const up = 200;
  const t = ms - c.onset_ms;
  if (t <= 0) return 0;
  if (t < up) return round3(c.peak * (t / up));
  if (t < up + c.hold_ms) return c.peak;
  const r = t - up - c.hold_ms;
  if (r < c.release_ms) return round3(c.peak * (1 - r / c.release_ms));
  return 0;
}

/** Random-but-seeded taste for a new identity (P3 creation flow). */
export function randomTaste(rng: Rng, likes: Mechanism[] = []): TasteModel {
  const weights: Partial<Record<Mechanism, number>> = {};
  for (const m of MECHANISMS) weights[m] = round3(likes.includes(m) ? 0.5 + 0.5 * rng() : rng() * 1.2 - 0.6);
  return { weights, composure: round3(0.45 + 0.35 * rng()), volatility: round3(0.05 + 0.15 * rng()), reaction_ms: 250 + Math.round(rng() * 300) };
}
