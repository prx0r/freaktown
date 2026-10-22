/**
 * Procedural GLB for agent-made identities (no Blender needed; the sandbox has
 * none, and the box pipeline scripts/blender_factory.py stays the path for
 * sculpted meshes). Pure TS → glTF 2.0 binary.
 *
 * Body: torso, arms, legs, a head from the identity's recipe (sphere | box |
 * lantern | blob), optional antenna. Face mesh carries ARKit morph targets the
 * stage already drives (GlbAvatar sniffs them): jawOpen, mouthSmileLeft,
 * mouthSmileRight, eyeBlinkLeft, eyeBlinkRight — so the character talks,
 * smiles (face.expression happy) and blinks on any set.
 */
import type { PartyIdentity } from './identity';
import { mulberry32 } from './rng';

type V3 = [number, number, number];
interface Part { pos: number[]; nrm: number[]; idx: number[] }
interface MeshSpec { name: string; color: string; part: Part; morphs?: Record<string, number[]> }

const hex = (h: string): [number, number, number, number] => {
  const n = parseInt(h.replace('#', ''), 16);
  const lin = (c: number) => Math.pow(c / 255, 2.2);
  return [lin((n >> 16) & 255), lin((n >> 8) & 255), lin(n & 255), 1];
};

function empty(): Part { return { pos: [], nrm: [], idx: [] }; }
function append(dst: Part, src: Part) {
  const off = dst.pos.length / 3;
  dst.pos.push(...src.pos); dst.nrm.push(...src.nrm); dst.idx.push(...src.idx.map((i) => i + off));
}

/** Ellipsoid (UV sphere), optional per-vertex shaping. */
function ellipsoid(c: V3, r: V3, seg = 16, ring = 12, shape?: (p: V3, n: V3) => V3): Part {
  const p = empty();
  for (let i = 0; i <= ring; i++) {
    const v = i / ring, th = v * Math.PI;
    for (let j = 0; j <= seg; j++) {
      const u = j / seg, ph = u * Math.PI * 2;
      const n: V3 = [Math.sin(th) * Math.sin(ph), Math.cos(th), Math.sin(th) * Math.cos(ph)];
      let q: V3 = [n[0] * r[0], n[1] * r[1], n[2] * r[2]];
      if (shape) q = shape(q, n);
      p.pos.push(c[0] + q[0], c[1] + q[1], c[2] + q[2]);
      p.nrm.push(...n);
    }
  }
  for (let i = 0; i < ring; i++) for (let j = 0; j < seg; j++) {
    const a = i * (seg + 1) + j, b = a + seg + 1;
    p.idx.push(a, b, a + 1, b, b + 1, a + 1);
  }
  return p;
}

/** Axis-aligned box. */
function box(c: V3, h: V3): Part {
  const p = empty();
  const faces: Array<[V3, V3, V3]> = [[[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[-1, 0, 0], [0, 1, 0], [0, 0, -1]], [[0, 1, 0], [0, 0, 1], [1, 0, 0]], [[0, -1, 0], [0, 0, -1], [1, 0, 0]], [[0, 0, 1], [1, 0, 0], [0, 1, 0]], [[0, 0, -1], [-1, 0, 0], [0, 1, 0]]];
  for (const [n, u, v] of faces) {
    const o = p.pos.length / 3;
    for (const [su, sv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      p.pos.push(c[0] + (n[0] + u[0] * su + v[0] * sv) * h[0], c[1] + (n[1] + u[1] * su + v[1] * sv) * h[1], c[2] + (n[2] + u[2] * su + v[2] * sv) * h[2]);
      p.nrm.push(...n);
    }
    p.idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
  }
  return p;
}

/** Vertical cylinder from y0 to y1. */
function cylinder(x: number, z: number, y0: number, y1: number, r: number, seg = 12): Part {
  const p = empty();
  for (let k = 0; k <= 1; k++) for (let j = 0; j <= seg; j++) {
    const a = (j / seg) * Math.PI * 2;
    p.pos.push(x + Math.sin(a) * r, k ? y1 : y0, z + Math.cos(a) * r);
    p.nrm.push(Math.sin(a), 0, Math.cos(a));
  }
  for (let j = 0; j < seg; j++) p.idx.push(j, j + seg + 1, j + 1, j + seg + 1, j + seg + 2, j + 1);
  return p;
}

/** A flat grid on the face plane z = zf, centred at (cx, cy): w × h, nx × ny verts. */
function plate(cx: number, cy: number, zf: number, w: number, h: number, nx: number, ny: number): Part {
  const p = empty();
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const u = i / (nx - 1) - 0.5, v = j / (ny - 1) - 0.5;
    // lens-shaped mouth/eye: taper toward the ends
    const taper = 1 - Math.pow(Math.abs(u) * 2, 2) * 0.7;
    p.pos.push(cx + u * w, cy + v * h * taper, zf);
    p.nrm.push(0, 0, 1);
  }
  for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
    const a = j * nx + i;
    p.idx.push(a, a + 1, a + nx, a + 1, a + nx + 1, a + nx);
  }
  return p;
}

export function buildIdentityMeshes(idn: PartyIdentity): MeshSpec[] {
  const body = idn.look.body ?? { head: 'sphere' as const, height: 1.7, eyes: 2, antenna: false, seed: 1 };
  const rng = mulberry32(body.seed);
  const [cBody, cTrim, cAccent] = [idn.look.palette[0] ?? '#F5C86B', idn.look.palette[1] ?? '#2B2D42', idn.look.palette[2] ?? '#EF8354'];
  const H = body.height;
  const s = H / 1.7;
  const torso = empty();
  append(torso, ellipsoid([0, 1.0 * s, 0], [0.24 * s, 0.34 * s, 0.17 * s]));
  append(torso, cylinder(-0.3 * s, 0, 0.72 * s, 1.22 * s, 0.055 * s));
  append(torso, cylinder(0.3 * s, 0, 0.72 * s, 1.22 * s, 0.055 * s));
  const legs = empty();
  append(legs, cylinder(-0.11 * s, 0, 0.0, 0.7 * s, 0.07 * s));
  append(legs, cylinder(0.11 * s, 0, 0.0, 0.7 * s, 0.07 * s));
  append(legs, box([-0.11 * s, 0.03 * s, 0.05 * s], [0.07 * s, 0.03 * s, 0.11 * s]));
  append(legs, box([0.11 * s, 0.03 * s, 0.05 * s], [0.07 * s, 0.03 * s, 0.11 * s]));

  const hy = 1.52 * s, hr = 0.2 * s;
  const wobble = 0.04 + rng() * 0.05;
  const head = body.head === 'box' ? box([0, hy, 0], [hr, hr * 1.05, hr * 0.9])
    : body.head === 'lantern' ? (() => { const p = ellipsoid([0, hy, 0], [hr * 0.95, hr * 1.15, hr * 0.95], 16, 12, (q, n) => [q[0] * (1 + 0.12 * Math.cos(n[1] * 6)), q[1], q[2] * (1 + 0.12 * Math.cos(n[1] * 6))]); append(p, box([0, hy + hr * 1.25, 0], [hr * 0.5, hr * 0.1, hr * 0.5])); append(p, box([0, hy - hr * 1.2, 0], [hr * 0.55, hr * 0.08, hr * 0.55])); return p; })()
      : body.head === 'dome' ? ellipsoid([0, hy, 0], [hr * 1.05, hr * 1.2, hr], 18, 14, (q, n) => { const up = Math.max(0, n[1]); const k = 1 + 0.35 * up * up - 0.12 * Math.max(0, -n[1]); return [q[0] * k, q[1], q[2] * k * (1 + wobble * Math.sin(n[0] * 4))]; })
      : body.head === 'blob' ? ellipsoid([0, hy, 0], [hr * 1.1, hr, hr], 16, 12, (q, n) => { const k = 1 + wobble * Math.sin(n[0] * 5 + n[1] * 3); return [q[0] * k, q[1] * k, q[2] * k]; })
        : ellipsoid([0, hy, 0], [hr, hr * 1.05, hr]);
  const zf = (body.head === 'box' ? hr * 0.9 : hr * 0.97) + 0.004 * s;

  // face: mouth (8×3 verts) + two eyes (5×3 each)
  const face = empty();
  const mouth = plate(0, hy - hr * 0.42, zf * 0.98, hr * 0.9, hr * 0.16, 8, 3);
  // eyes: 2 (default) = left + right; 3 adds a centre eye above; 1 = one big centre eye
  const nEyes = Math.max(1, Math.min(3, body.eyes ?? 2));
  const eyeSpecs: Array<[number, number, number, number]> = nEyes === 1 ? [[0, hy + hr * 0.22, hr * 0.5, hr * 0.38]]
    : [[-hr * 0.38, hy + hr * 0.22, hr * 0.32, hr * 0.26], [hr * 0.38, hy + hr * 0.22, hr * 0.32, hr * 0.26], ...(nEyes === 3 ? [[0, hy + hr * 0.62, hr * 0.26, hr * 0.22] as [number, number, number, number]] : [])];
  append(face, mouth); const mouthN = mouth.pos.length / 3;
  for (const [ex, ey, ew, eh] of eyeSpecs) append(face, plate(ex, ey, zf * 0.99, ew, eh, 5, 3));
  const nv = face.pos.length / 3;
  const zero = () => new Array(nv * 3).fill(0);
  const jaw = zero(), smL = zero(), smR = zero(), blL = zero(), blR = zero();
  for (let v = 0; v < mouthN; v++) {
    const i = v % 8, j = Math.floor(v / 8);
    const u = i / 7 - 0.5;
    if (j === 0) jaw[v * 3 + 1] = -hr * 0.28 * (1 - Math.abs(u) * 1.2);
    if (j === 1) jaw[v * 3 + 1] = -hr * 0.12 * (1 - Math.abs(u) * 1.2);
    const corner = Math.max(0, Math.abs(u) * 2 - 0.2);
    if (u < 0) { smL[v * 3 + 1] = hr * 0.16 * corner; smL[v * 3] = -hr * 0.05 * corner; }
    if (u > 0) { smR[v * 3 + 1] = hr * 0.16 * corner; smR[v * 3] = hr * 0.05 * corner; }
  }
  const eyeBase = (which: number) => mouthN + which * 15;
  eyeSpecs.forEach(([, cy], which) => {
    const arr = which === 1 ? blR : blL; // the centre eye blinks with the left
    for (let k = 0; k < 15; k++) { const v = eyeBase(which) + k; arr[v * 3 + 1] = (cy - face.pos[v * 3 + 1]) * 0.92; }
  });
  const meshes: MeshSpec[] = [
    { name: 'body', color: cBody, part: torso },
    { name: 'legs', color: cTrim, part: legs },
    { name: 'head', color: cBody, part: head },
    { name: 'face', color: '#15131c', part: face, morphs: { jawOpen: jaw, mouthSmileLeft: smL, mouthSmileRight: smR, eyeBlinkLeft: blL, eyeBlinkRight: blR } },
  ];
  if (body.antenna) {
    const a = empty();
    const top = hy + hr * (body.head === 'dome' ? 1.2 : 1);
    append(a, cylinder(0, 0, top, top + 0.16 * s, 0.012 * s, 8));
    append(a, ellipsoid([0, top + 0.18 * s, 0], [0.03 * s, 0.03 * s, 0.03 * s], 10, 8));
    meshes.push({ name: 'antenna', color: cAccent, part: a });
  }
  return meshes;
}

/** Encode meshes as a glTF 2.0 binary (.glb). */
export function encodeGlb(meshes: MeshSpec[], name: string): Uint8Array {
  const chunks: Uint8Array[] = [];
  let byteLength = 0;
  const bufferViews: Array<Record<string, unknown>> = [];
  const accessors: Array<Record<string, unknown>> = [];
  const addView = (data: ArrayBufferView, target?: number) => {
    const bytes = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    const pad = (4 - (bytes.length % 4)) % 4;
    bufferViews.push({ buffer: 0, byteOffset: byteLength, byteLength: bytes.length, ...(target ? { target } : {}) });
    chunks.push(bytes, new Uint8Array(pad));
    byteLength += bytes.length + pad;
    return bufferViews.length - 1;
  };
  const vec3 = (arr: number[], minmax = true) => {
    const f = new Float32Array(arr);
    const view = addView(f, 34962);
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < f.length; i += 3) for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], f[i + k]); max[k] = Math.max(max[k], f[i + k]); }
    accessors.push({ bufferView: view, componentType: 5126, count: f.length / 3, type: 'VEC3', ...(minmax ? { min, max } : {}) });
    return accessors.length - 1;
  };
  const materials: Array<Record<string, unknown>> = [];
  const gMeshes: Array<Record<string, unknown>> = [];
  for (const m of meshes) {
    const pos = vec3(m.part.pos);
    const nrm = vec3(m.part.nrm, false);
    const idx = new Uint16Array(m.part.idx);
    accessors.push({ bufferView: addView(idx, 34963), componentType: 5123, count: idx.length, type: 'SCALAR' });
    const ia = accessors.length - 1;
    materials.push({ name: m.name, pbrMetallicRoughness: { baseColorFactor: hex(m.color), metallicFactor: 0.05, roughnessFactor: 0.7 } });
    const prim: Record<string, unknown> = { attributes: { POSITION: pos, NORMAL: nrm }, indices: ia, material: materials.length - 1 };
    const mesh: Record<string, unknown> = { name: m.name, primitives: [prim] };
    if (m.morphs) {
      const names = Object.keys(m.morphs);
      prim.targets = names.map((n) => ({ POSITION: vec3(m.morphs![n]) }));
      mesh.weights = names.map(() => 0);
      mesh.extras = { targetNames: names };
    }
    gMeshes.push(mesh);
  }
  const json = {
    asset: { version: '2.0', generator: 'funnier-party procedural identity v1' },
    scene: 0, scenes: [{ name, nodes: [0] }],
    nodes: [{ name, children: gMeshes.map((_, i) => i + 1) }, ...gMeshes.map((m, i) => ({ name: String(m.name), mesh: i }))],
    meshes: gMeshes, materials, accessors, bufferViews, buffers: [{ byteLength }],
  };
  const enc = new TextEncoder().encode(JSON.stringify(json));
  const jpad = (4 - (enc.length % 4)) % 4;
  const jsonChunk = new Uint8Array(enc.length + jpad).fill(0x20);
  jsonChunk.set(enc);
  const total = 12 + 8 + jsonChunk.length + 8 + byteLength;
  const out = new Uint8Array(total);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, 0x46546c67, true); dv.setUint32(4, 2, true); dv.setUint32(8, total, true);
  dv.setUint32(12, jsonChunk.length, true); dv.setUint32(16, 0x4e4f534a, true);
  out.set(jsonChunk, 20);
  let o = 20 + jsonChunk.length;
  dv.setUint32(o, byteLength, true); dv.setUint32(o + 4, 0x004e4942, true);
  o += 8;
  for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

export function identityGlb(idn: PartyIdentity): Uint8Array {
  return encodeGlb(buildIdentityMeshes(idn), idn.name);
}

/** Minimal GLB reader for checks: header + JSON chunk. */
export function readGlbJson(b: Uint8Array): { version: number; length: number; json: Record<string, any> } {
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  if (dv.getUint32(0, true) !== 0x46546c67) throw new Error('not glTF');
  const jl = dv.getUint32(12, true);
  return { version: dv.getUint32(4, true), length: dv.getUint32(8, true), json: JSON.parse(new TextDecoder().decode(b.subarray(20, 20 + jl))) };
}
