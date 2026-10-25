/**
 * ARKit-52 / Oculus-15 / VRM-5 face vocabularies and the maps between them.
 *
 * Ported from feature/mutuals-acting-party-smiles (008d4f5): app.py ARKIT_MOUTH /
 * OCULUS_MOUTH (GLB sniffing), WAWA_MAP (Oculus-15 → VRM-5, "v1 approximations,
 * AB-tested"), applyFace (MediaPipe 52 blendshapes → VRM presets), and
 * static/affect-servo.js smileFusion. Pure functions, no three.js.
 */
import type { Emotions, Visemes } from '../avatars/types';

export const ARKIT_52 = [
  'browDownLeft', 'browDownRight', 'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight',
  'cheekPuff', 'cheekSquintLeft', 'cheekSquintRight',
  'eyeBlinkLeft', 'eyeBlinkRight', 'eyeLookDownLeft', 'eyeLookDownRight', 'eyeLookInLeft', 'eyeLookInRight',
  'eyeLookOutLeft', 'eyeLookOutRight', 'eyeLookUpLeft', 'eyeLookUpRight', 'eyeSquintLeft', 'eyeSquintRight',
  'eyeWideLeft', 'eyeWideRight',
  'jawForward', 'jawLeft', 'jawOpen', 'jawRight',
  'mouthClose', 'mouthDimpleLeft', 'mouthDimpleRight', 'mouthFrownLeft', 'mouthFrownRight', 'mouthFunnel',
  'mouthLeft', 'mouthLowerDownLeft', 'mouthLowerDownRight', 'mouthPressLeft', 'mouthPressRight', 'mouthPucker',
  'mouthRight', 'mouthRollLower', 'mouthRollUpper', 'mouthShrugLower', 'mouthShrugUpper',
  'mouthSmileLeft', 'mouthSmileRight', 'mouthStretchLeft', 'mouthStretchRight',
  'mouthUpperUpLeft', 'mouthUpperUpRight', 'noseSneerLeft', 'noseSneerRight', 'tongueOut',
] as const;
export type ArkitName = (typeof ARKIT_52)[number];
export type Blendshapes = Partial<Record<string, number>>;

/** Mouth subset that makes a GLB "lipsync-capable" (app.py ARKIT_MOUTH). */
export const ARKIT_MOUTH = new Set<string>([
  'jawOpen', 'mouthClose', 'mouthFunnel', 'mouthPucker', 'mouthLeft', 'mouthRight', 'mouthSmileLeft', 'mouthSmileRight',
  'mouthFrownLeft', 'mouthFrownRight', 'mouthDimpleLeft', 'mouthDimpleRight', 'mouthStretchLeft', 'mouthStretchRight',
  'mouthRollLower', 'mouthRollUpper', 'mouthShrugLower', 'mouthShrugUpper', 'mouthPressLeft', 'mouthPressRight',
  'mouthLowerDownLeft', 'mouthLowerDownRight', 'mouthUpperUpLeft', 'mouthUpperUpRight',
]);

export const OCULUS_15 = ['sil', 'PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS', 'nn', 'RR', 'aa', 'E', 'I', 'O', 'U'] as const;
export type OculusViseme = (typeof OCULUS_15)[number];

/** Oculus-15 → VRM-5 (WAWA_MAP): [preset, weight]; sil → closed. */
export const OCULUS_TO_VRM: Record<OculusViseme, [keyof Visemes, number] | null> = {
  sil: null, PP: ['ou', 0.5], FF: ['ih', 0.6], TH: ['ih', 0.5], DD: ['ee', 0.6], kk: ['aa', 0.4],
  CH: ['oh', 0.6], SS: ['ih', 0.7], nn: ['ee', 0.4], RR: ['ou', 0.6], aa: ['aa', 1.0], E: ['ee', 0.9],
  I: ['ih', 0.9], O: ['oh', 0.9], U: ['ou', 0.9],
};

const ZV = (): Visemes => ({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
const ZE = (): Emotions => ({ happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 });
const c01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

/** One Oculus viseme code (with or without "viseme_" prefix) → VRM-5 weights. */
export function oculusToVisemes(code: string, weight = 1): { open: number; visemes: Visemes } {
  const key = code.replace(/^viseme_/, '') as OculusViseme;
  const hit = OCULUS_TO_VRM[key];
  const v = ZV();
  if (!hit) return { open: 0, visemes: v };
  v[hit[0]] = c01(hit[1] * weight);
  return { open: v[hit[0]], visemes: v };
}

/** A full face frame every driver understands (VRM presets + open + blink). */
export interface FaceFrame {
  open: number;
  visemes: Visemes;
  emotions: Emotions;
  blink: number;
  /** Raw ARKit weights, for drivers that carry them (GLB morphs / VRM custom). */
  blendshapes?: Blendshapes;
  /** Extra expressive channels (brow flash, the look's furrow, squint, smirk, gaze, per-eye blink). */
  expressive?: { browUp?: number; browDown?: number; squint?: number; smirk?: number; lookX?: number; lookY?: number; blinkL?: number; blinkR?: number };
}

/**
 * ARKit-52 (e.g. MediaPipe FaceLandmarker categories) → FaceFrame.
 * Visemes: VRM names if the source has them (MediaPipe on VRM rigs), else derived
 * from jawOpen / funnel / pucker / smile / stretch. Emotions are derived (documented
 * approximations): happy = smile (fused with squint), surprised = browInnerUp + eyeWide,
 * angry = browDown + sneer, sad = frown + inner brow, relaxed = low arousal residue.
 */
export function arkitToFace(cats: Blendshapes): FaceFrame {
  const g = (k: string) => c01(Number(cats[k] ?? 0));
  const avg = (a: string, b: string) => (g(a) + g(b)) / 2;
  const jaw = Math.max(g('jawOpen'), g('mouthOpen'), g('aa'));
  const v = ZV();
  if (['aa', 'ee', 'ih', 'oh', 'ou'].some((k) => cats[k] !== undefined)) {
    for (const k of Object.keys(v) as (keyof Visemes)[]) v[k] = g(k);
  } else {
    const funnel = g('mouthFunnel'), pucker = g('mouthPucker'), stretch = avg('mouthStretchLeft', 'mouthStretchRight');
    const smile = avg('mouthSmileLeft', 'mouthSmileRight');
    v.oh = c01(funnel * 0.9 + jaw * 0.2);
    v.ou = c01(pucker * 0.9);
    v.ee = c01(stretch * 0.7 + smile * 0.3) * (jaw > 0.05 ? 1 : 0.4);
    v.ih = c01(jaw * 0.35 + stretch * 0.2) * (1 - funnel);
    v.aa = c01(jaw - funnel * 0.5 - pucker * 0.5);
  }
  const e = ZE();
  e.happy = smileFusion(cats);
  e.surprised = c01(g('browInnerUp') * 0.6 + avg('eyeWideLeft', 'eyeWideRight') * 0.6 + jaw * 0.15);
  e.angry = c01(avg('browDownLeft', 'browDownRight') * 0.8 + avg('noseSneerLeft', 'noseSneerRight') * 0.4);
  e.sad = c01(avg('mouthFrownLeft', 'mouthFrownRight') * 0.8 + g('browInnerUp') * 0.25 - e.happy * 0.5);
  e.relaxed = c01(0.3 - jaw - e.surprised - e.angry) * 0.5;
  return {
    open: jaw, visemes: v, emotions: e,
    blink: Math.max(g('eyeBlinkLeft'), g('eyeBlinkRight')),
    blendshapes: { ...cats },
  };
}

/** affect-servo.js smileFusion: smile + cheek/eye squint + jaw → 0..1 "smile" (break probability). */
export function smileFusion(s: Blendshapes, w: { smile?: number; squint?: number; jaw?: number } = {}): number {
  const g = (k: string) => c01(Number(s[k] ?? 0));
  const smile = (g('mouthSmileLeft') + g('mouthSmileRight')) / 2;
  const squint = (g('cheekSquintLeft') + g('cheekSquintRight') + g('eyeSquintLeft') + g('eyeSquintRight')) / 4;
  const x = (w.smile ?? 0.42) * smile + (w.squint ?? 0.3) * squint + (w.jaw ?? 0.1) * g('jawOpen');
  return Math.round(c01((x - 0.18) / 0.55) * 1000) / 1000;
}

/** VRM-5 visemes + emotions → ARKit weights (for ARKit-only GLBs driven by our plan/text mouth). */
export function faceToArkit(f: Pick<FaceFrame, 'open' | 'visemes' | 'emotions' | 'blink'>): Blendshapes {
  const { visemes: v, emotions: e } = f;
  return {
    jawOpen: c01(Math.max(f.open * 0.8, v.aa, v.oh * 0.7)),
    mouthFunnel: c01(v.oh * 0.8), mouthPucker: c01(v.ou * 0.9),
    mouthStretchLeft: c01(v.ee * 0.6 + v.ih * 0.3), mouthStretchRight: c01(v.ee * 0.6 + v.ih * 0.3),
    mouthSmileLeft: c01(e.happy * 0.9), mouthSmileRight: c01(e.happy * 0.9),
    mouthFrownLeft: c01(e.sad * 0.8), mouthFrownRight: c01(e.sad * 0.8),
    browDownLeft: c01(e.angry * 0.9), browDownRight: c01(e.angry * 0.9),
    browInnerUp: c01(e.surprised * 0.8 + e.sad * 0.4),
    eyeWideLeft: c01(e.surprised * 0.7), eyeWideRight: c01(e.surprised * 0.7),
    noseSneerLeft: c01(e.angry * 0.3), noseSneerRight: c01(e.angry * 0.3),
    cheekSquintLeft: c01(e.happy * 0.5), cheekSquintRight: c01(e.happy * 0.5),
    eyeBlinkLeft: c01(f.blink), eyeBlinkRight: c01(f.blink),
  };
}
