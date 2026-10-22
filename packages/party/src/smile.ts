/**
 * Measured smile (human) — MediaPipe FaceLandmarker blendshapes → one 0..1 score.
 * Uses the stage-runtime port of affect-servo smileFusion
 * (mouthSmileL/R + cheekSquint/eyeSquint + a little jawOpen). Runs on-device;
 * only the resulting number (and game events) ever leave the browser.
 */
import { smileFusion, type Blendshapes } from '@funnier/stage-runtime/face/arkit';

export { smileFusion };
export type { Blendshapes };

/** MediaPipe `faceBlendshapes[0].categories` → name→score map. */
export function categoriesToBlendshapes(cats: Array<{ categoryName: string; score: number }>): Blendshapes {
  const out: Blendshapes = {};
  for (const c of cats) out[c.categoryName] = c.score;
  return out;
}

export function smileScore(bs: Blendshapes): number {
  return smileFusion(bs);
}

/**
 * Synthetic blendshape frame for a target smile level (tests, the fake-webcam
 * e2e and the simulated-round render). Inverts smileFusion along a fixed mix
 * so smileScore(syntheticFrame(x)) ≈ x.
 */
export function syntheticFrame(level: number): Blendshapes {
  // smileFusion: x = .42*smile + .30*squint + .10*jaw; score = (x - .18)/.55
  const target = Math.max(0, Math.min(1, level)) * 0.55 + 0.18;
  // keep smile:squint:jaw at 1 : .8 : .15 → x = (.42 + .24 + .015) * m = .675 m
  const m = Math.min(1, target / 0.675);
  return {
    mouthSmileLeft: m, mouthSmileRight: m,
    cheekSquintLeft: m * 0.8, cheekSquintRight: m * 0.8, eyeSquintLeft: m * 0.8, eyeSquintRight: m * 0.8,
    jawOpen: m * 0.15,
  };
}
