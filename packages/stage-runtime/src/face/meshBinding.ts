/**
 * meshBinding — which face channels a mesh can drive, from names alone.
 *
 * Pure (no three.js): the stage's GlbAvatar and the `face:check` CLI both
 * call bindFace() with the morph-target names and bone names found in a
 * GLB, so "what the CLI reports" and "what the stage drives" are the same
 * function. Names are matched through an alias map after normalisation
 * (case, separators, exporter prefixes like `blendShape1.` / `Key.` /
 * `vrc.` are ignored), so ARKit, Oculus/VRChat, VRM0/VRoid, CC4/iClone,
 * Daz/Genesis and hand-named Blender shapes all land on the same channels.
 *
 * Mouth order (first that exists wins):
 *   visemes (≥2 of aa/ih/ou/ee/oh)  → 'viseme'
 *   an open/jaw morph               → 'morph'
 *   a jaw bone                      → 'jaw'
 *   nothing                         → 'none'  (warned; see docs/MESH-FACE-HOOKUP.md)
 */

export type FaceMouthMode = 'viseme' | 'morph' | 'jaw' | 'none';
export type FaceVisemeKey = 'aa' | 'ih' | 'ou' | 'ee' | 'oh';
export type FaceEmotionKey = 'happy' | 'angry' | 'sad' | 'surprised' | 'relaxed';

/** Lower-case, strip exporter prefixes and every non-alphanumeric. */
export function normFaceName(name: string): string {
  let s = name.trim();
  // "blendShape1.jawOpen", "Key 1|jawOpen", "Face:jawOpen", "vrc.v_aa"
  const cut = Math.max(s.lastIndexOf('.'), s.lastIndexOf('|'), s.lastIndexOf(':'));
  if (cut >= 0 && cut < s.length - 1) s = s.slice(cut + 1);
  return s.toLowerCase().replace(/[^a-z0-9\u3040-\u30ff]/g, '');
}

const n = (...names: string[]) => names.map(normFaceName);

/** Normalised aliases per channel. Add a name here and every mesh using it hooks in. */
export const MESH_FACE_ALIASES = {
  open: n('jawOpen', 'mouthOpen', 'jaw_open', 'Mouth_Open', 'JawDown', 'jaw_down', 'mouth_wide', 'MouthWide', 'A_Open', 'Jaw_Open', 'CC_Base_JawOpen', 'mouthopen_jaw', 'MTH_OPEN'),
  visemes: {
    aa: n('viseme_aa', 'v_aa', 'aa', 'A', 'mouth_a', 'Fcl_MTH_A', 'vrc.v_aa', 'MTH_A', 'Viseme_AA', 'AE', 'あ'),
    ih: n('viseme_I', 'viseme_ih', 'v_ih', 'ih', 'I', 'mouth_i', 'Fcl_MTH_I', 'vrc.v_ih', 'MTH_I', 'Viseme_IH', 'い'),
    ou: n('viseme_U', 'viseme_ou', 'v_ou', 'ou', 'U', 'mouth_u', 'Fcl_MTH_U', 'vrc.v_ou', 'MTH_U', 'Viseme_OU', 'う'),
    ee: n('viseme_E', 'viseme_ee', 'v_e', 'v_ee', 'ee', 'E', 'mouth_e', 'Fcl_MTH_E', 'vrc.v_e', 'MTH_E', 'Viseme_EE', 'え'),
    oh: n('viseme_O', 'viseme_oh', 'v_oh', 'oh', 'O', 'mouth_o', 'Fcl_MTH_O', 'vrc.v_oh', 'MTH_O', 'Viseme_OH', 'お'),
  } as Record<FaceVisemeKey, string[]>,
  blinkLeft: n('eyeBlinkLeft', 'eyeBlink_L', 'Eye_Blink_L', 'blinkLeft', 'blink_L', 'eyeClosedLeft', 'eyeCloseLeft', 'Eyes_Closed_L', 'Fcl_EYE_Close_L', 'EyeBlink_L', 'eye_close_l', 'eyeBlinkL'),
  blinkRight: n('eyeBlinkRight', 'eyeBlink_R', 'Eye_Blink_R', 'blinkRight', 'blink_R', 'eyeClosedRight', 'eyeCloseRight', 'Eyes_Closed_R', 'Fcl_EYE_Close_R', 'EyeBlink_R', 'eye_close_r', 'eyeBlinkR'),
  blinkBoth: n('blink', 'Blink', 'eyesClosed', 'Eyes_Closed', 'eyeClose', 'eyes_close', 'Fcl_EYE_Close', 'blink_both', 'まばたき'),
  emotions: {
    // FACS-calibrated (AUBlendNet Table 2; see face_profiles.py):
    // Happy AU6+12, Anger AU4+5+7+9+23, Sad AU1+4+15, Surprise AU1+2+5+27.
    happy: n('mouthSmileLeft', 'mouthSmileRight', 'cheekSquintLeft', 'cheekSquintRight', 'happy', 'smile', 'Mouth_Smile', 'Mouth_Smile_L', 'Mouth_Smile_R', 'Fcl_ALL_Joy', 'joy'),
    angry: n('browDownLeft', 'browDownRight', 'eyeSquintLeft', 'eyeSquintRight', 'noseSneerLeft', 'noseSneerRight', 'mouthPressLeft', 'mouthPressRight', 'angry', 'Fcl_ALL_Angry'),
    sad: n('mouthFrownLeft', 'mouthFrownRight', 'browInnerUp', 'sad', 'sorrow', 'Fcl_ALL_Sorrow'),
    // jawOpen is deliberately NOT here: the mouth channel owns it (a surprise
    // jaw is added to the mouth instead of fighting it every frame).
    surprised: n('browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'eyeWideLeft', 'eyeWideRight', 'surprised', 'Fcl_ALL_Surprised'),
    relaxed: n('relaxed', 'fun', 'Fcl_ALL_Fun'),
  } as Record<FaceEmotionKey, string[]>,
  prosodyBrow: n('browInnerUp', 'browOuterUpLeft', 'browOuterUpRight'),
  prosodyEye: n('eyeWideLeft', 'eyeWideRight'),
};

/** Jaw bones: exact-ish names first; "_end"/"nub" leaf helpers never count. */
const JAW_BONE = /(^|[^a-z])(jaw|lowerjaw|jawroot|jaw_?bone|chin)([^a-z]|$)|jaw$/i;
const HEAD_BONE = /(^|[^a-z])head([^a-z]|$)|head$/i;
const SPINE_BONE = /spine2|spine1|spine02|spine01|spine|chest/i;
const HELPER = /(_end|end$|nub|top|front|_tip|tip$|null)/i;

export function pickBone(names: string[], re: RegExp): string | null {
  const hits = names.filter((b) => re.test(b) && !HELPER.test(b));
  if (!hits.length) return null;
  // shortest name wins ("Head" over "HeadTop_Ctrl"), stable for ties
  return hits.reduce((a, b) => (b.length < a.length ? b : a));
}

export interface FaceBinding {
  /** channel → the ORIGINAL morph names that feed it */
  visemes: Partial<Record<FaceVisemeKey, string[]>>;
  open: string[];
  blink: string[];
  blinkLeft: string[];
  blinkRight: string[];
  emotions: Partial<Record<FaceEmotionKey, string[]>>;
  prosodyBrow: string[];
  prosodyEye: string[];
  jawBone: string | null;
  headBone: string | null;
  spineBone: string | null;
  mouthMode: FaceMouthMode;
  hasBlink: boolean;
  hasExpressions: boolean;
  /** morph names nothing binds (ARKit names still reach setBlendshapes) */
  unbound: string[];
  arkitCount: number;
  warnings: string[];
}

const ARKIT_SET = new Set(n(
  'browDownLeft', 'browDownRight', 'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'cheekPuff', 'cheekSquintLeft', 'cheekSquintRight',
  'eyeBlinkLeft', 'eyeBlinkRight', 'eyeLookDownLeft', 'eyeLookDownRight', 'eyeLookInLeft', 'eyeLookInRight', 'eyeLookOutLeft', 'eyeLookOutRight',
  'eyeLookUpLeft', 'eyeLookUpRight', 'eyeSquintLeft', 'eyeSquintRight', 'eyeWideLeft', 'eyeWideRight', 'jawForward', 'jawLeft', 'jawOpen', 'jawRight',
  'mouthClose', 'mouthDimpleLeft', 'mouthDimpleRight', 'mouthFrownLeft', 'mouthFrownRight', 'mouthFunnel', 'mouthLeft', 'mouthLowerDownLeft',
  'mouthLowerDownRight', 'mouthPressLeft', 'mouthPressRight', 'mouthPucker', 'mouthRight', 'mouthRollLower', 'mouthRollUpper', 'mouthShrugLower',
  'mouthShrugUpper', 'mouthSmileLeft', 'mouthSmileRight', 'mouthStretchLeft', 'mouthStretchRight', 'mouthUpperUpLeft', 'mouthUpperUpRight',
  'noseSneerLeft', 'noseSneerRight', 'tongueOut',
));

export function bindFace(morphNames: string[], boneNames: string[] = []): FaceBinding {
  const uniq = [...new Set(morphNames)];
  const byNorm = new Map<string, string[]>();
  for (const m of uniq) {
    const k = normFaceName(m);
    byNorm.set(k, [...(byNorm.get(k) ?? []), m]);
  }
  const used = new Set<string>();
  const pick = (aliases: string[]): string[] => {
    const out: string[] = [];
    for (const a of aliases) for (const m of byNorm.get(a) ?? []) if (!out.includes(m)) { out.push(m); used.add(m); }
    return out;
  };
  const visemes: FaceBinding['visemes'] = {};
  for (const k of Object.keys(MESH_FACE_ALIASES.visemes) as FaceVisemeKey[]) {
    const hit = pick(MESH_FACE_ALIASES.visemes[k]);
    if (hit.length) visemes[k] = hit;
  }
  const open = pick(MESH_FACE_ALIASES.open);
  const blinkLeft = pick(MESH_FACE_ALIASES.blinkLeft);
  const blinkRight = pick(MESH_FACE_ALIASES.blinkRight);
  const blinkBoth = pick(MESH_FACE_ALIASES.blinkBoth);
  const blink = [...new Set([...blinkLeft, ...blinkRight, ...blinkBoth])];
  const emotions: FaceBinding['emotions'] = {};
  for (const k of Object.keys(MESH_FACE_ALIASES.emotions) as FaceEmotionKey[]) {
    const hit = pick(MESH_FACE_ALIASES.emotions[k]);
    if (hit.length) emotions[k] = hit;
  }
  const prosodyBrow = pick(MESH_FACE_ALIASES.prosodyBrow);
  const prosodyEye = pick(MESH_FACE_ALIASES.prosodyEye);

  const jawBone = pickBone(boneNames, JAW_BONE);
  const headBone = pickBone(boneNames, HEAD_BONE);
  const spineBone = pickBone(boneNames, SPINE_BONE);

  const visemeCount = Object.keys(visemes).length;
  const mouthMode: FaceMouthMode = visemeCount >= 2 ? 'viseme' : open.length ? 'morph' : jawBone ? 'jaw' : 'none';
  const warnings: string[] = [];
  if (mouthMode === 'none') warnings.push('no mouth channel: no viseme/jawOpen/mouthOpen morph and no jaw bone — the mouth cannot move');
  if (visemeCount === 1) warnings.push(`only one viseme (${Object.keys(visemes)[0]}) — need ≥2 for viseme mode; add jawOpen or the full set`);
  if (!blink.length) warnings.push('no blink morph (eyeBlinkLeft/eyeBlinkRight or blink) — eyes never close');
  if (blinkLeft.length && !blinkRight.length) warnings.push('eyeBlinkLeft without eyeBlinkRight — one eye blinks');
  if (blinkRight.length && !blinkLeft.length) warnings.push('eyeBlinkRight without eyeBlinkLeft — one eye blinks');
  if (!headBone && boneNames.length) warnings.push('skeleton has no Head bone — nods/head turns fall back to whole-body sway');
  const unbound = uniq.filter((m) => !used.has(m) && !ARKIT_SET.has(normFaceName(m)));
  const arkitCount = uniq.filter((m) => ARKIT_SET.has(normFaceName(m))).length;
  return {
    visemes, open, blink, blinkLeft, blinkRight, emotions, prosodyBrow, prosodyEye,
    jawBone, headBone, spineBone, mouthMode,
    hasBlink: blink.length > 0, hasExpressions: Object.keys(emotions).length > 0,
    unbound, arkitCount, warnings,
  };
}

/** One-line human summary (console warnings, CLI header). */
export function describeBinding(b: FaceBinding): string {
  const vis = Object.keys(b.visemes);
  const mouth = b.mouthMode === 'viseme' ? `visemes ${vis.join('/')}` : b.mouthMode === 'morph' ? `morph ${b.open.join(',')}` : b.mouthMode === 'jaw' ? `jaw bone ${b.jawBone}` : 'NONE';
  return `mouth=${mouth}; blink=${b.blink.length ? b.blink.join(',') : 'none'}; expressions=${Object.keys(b.emotions).join(',') || 'none'}; arkit=${b.arkitCount}/52; head=${b.headBone ?? 'none'}`;
}
