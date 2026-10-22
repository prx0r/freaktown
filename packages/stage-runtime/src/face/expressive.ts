/**
 * Expressive face: one channel set for every mesh, with the SAME numbers in three.js and the Blender bake.
 *
 *   expressive-map.json  channels (open, aa ih ou ee oh, blinkL/R, smileL/R, grin, frown, browUp/Down/Sad, squint,
 *                        eyeWide, lookX/Y) -> per-rig shape targets (VRoid Fcl_*, ARKit-52, Oculus visemes, VRM
 *                        presets) with gains (up to max_gain, so a VRoid mouth actually opens), emotion -> channel
 *                        mixes, and the check rule. sets/blender/face_express.py reads the same file.
 *
 *   checkFace(names)     can this mesh express? fail = a core group (mouth, blink, smile, brow) has no shape at all;
 *                        warn = an extended capability is missing (5 visemes, one-sided smile, frown, sad brow,
 *                        squint, wide eyes, gaze). Use it at load time; the stage logs it and the Blender bake
 *                        refuses a failing mesh with --strict.
 *   channelsFromState()  visemes/emotions/blink/brow/squint/smirk/look -> channel weights (speech-aware)
 *   shapesFor()          channel weights -> {shape name: weight} for the bound rig (summed, clamped)
 *   ExpressiveFace       binds a three.js object's morphs, generates missing one-sided shapes (smirk) from a
 *                        symmetric one exactly like the bake does, aims eye bones, writes influences.
 */
import * as THREE from 'three';
import MAP from './expressive-map.json';
import type { Emotions, Visemes } from '../avatars/types';

export type Channel = keyof typeof MAP.channels;
export type Channels = Partial<Record<Channel, number>>;
export type RigId = keyof typeof MAP.rigs;
type Target = [string, number];
interface RigSpec {
  detect: string[];
  shapes: Partial<Record<Channel, Target[]>>;
  generate?: Record<string, { from: string; side: 'L' | 'R'; gain: number }>;
  gaze_bones?: { left: string; right: string; yaw_deg: number; pitch_deg: number };
  gaze_morphs?: Record<'left' | 'right' | 'up' | 'down', Target[]>;
}

export const EXPRESSIVE_MAP = MAP;
export const CHANNELS = Object.keys(MAP.channels) as Channel[];
export const MAX_GAIN: number = MAP.max_gain;
const RIGS = MAP.rigs as unknown as Record<RigId, RigSpec>;

/** Same normalisation as meshBinding / newsroom_perform.norm: drop any "Prefix." / "a|b" path, keep [a-z0-9]. */
export function normName(name: string): string {
  let s = name.trim();
  const cut = Math.max(s.lastIndexOf('.'), s.lastIndexOf('|'), s.lastIndexOf(':'));
  if (cut >= 0 && cut < s.length - 1) s = s.slice(cut + 1);
  return s.toLowerCase().replace(/[^a-z0-9]/g, '');
}

export interface RigBinding {
  rig: RigId | null;
  /** channel -> [[actual shape name on the mesh, weight]] */
  bound: Partial<Record<Channel, Target[]>>;
  /** one-sided shapes to generate: [new name, source actual name, side, gain] */
  generate: Array<[string, string, 'L' | 'R', number]>;
  gazeBones: RigSpec['gaze_bones'] | null;
  gazeMorphs: Partial<Record<'left' | 'right' | 'up' | 'down', Target[]>>;
}

/** Pick the rig whose detect names the mesh carries (most hits, then most bound channels) and bind it. */
export function bindRig(names: string[], bones: string[] = [], force?: RigId): RigBinding {
  const have = new Map<string, string>();
  for (const n of names) if (!have.has(normName(n))) have.set(normName(n), n);
  const boneSet = new Set(bones.map(normName));
  let best: RigBinding = { rig: null, bound: {}, generate: [], gazeBones: null, gazeMorphs: {} };
  let bestScore = -1;
  for (const id of (force ? [force] : (Object.keys(RIGS) as RigId[]))) {
    const spec = RIGS[id];
    const hits = spec.detect.filter((d) => have.has(normName(d))).length;
    const gen: RigBinding['generate'] = [];
    const virtual = new Map(have);
    for (const [nm, g] of Object.entries(spec.generate ?? {})) {
      const src = have.get(normName(g.from));
      if (src && !have.has(normName(nm))) { gen.push([nm, src, g.side, g.gain]); virtual.set(normName(nm), nm); }
    }
    const bound: RigBinding['bound'] = {};
    for (const [ch, targets] of Object.entries(spec.shapes) as [Channel, Target[]][]) {
      const t = targets.flatMap(([n, w]): Target[] => (virtual.has(normName(n)) ? [[virtual.get(normName(n))!, w]] : []));
      if (t.length) bound[ch] = t;
    }
    const gazeMorphs: RigBinding['gazeMorphs'] = {};
    for (const [dir, targets] of Object.entries(spec.gaze_morphs ?? {}) as ['left' | 'right' | 'up' | 'down', Target[]][]) {
      const t = targets.flatMap(([n, w]): Target[] => (have.has(normName(n)) ? [[have.get(normName(n))!, w]] : []));
      if (t.length) gazeMorphs[dir] = t;
    }
    const gb = spec.gaze_bones && boneSet.has(normName(spec.gaze_bones.left)) && boneSet.has(normName(spec.gaze_bones.right)) ? spec.gaze_bones : null;
    const score = hits * 100 + Object.keys(bound).length;
    if (hits >= Math.min(2, spec.detect.length) && score > bestScore) {
      bestScore = score;
      best = { rig: id, bound, generate: gen, gazeBones: gb, gazeMorphs };
    }
  }
  return best;
}

export interface FaceCheck {
  rig: RigId | null;
  level: 'ok' | 'warn' | 'fail';
  channels: Channel[];
  missingCore: string[];
  warnings: string[];
  generated: string[];
}

/** Can this mesh express? (see the file header for the rule; expressive-map.json "check"). */
export function checkFace(names: string[], bones: string[] = [], opts: { gazeByHead?: boolean } = {}): FaceCheck {
  const b = bindRig(names, bones);
  const has = (c: Channel) => !!b.bound[c];
  const groups: Record<string, boolean> = {
    mouth: ['open', 'aa', 'ih', 'ou', 'ee', 'oh'].some((c) => has(c as Channel)),
    blink: has('blinkL') || has('blinkR'),
    smile: has('smileL') || has('smileR'),
    brow: has('browUp') || has('browDown') || has('browSad'),
  };
  const missingCore = MAP.check.core.filter((g) => !groups[g]);
  const sameSides = has('smileL') && has('smileR') && JSON.stringify(b.bound.smileL) === JSON.stringify(b.bound.smileR);
  const ext: Record<string, boolean> = {
    // five visemes that are not all the same jaw: at least 3 distinct shape-name sets
    visemes: ['aa', 'ih', 'ou', 'ee', 'oh'].every((c) => has(c as Channel))
      && new Set(['aa', 'ih', 'ou', 'ee', 'oh'].map((c) => JSON.stringify((b.bound[c as Channel] ?? []).map((t) => t[0]).sort()))).size >= 3,
    smileSides: has('smileL') && has('smileR') && !sameSides,
    frown: has('frown'), browSad: has('browSad'), squint: has('squint'), eyeWide: has('eyeWide'),
    gaze: !!b.gazeBones || Object.keys(b.gazeMorphs).length >= 2 || !!opts.gazeByHead,
  };
  const warnings = MAP.check.extended.filter((k) => !ext[k]).map((k) => `no ${k}`);
  return {
    rig: b.rig,
    level: missingCore.length ? 'fail' : warnings.length ? 'warn' : 'ok',
    channels: Object.keys(b.bound) as Channel[],
    missingCore,
    warnings,
    generated: b.generate.map((g) => g[0]),
  };
}

export interface ExpressiveState {
  /** mouth amplitude 0..1 and the viseme mix (weights 0..1) */
  open?: number;
  visemes?: Partial<Visemes>;
  emotions?: Partial<Emotions>;
  blinkL?: number;
  blinkR?: number;
  /** extra brow raise (setup flash, emphasis) and furrow (the look) */
  browUp?: number;
  browDown?: number;
  squint?: number;
  /** -1 = smirk on the face's right, +1 = on its left */
  smirk?: number;
  lookX?: number;
  lookY?: number;
  speaking?: boolean;
}

const c01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
const r6 = (x: number) => Math.round(x * 1e6) / 1e6;

/** State -> channel weights. Emotions mix through expressive-map.json "emotions" (max-blended per channel). */
export function channelsFromState(s: ExpressiveState): Channels {
  const ch: Record<string, number> = {};
  const put = (k: string, v: number) => { if (v > 0) ch[k] = Math.max(ch[k] ?? 0, v); };
  const vis = s.visemes ?? {};
  const anyVis = (['aa', 'ih', 'ou', 'ee', 'oh'] as const).some((k) => (vis[k] ?? 0) > 0);
  if (anyVis) for (const k of ['aa', 'ih', 'ou', 'ee', 'oh'] as const) put(k, c01(vis[k] ?? 0));
  else put('open', c01(s.open ?? 0));
  for (const [emo, mix] of Object.entries(MAP.emotions)) {
    const e = c01((s.emotions as Record<string, number> | undefined)?.[emo] ?? 0);
    if (e > 0) for (const [k, w] of Object.entries(mix)) put(k, e * (w as number));
  }
  put('blinkL', c01(s.blinkL ?? 0));
  put('blinkR', c01(s.blinkR ?? 0));
  put('browUp', c01(s.browUp ?? 0));
  put('browDown', c01(s.browDown ?? 0));
  put('squint', c01(s.squint ?? 0));
  const sm = s.smirk ?? 0;
  if (sm > 0) put('smileL', c01(sm));
  if (sm < 0) put('smileR', c01(-sm));
  if (s.speaking) for (const [k, f] of Object.entries(MAP.speech.while_speaking)) if (ch[k] !== undefined && k !== 'open') ch[k] *= f as number;
  // a raised and a furrowed brow fight each other: the stronger wins, the other is halved
  if (ch.browUp && ch.browDown) { if (ch.browUp >= ch.browDown) ch.browDown *= 0.5; else ch.browUp *= 0.5; }
  if (s.lookX) ch.lookX = Math.max(-1, Math.min(1, s.lookX));
  if (s.lookY) ch.lookY = Math.max(-1, Math.min(1, s.lookY));
  const out: Channels = {};
  for (const k of Object.keys(ch).sort()) out[k as Channel] = r6(ch[k]);
  return out;
}

/** Channel weights -> shape weights for a binding (targets summed, clamped to [0, max_gain]). */
export function shapesFor(b: Pick<RigBinding, 'bound' | 'gazeMorphs'>, ch: Channels): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [c, v] of Object.entries(ch) as [Channel, number][]) {
    if (c === 'lookX' || c === 'lookY') continue;
    for (const [n, w] of b.bound[c] ?? []) out[n] = (out[n] ?? 0) + v * w;
  }
  const gm = b.gazeMorphs;
  const lx = ch.lookX ?? 0, ly = ch.lookY ?? 0;
  const g = (dir: 'left' | 'right' | 'up' | 'down', v: number) => { for (const [n, w] of gm[dir] ?? []) out[n] = (out[n] ?? 0) + v * w; };
  if (lx > 0) g('left', lx); if (lx < 0) g('right', -lx);
  if (ly > 0) g('up', ly); if (ly < 0) g('down', -ly);
  for (const k of Object.keys(out)) out[k] = r6(Math.max(0, Math.min(MAX_GAIN, out[k])));
  return out;
}

/** Soft side mask for one-sided shapes: weight of a vertex at x for side L (+x, the face's own left) or R. */
export function sideMask(x: number, side: 'L' | 'R', width = 0.012): number {
  const u = c01(0.5 + (side === 'L' ? x : -x) / width);
  return u * u * (3 - 2 * u);
}

/** Add a one-sided copy of a morph target (position deltas x side mask x gain) to a geometry. Returns its index. */
export function generateSideMorph(geo: THREE.BufferGeometry, srcIndex: number, side: 'L' | 'R', gain: number, name: string,
  dict: Record<string, number>): number {
  const pos = geo.getAttribute('position') as THREE.BufferAttribute;
  const src = geo.morphAttributes.position[srcIndex] as THREE.BufferAttribute;
  const rel = geo.morphTargetsRelative;
  const arr = new Float32Array(src.count * 3);
  for (let i = 0; i < src.count; i++) {
    const m = sideMask(pos.getX(i), side) * gain;
    for (let k = 0; k < 3; k++) {
      const base = (pos.array as ArrayLike<number>)[i * 3 + k];
      const d = (src.array as ArrayLike<number>)[i * 3 + k] - (rel ? 0 : base);
      arr[i * 3 + k] = (rel ? 0 : base) + d * m;
    }
  }
  geo.morphAttributes.position.push(new THREE.BufferAttribute(arr, 3));
  if (geo.morphAttributes.normal) {
    const sn = geo.morphAttributes.normal[srcIndex] as THREE.BufferAttribute;
    geo.morphAttributes.normal.push(sn.clone());
  }
  const idx = geo.morphAttributes.position.length - 1;
  dict[name] = idx;
  return idx;
}

interface Ref { mesh: THREE.Mesh; index: number }

/** Binds a three.js avatar's morphs (and eye bones) to the expressive channels and writes them. */
export class ExpressiveFace {
  readonly binding: RigBinding;
  readonly check: FaceCheck;
  private refs = new Map<string, Ref[]>();
  private eyes: { l: THREE.Object3D; r: THREE.Object3D; lq: THREE.Quaternion; rq: THREE.Quaternion } | null = null;
  private written = new Set<string>();
  private gazeWas = false;

  constructor(root: THREE.Object3D, opts: { force?: RigId; generate?: boolean } = {}) {
    const names: string[] = [];
    const bones: string[] = [];
    const meshes: THREE.Mesh[] = [];
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && m.morphTargetDictionary) { meshes.push(m); names.push(...Object.keys(m.morphTargetDictionary)); }
      if ((o as THREE.Bone).isBone || o.type === 'Bone' || /eye/i.test(o.name)) bones.push(o.name);
    });
    this.binding = bindRig(names, bones, opts.force);
    if (opts.generate !== false) {
      for (const [nm, srcName, side, gain] of this.binding.generate) {
        for (const m of meshes) {
          const dict = m.morphTargetDictionary!;
          const si = dict[srcName];
          if (si === undefined || dict[nm] !== undefined || !m.geometry.morphAttributes.position) continue;
          generateSideMorph(m.geometry, si, side, gain, nm, dict);
          (m.morphTargetInfluences ??= []).push(0);
        }
      }
    }
    for (const m of meshes) for (const [k, i] of Object.entries(m.morphTargetDictionary!)) {
      const l = this.refs.get(k) ?? []; l.push({ mesh: m, index: i }); this.refs.set(k, l);
    }
    this.check = checkFace([...this.refs.keys()], bones);
    const gb = this.binding.gazeBones;
    if (gb) {
      const l = root.getObjectByName(gb.left), r = root.getObjectByName(gb.right);
      if (l && r) this.eyes = { l, r, lq: l.quaternion.clone(), rq: r.quaternion.clone() };
    }
  }

  /** Every shape name this face may write (so other writers can stay off them). */
  get shapeNames(): string[] {
    const s = new Set<string>();
    for (const t of Object.values(this.binding.bound)) for (const [n] of t ?? []) s.add(n);
    return [...s];
  }

  apply(ch: Channels): Record<string, number> {
    const w = shapesFor(this.binding, ch);
    const next = new Set(Object.keys(w));
    for (const n of this.written) if (!next.has(n)) w[n] = 0;      // nothing sticks when its source decays
    for (const [n, v] of Object.entries(w)) for (const r of this.refs.get(n) ?? []) if (r.mesh.morphTargetInfluences) r.mesh.morphTargetInfluences[r.index] = v;
    this.written = next;
    // eye bones only while a gaze is given (and once more to return to rest), so VRM lookAt keeps them otherwise
    const gazing = ch.lookX !== undefined || ch.lookY !== undefined;
    if (this.eyes && this.binding.gazeBones && (gazing || this.gazeWas)) {
      this.gazeWas = gazing;
      const gb = this.binding.gazeBones;
      const yaw = THREE.MathUtils.degToRad(gb.yaw_deg) * (ch.lookX ?? 0);
      const pitch = THREE.MathUtils.degToRad(gb.pitch_deg) * (ch.lookY ?? 0);
      const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(-pitch, yaw, 0, 'YXZ'));
      this.eyes.l.quaternion.copy(this.eyes.lq).multiply(q);
      this.eyes.r.quaternion.copy(this.eyes.rq).multiply(q);
    }
    return w;
  }
}
