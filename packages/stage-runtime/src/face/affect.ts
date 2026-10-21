/**
 * Affect servo — (arousal, valence, power) in [-1,1].
 * affectToDelivery is a straight port of static/affect-servo.js (lab rig on
 * feature/mutuals-acting-party-smiles / main 4cfe7c3): relu-gated, pure.
 * affectToEmotions is new here: a documented A/V/P → VRM-5 emotion projection so
 * a set (or a live affect feed) can steer a face with three numbers.
 */
import type { Emotions } from '../avatars/types';

const relu = (x: number) => (x > 0 ? x : 0);
const gate = (x: number, t: number) => relu(Math.min(1, Math.max(0, (x - t) * 40 + 0.5)));
const c01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
const r3 = (x: number) => Math.round(x * 1000) / 1000;

export const AFFECT_DEFAULT_WEIGHTS = {
  energyBase: 0.55, energyArousal: 0.35, energyValence: 0.10,
  paceBase: 1.0, paceArousal: 0.18, paceValence: 0.06,
  pauseBaseMs: 900, pauseArousalMs: -350, pauseValenceMs: -100,
  emphasisBase: 0.5, emphasisPower: 0.3,
  hotThreshold: 0.65, hotBoost: 0.15,
};
export type AffectWeights = typeof AFFECT_DEFAULT_WEIGHTS;

export function affectToDelivery(a: number, v: number, p: number, w: Partial<AffectWeights> = {}) {
  const W = { ...AFFECT_DEFAULT_WEIGHTS, ...w };
  const hot = gate((a + 1) / 2, W.hotThreshold);
  const energy = c01(W.energyBase + W.energyArousal * a + W.energyValence * v + hot * W.hotBoost);
  const pace = Math.max(0.6, W.paceBase + W.paceArousal * a + W.paceValence * v);
  const pauseMs = Math.max(250, (W.pauseBaseMs + W.pauseArousalMs * a + W.pauseValenceMs * v) * (1 - hot) + 450 * hot);
  const emphasis = c01(W.emphasisBase + W.emphasisPower * p);
  return { energy: r3(energy), pace: r3(pace), pauseMs: Math.round(pauseMs), emphasis: r3(emphasis), hot: hot > 0.5 };
}

/** A/V/P → emotions: +V happy, −V sad (low A) / angry (high A, +P), high A surprised, low A relaxed. */
export function affectToEmotions(a: number, v: number, p = 0): Emotions {
  const A = Math.max(-1, Math.min(1, a)), V = Math.max(-1, Math.min(1, v)), P = Math.max(-1, Math.min(1, p));
  return {
    happy: r3(c01(V) * (0.7 + 0.3 * c01(A + 0.5))),
    sad: r3(c01(-V) * c01(0.6 - A * 0.6 - P * 0.3)),
    angry: r3(c01(-V) * c01(A * 0.8 + P * 0.5)),
    surprised: r3(c01(A - 0.4) * (1 - c01(-V) * 0.5)),
    relaxed: r3(c01(-A) * 0.6 * (1 - c01(-V))),
  };
}
