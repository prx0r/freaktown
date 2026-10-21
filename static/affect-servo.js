/* Affect servo — (arousal, valence, power) → delivery params.
 *
 * Handwired-subset discipline (compilable later — mechanical translation):
 *   - pure functions only: same inputs → same outputs, no I/O, no Date, no random
 *   - branches ONLY via relu gates: gate(x) = relu(x) - relu(x-1) is 1 when
 *     x >= 1 else 0 for the 0/1-bounded signals used here; blends pick branches
 *   - all state passed in, all state returned (room weights = explicit args)
 *
 * Inputs A/V/P in [-1, 1]. Weights object carries room tuning (starts at
 * defaults = the legible rules; learns per room later).
 */
(function (global) {
  "use strict";

  function relu(x) { return x > 0 ? x : 0; }

  // 0/1 gate for a signal already in [0,1]: 1 when x >= t else 0.
  function gate(x, t) {
    const s = 40; // sharpness; exact in the limit, smooth enough to train
    return relu(Math.min(1, Math.max(0, (x - t) * s + 0.5)));
  }

  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }

  const DEFAULT_WEIGHTS = {
    energyBase: 0.55, energyArousal: 0.35, energyValence: 0.10,
    paceBase: 1.0, paceArousal: 0.18, paceValence: 0.06,
    pauseBaseMs: 900, pauseArousalMs: -350, pauseValenceMs: -100,
    emphasisBase: 0.5, emphasisPower: 0.3,
    hotThreshold: 0.65, hotBoost: 0.15,
  };

  // (A, V, P) → {energy 0..1, pace multiplier, pauseMs, emphasis 0..1}.
  // Hot branch (high arousal): shorter pauses, +energy — blended by gate,
  // never a cliff (trainable later via weights).
  function affectToDelivery(a, v, p, w) {
    w = Object.assign({}, DEFAULT_WEIGHTS, w || {});
    const hot = gate((a + 1) / 2, w.hotThreshold);
    const coldW = 1 - hot;
    const energy = clamp01(w.energyBase + w.energyArousal * a + w.energyValence * v
      + hot * w.hotBoost);
    const pace = Math.max(0.6, w.paceBase + w.paceArousal * a + w.paceValence * v);
    const pauseMs = Math.max(250, (w.pauseBaseMs + w.pauseArousalMs * a
      + w.pauseValenceMs * v) * coldW + 450 * hot);
    const emphasis = clamp01(w.emphasisBase + w.emphasisPower * p);
    return { energy: r3(energy), pace: r3(pace), pauseMs: Math.round(pauseMs),
             emphasis: r3(emphasis), hot: hot > 0.5 };
  }

  function r3(x) { return Math.round(x * 1000) / 1000; }

  // 52-blendshape vector (ARKit names, subset read) → break probability.
  // signals: {mouthSmileLeft, mouthSmileRight, cheekSquintLeft,
  //           cheekSquintRight, eyeSquintLeft, eyeSquintRight, jawOpen}
  // Exact day one; weights tune per room in calibration.
  function smileFusion(s, w) {
    w = w || {};
    const wSmile = w.smile == null ? 0.42 : w.smile;
    const wSquint = w.squint == null ? 0.30 : w.squint;
    const wJaw = w.jaw == null ? 0.10 : w.jaw;
    const g = function (k) { return clamp01(s[k] == null ? 0 : s[k]); };
    const smile = (g("mouthSmileLeft") + g("mouthSmileRight")) / 2;
    const squint = (g("cheekSquintLeft") + g("cheekSquintRight")
      + g("eyeSquintLeft") + g("eyeSquintRight")) / 2 / 2;
    const jaw = g("jawOpen");
    const x = wSmile * smile + wSquint * squint + wJaw * jaw;
    return r3(clamp01((x - 0.18) / 0.55));
  }

  // Vote weight from decision speed (Quiplash snap/confidence shape).
  function voteWeight(decisionMs) {
    const fast = 1 - gate(decisionMs / 12000, 0.125); // <1.5s → 1
    const slow = gate(decisionMs / 12000, 1.0);      // >12s → 1
    return r3(1 + 0.25 * fast - 0.3 * slow);
  }

  global.AffectServo = {
    affectToDelivery: affectToDelivery,
    smileFusion: smileFusion,
    voteWeight: voteWeight,
    DEFAULT_WEIGHTS: DEFAULT_WEIGHTS,
    relu: relu, gate: gate,
  };
})(typeof window !== "undefined" ? window : this);
