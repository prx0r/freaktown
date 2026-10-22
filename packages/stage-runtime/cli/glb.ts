/**
 * Minimal GLB reader/writer for the face CLIs (no deps, Node only).
 * Reads JSON + BIN chunks, decodes accessors (float / normalized ints),
 * appends float32 accessors and writes the file back.
 */
import fs from 'node:fs';

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Gltf = any;

export interface Glb { json: Gltf; bin: Buffer }

export function readGlb(path: string): Glb {
  const d = fs.readFileSync(path);
  if (d.toString('ascii', 0, 4) !== 'glTF') throw new Error(`${path}: not a binary glTF (.glb)`);
  let off = 12; let json: Gltf = null; let bin = Buffer.alloc(0);
  while (off < d.length) {
    const len = d.readUInt32LE(off); const type = d.toString('ascii', off + 4, off + 8);
    const body = d.subarray(off + 8, off + 8 + len);
    if (type === 'JSON') json = JSON.parse(body.toString('utf8'));
    else if (type === 'BIN\0') bin = Buffer.from(body);
    off += 8 + len + ((4 - (len % 4)) % 4);
  }
  if (!json) throw new Error(`${path}: no JSON chunk`);
  return { json, bin };
}

export function writeGlb(path: string, g: Glb): void {
  let jb = Buffer.from(JSON.stringify(g.json), 'utf8');
  jb = Buffer.concat([jb, Buffer.alloc((4 - (jb.length % 4)) % 4, 0x20)]);
  const bb = Buffer.concat([g.bin, Buffer.alloc((4 - (g.bin.length % 4)) % 4)]);
  const head = Buffer.alloc(12); head.write('glTF', 0, 'ascii'); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + jb.length + 8 + bb.length, 8);
  const ch = (len: number, type: string) => { const b = Buffer.alloc(8); b.writeUInt32LE(len, 0); b.write(type, 4, 'ascii'); return b; };
  fs.writeFileSync(path, Buffer.concat([head, ch(jb.length, 'JSON'), jb, ch(bb.length, 'BIN\0'), bb]));
}

const NCOMP: Record<string, number> = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
const CSIZE: Record<number, number> = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };

/** Decode an accessor to floats (normalized ints → 0..1 / -1..1). Sparse accessors are not supported. */
export function readAccessor(g: Glb, idx: number): { data: Float32Array; count: number; ncomp: number } {
  const a = g.json.accessors[idx];
  const nc = NCOMP[a.type]; const out = new Float32Array(a.count * nc);
  if (a.bufferView === undefined) return { data: out, count: a.count, ncomp: nc };
  const bv = g.json.bufferViews[a.bufferView];
  const cs = CSIZE[a.componentType]; const stride = bv.byteStride || nc * cs;
  const base = (bv.byteOffset ?? 0) + (a.byteOffset ?? 0);
  const norm = !!a.normalized;
  for (let i = 0; i < a.count; i++) for (let c = 0; c < nc; c++) {
    const o = base + i * stride + c * cs; let v: number;
    switch (a.componentType) {
      case 5126: v = g.bin.readFloatLE(o); break;
      case 5121: v = g.bin.readUInt8(o); if (norm) v /= 255; break;
      case 5123: v = g.bin.readUInt16LE(o); if (norm) v /= 65535; break;
      case 5125: v = g.bin.readUInt32LE(o); break;
      case 5120: v = g.bin.readInt8(o); if (norm) v = Math.max(v / 127, -1); break;
      default: v = g.bin.readInt16LE(o); if (norm) v = Math.max(v / 32767, -1);
    }
    out[i * nc + c] = v;
  }
  return { data: out, count: a.count, ncomp: nc };
}

/** Append a tightly packed float32 VEC3 accessor (with min/max); returns its index. */
export function appendVec3(g: Glb, data: Float32Array): number {
  const pad = (4 - (g.bin.length % 4)) % 4;
  const raw = Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  const offset = g.bin.length + pad;
  g.bin = Buffer.concat([g.bin, Buffer.alloc(pad), raw]);
  g.json.bufferViews ??= [];
  g.json.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: raw.length });
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < data.length; i += 3) for (let c = 0; c < 3; c++) { min[c] = Math.min(min[c], data[i + c]); max[c] = Math.max(max[c], data[i + c]); }
  g.json.accessors.push({ bufferView: g.json.bufferViews.length - 1, componentType: 5126, count: data.length / 3, type: 'VEC3', min, max });
  g.json.buffers ??= [{}];
  g.json.buffers[0].byteLength = g.bin.length;
  return g.json.accessors.length - 1;
}

/** Morph target names for a mesh (mesh.extras.targetNames, else primitive extras, else target<i>). */
export function targetNames(mesh: Gltf): string[] {
  const count = Math.max(0, ...(mesh.primitives ?? []).map((p: Gltf) => (p.targets ?? []).length));
  const names: string[] | undefined = mesh.extras?.targetNames ?? mesh.primitives?.[0]?.extras?.targetNames;
  return Array.from({ length: count }, (_, i) => names?.[i] ?? `target${i}`);
}

/** Node indices reachable from the default scene. */
export function sceneNodes(json: Gltf): Set<number> {
  const seen = new Set<number>();
  const scene = json.scenes?.[json.scene ?? 0];
  const stack: number[] = [...(scene?.nodes ?? [])];
  while (stack.length) { const i = stack.pop()!; if (seen.has(i)) continue; seen.add(i); stack.push(...(json.nodes[i].children ?? [])); }
  return seen;
}

/**
 * Head-rig input for a skinned primitive: positions/joints/weights + the
 * skin-joint indices of the Head bone and its descendants.
 */
export function headRigInput(g: Glb, meshIdx: number, primIdx: number, headName: string) {
  const json = g.json;
  const nodeIdx = json.nodes.findIndex((nd: Gltf) => nd.mesh === meshIdx && nd.skin !== undefined);
  if (nodeIdx < 0) return null;
  const skin = json.skins[json.nodes[nodeIdx].skin];
  const headNode = skin.joints.find((j: number) => json.nodes[j].name === headName);
  if (headNode === undefined) return null;
  const sub = new Set<number>();
  const stack = [headNode];
  while (stack.length) { const k = stack.pop()!; sub.add(k); stack.push(...(json.nodes[k].children ?? [])); }
  const headJoints = new Set<number>(skin.joints.map((j: number, i: number) => (sub.has(j) ? i : -1)).filter((i: number) => i >= 0));
  const prim = json.meshes[meshIdx].primitives[primIdx];
  if (prim.attributes.JOINTS_0 === undefined || prim.attributes.WEIGHTS_0 === undefined) return null;
  const positions = readAccessor(g, prim.attributes.POSITION).data;
  const skinIndex = readAccessor(g, prim.attributes.JOINTS_0).data;
  const skinWeight = readAccessor(g, prim.attributes.WEIGHTS_0).data;
  return { positions, skinIndex, skinWeight, headJoints };
}
