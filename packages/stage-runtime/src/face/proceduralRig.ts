/**
 * proceduralRig — synthesise jawOpen, eyeBlinkLeft/Right, browInnerUp,
 * browDownLeft/Right and mouthSmileLeft/Right morph deltas for a
 * skinned mesh that has a Head bone but no face channels (Meshy, Tripo,
 * Hunyuan, Rodin… body rigs ship with ZERO face shapes).
 *
 * Pure (no three.js): typed arrays in, POSITION-space deltas out. Used by
 *   - GlbAvatar at load time (runtime fallback, with a console warning), and
 *   - `npm run face:rig in.glb out.glb` (bakes the same shapes into the file
 *     so they ship with the asset and show up in face:check / Blender).
 *
 * It is a fallback, not a face: real ARKit shapes authored in Blender always
 * look better (docs/MESH-FACE-HOOKUP.md). What it does:
 *   jawOpen  — vertices below the mouth line rotate about a hinge behind and
 *              above the mouth (like a mandible), feathered across the lip
 *              line so the mouth OPENS instead of the lower face sliding.
 *   blink    — each eye region is squashed toward its lid line, so painted
 *              (texture) eyes close to a slit as well as modelled lids.
 *   browInnerUp, browDownLeft/Right, mouthSmileLeft/Right — brow lift, brow
 *              knit and smile corners, so surprise / annoyed / happy and the
 *              prosody brow flash read on the face.
 * Landmarks come from the head-weighted vertex cloud: chin = lowest front
 * centre vertex, nose = most forward point above it, mouth/eyes at fixed
 * fractions of the nose→chin span (overridable per mesh).
 */

export type Vec3 = [number, number, number];

export interface RigInput {
  /** POSITION, xyz per vertex (bind pose, mesh space) */
  positions: ArrayLike<number>;
  /** JOINTS_0 / skinIndex, 4 per vertex */
  skinIndex: ArrayLike<number>;
  /** WEIGHTS_0 / skinWeight, 4 per vertex, already normalised to 0..1 */
  skinWeight: ArrayLike<number>;
  /** joint indices that count as "head" (Head + its descendants, e.g. headfront, jaw) */
  headJoints: Set<number>;
  /** whole-mesh up axis in mesh space (default +Y) */
  up?: Vec3;
  /** face-forward axis in mesh space (default +Z, glTF convention) */
  forward?: Vec3;
  tune?: Partial<RigTune>;
}

export interface RigTune {
  /** min summed head weight for a vertex to be part of the head */
  headWeight: number;
  /** mouth line: fraction of the nose-tip→chin span below the nose tip */
  mouthFrac: number;
  /** eye line: fraction of the nose-tip→chin span ABOVE the nose tip */
  eyeFrac: number;
  /** eye centres: fraction of head width either side of centre */
  eyeSpread: number;
  /** jaw rotation at weight 1 (radians) */
  jawAngle: number;
  /** blink: 0..1 how far the eye squashes toward the lid line */
  blinkSquash: number;
}

export const DEFAULT_TUNE: RigTune = { headWeight: 0.35, mouthFrac: 0.38, eyeFrac: 0.45, eyeSpread: 0.26, jawAngle: 0.26, blinkSquash: 0.92 };

export interface RigResult {
  targets: { name: string; deltas: Float32Array; moved: number }[];
  landmarks: { chin: number; nose: number; mouth: number; eyes: number; headHeight: number; headWidth: number; headVerts: number };
  warnings: string[];
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const smooth = (e0: number, e1: number, x: number) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
function pct(vals: number[], p: number): number { const s = [...vals].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.max(0, Math.round(p * (s.length - 1))))]; }

export function proceduralFaceRig(inp: RigInput): RigResult {
  const t = { ...DEFAULT_TUNE, ...inp.tune };
  const U: Vec3 = inp.up ?? [0, 1, 0];
  const F: Vec3 = inp.forward ?? [0, 0, 1];
  const S: Vec3 = cross(U, F); // = the character's LEFT (+X for +Y up, +Z forward)
  const P = inp.positions, J = inp.skinIndex, W = inp.skinWeight;
  const n = Math.floor(P.length / 3);
  const warnings: string[] = [];

  // head cloud in (s,u,f) coordinates
  const head: number[] = [];
  const su: number[] = [], uu: number[] = [], fu: number[] = [];
  for (let i = 0; i < n; i++) {
    let w = 0;
    for (let k = 0; k < 4; k++) if (inp.headJoints.has(J[i * 4 + k])) w += W[i * 4 + k];
    if (w < t.headWeight) continue;
    const p: Vec3 = [P[i * 3], P[i * 3 + 1], P[i * 3 + 2]];
    head.push(i); su.push(dot(p, S)); uu.push(dot(p, U)); fu.push(dot(p, F));
  }
  const empty: RigResult = { targets: [], landmarks: { chin: 0, nose: 0, mouth: 0, eyes: 0, headHeight: 0, headWidth: 0, headVerts: head.length }, warnings };
  if (head.length < 100) { warnings.push(`only ${head.length} head-weighted vertices — weight the head to the Head bone first`); return empty; }

  const sMin = pct(su, 0.01), sMax = pct(su, 0.99), uMin = pct(uu, 0.01), uMax = pct(uu, 0.99), fMin = pct(fu, 0.01), fMax = pct(fu, 0.99);
  const w = sMax - sMin, h = uMax - uMin, d = fMax - fMin;
  const sMid = (sMin + sMax) / 2, fMid = (fMin + fMax) / 2;

  // front-centre strip (the profile line down the middle of the face)
  const strip: number[] = [];
  for (let j = 0; j < head.length; j++) if (Math.abs(su[j] - sMid) < 0.12 * w && fu[j] > fMid) strip.push(j);
  if (strip.length < 10) { warnings.push('could not find the front of the face (is the mesh facing +Z?)'); return empty; }
  const chin = pct(strip.map((j) => uu[j]), 0.02);
  // nose tip: most forward strip point in the middle band of the face
  let nose = uMin + 0.45 * h, best = -Infinity;
  for (const j of strip) {
    if (uu[j] < chin + 0.12 * h || uu[j] > chin + 0.55 * h) continue;
    if (fu[j] > best) { best = fu[j]; nose = uu[j]; }
  }
  const span = Math.max(1e-6, nose - chin);
  const mouth = nose - t.mouthFrac * span;
  const eyes = nose + t.eyeFrac * span;

  // ── jawOpen: rotate the lower face about a hinge (ear level, behind the mouth)
  const jaw = new Float32Array(n * 3);
  const hingeU = mouth + 0.10 * h, hingeF = fMid - 0.15 * d;
  const feather = 0.035 * h; // across the lip line
  const ca = Math.cos(t.jawAngle), sa = Math.sin(t.jawAngle);
  let movedJaw = 0;
  for (let j = 0; j < head.length; j++) {
    const below = mouth - uu[j];
    if (below < -feather * 0.5) continue; // upper face stays
    const front = smooth(fMid - 0.25 * d, fMid + 0.15 * d, fu[j]);
    const side = Math.exp(-Math.pow((su[j] - sMid) / (0.42 * w), 2));
    const wt = smooth(-feather * 0.5, feather, below) * front * side;
    if (wt <= 1e-3) continue;
    // rotate (u,f) about hinge: chin goes down and slightly back
    const du0 = uu[j] - hingeU, df0 = fu[j] - hingeF;
    const du1 = du0 * ca - df0 * sa, df1 = du0 * sa + df0 * ca;
    const dU = (du1 - du0) * wt, dF = (df1 - df0) * wt;
    const i = head[j];
    for (let a = 0; a < 3; a++) jaw[i * 3 + a] = U[a] * dU + F[a] * dF;
    movedJaw++;
  }

  // ── blink: squash each eye toward its lid line (slightly below centre)
  const rx = 0.17 * w, ry = 0.14 * h;
  const lid = (side: number) => {
    const out = new Float32Array(n * 3);
    const cs = sMid + side * t.eyeSpread * w;
    const lidU = eyes - 0.1 * ry;
    let moved = 0;
    for (let j = 0; j < head.length; j++) {
      if (fu[j] < fMid) continue;
      const ds = (su[j] - cs) / rx, du = (uu[j] - eyes) / ry;
      const r2 = ds * ds + du * du;
      if (r2 >= 1) continue;
      const fall = Math.min(1, 1.6 * (1 - r2)) * smooth(fMid, fMid + 0.3 * d, fu[j]);
      const dU = (lidU - uu[j]) * t.blinkSquash * fall;
      if (Math.abs(dU) < 1e-7) continue;
      const i = head[j];
      for (let a = 0; a < 3; a++) out[i * 3 + a] = U[a] * dU;
      moved++;
    }
    return { deltas: out, moved };
  };
  // S = U×F is the character's left (+X when facing +Z): ARKit eyeBlinkLeft = their left eye.
  const left = lid(+1), right = lid(-1);
  // ── browInnerUp: lift the band above the eyes (surprise / sad / prosody brow flash)
  const brow = new Float32Array(n * 3);
  const browDL = new Float32Array(n * 3), browDR = new Float32Array(n * 3);
  let movedBrow = 0;
  const b0 = eyes + 0.75 * ry, b1 = eyes + 2.6 * ry, bMid = (b0 + b1) / 2;
  for (let j = 0; j < head.length; j++) {
    if (fu[j] < fMid || uu[j] < b0 - 0.4 * ry || uu[j] > b1 + 0.8 * ry) continue;
    const band = uu[j] <= bMid ? smooth(b0 - 0.4 * ry, bMid, uu[j]) : 1 - smooth(bMid, b1 + 0.8 * ry, uu[j]);
    const side = Math.exp(-Math.pow((su[j] - sMid) / (0.38 * w), 2));
    const wt = band * side * smooth(fMid, fMid + 0.3 * d, fu[j]);
    if (wt <= 1e-3) continue;
    const i = head[j];
    for (let a = 0; a < 3; a++) brow[i * 3 + a] = U[a] * 0.08 * h * wt;
    // browDown (anger/annoyed, AU4): each side drops and knits toward the nose
    const left = smooth(sMid - 0.04 * w, sMid + 0.04 * w, su[j]);
    for (let a = 0; a < 3; a++) {
      const v = -U[a] * 0.05 * h * wt;
      browDL[i * 3 + a] = (v - S[a] * 0.012 * w * wt) * left;
      browDR[i * 3 + a] = (v + S[a] * 0.012 * w * wt) * (1 - left);
    }
    movedBrow++;
  }

  // ── mouthSmileLeft/Right: pull each mouth corner up and out
  const smile = (side: number) => {
    const out = new Float32Array(n * 3);
    const cs = sMid + side * 0.17 * w, r = 0.13 * w;
    let moved = 0;
    for (let j = 0; j < head.length; j++) {
      if (fu[j] < fMid) continue;
      const ds = (su[j] - cs) / r, du = (uu[j] - mouth) / (0.8 * r);
      const r2 = ds * ds + du * du;
      if (r2 >= 1) continue;
      const wt = (1 - r2) * (1 - r2) * smooth(fMid, fMid + 0.3 * d, fu[j]);
      const i = head[j];
      for (let a = 0; a < 3; a++) out[i * 3 + a] = (U[a] * 0.035 * h + S[a] * side * 0.015 * w - F[a] * 0.01 * d) * wt;
      moved++;
    }
    return { deltas: out, moved };
  };
  const smL = smile(+1), smR = smile(-1);

  if (movedJaw < 30) warnings.push(`jaw region tiny (${movedJaw} verts) — landmarks may be off; tune mouthFrac`);
  if (left.moved < 10 || right.moved < 10) warnings.push('eye regions tiny — tune eyeFrac/eyeSpread');
  return {
    targets: [
      { name: 'jawOpen', deltas: jaw, moved: movedJaw },
      { name: 'eyeBlinkLeft', deltas: left.deltas, moved: left.moved },
      { name: 'eyeBlinkRight', deltas: right.deltas, moved: right.moved },
      { name: 'browInnerUp', deltas: brow, moved: movedBrow },
      { name: 'browDownLeft', deltas: browDL, moved: movedBrow },
      { name: 'browDownRight', deltas: browDR, moved: movedBrow },
      { name: 'mouthSmileLeft', deltas: smL.deltas, moved: smL.moved },
      { name: 'mouthSmileRight', deltas: smR.deltas, moved: smR.moved },
    ],
    landmarks: { chin, nose, mouth, eyes, headHeight: h, headWidth: w, headVerts: head.length },
    warnings,
  };
}

/** Snap a direction to the nearest signed principal axis. */
export function snapAxis(v: Vec3): Vec3 {
  const a = v.map(Math.abs); const k = a[0] > a[1] ? (a[0] > a[2] ? 0 : 2) : (a[1] > a[2] ? 1 : 2);
  const out: Vec3 = [0, 0, 0]; out[k] = Math.sign(v[k]) || 1; return out;
}

/** Up axis from the data: head-cloud centroid minus whole-mesh centroid, snapped. */
export function inferUp(positions: ArrayLike<number>, headIdx: number[]): Vec3 {
  const n = Math.floor(positions.length / 3);
  const c = [0, 0, 0], hc = [0, 0, 0];
  for (let i = 0; i < n; i++) for (let a = 0; a < 3; a++) c[a] += positions[i * 3 + a] / n;
  for (const i of headIdx) for (let a = 0; a < 3; a++) hc[a] += positions[i * 3 + a] / Math.max(1, headIdx.length);
  return snapAxis([hc[0] - c[0], hc[1] - c[1], hc[2] - c[2]]);
}
