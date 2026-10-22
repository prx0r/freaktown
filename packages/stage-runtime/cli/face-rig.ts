/**
 * face:rig — bake procedural jawOpen, eyeBlinkLeft/Right, browInnerUp, browDownLeft/Right and
 * mouthSmileLeft/Right morph
 * targets into a rigged GLB that has none (same generator the stage runs at
 * load time: face/proceduralRig.ts), so the shapes ship with the file.
 *
 *   npm run face:rig -- in.glb out.glb [--mouth=0.38] [--eyes=0.45] [--spread=0.26] [--jaw=0.26] [--force]
 *
 * Refuses a file that already has face channels unless --force (real shapes
 * always beat generated ones). Tune flags move the landmarks when the
 * mouth/eyes land in the wrong place; check the result with face:check and
 * the stage (docs/MESH-FACE-HOOKUP.md).
 */
import { bindFace } from '../src/face/meshBinding';
import { proceduralFaceRig, inferUp, type RigTune } from '../src/face/proceduralRig';
import { readGlb, writeGlb, appendVec3, targetNames, sceneNodes, headRigInput, type Gltf } from './glb';

const args = process.argv.slice(2).filter((a) => a !== '--');
const [src, dst] = args.filter((a) => !a.startsWith('--'));
if (!src || !dst) { console.error('usage: npm run face:rig -- in.glb out.glb [--mouth=0.38] [--eyes=0.45] [--spread=0.26] [--jaw=0.26] [--force]'); process.exit(2); }
const flag = (k: string) => { const a = args.find((x) => x.startsWith(`--${k}=`)); return a ? Number(a.split('=')[1]) : undefined; };
const tune: Partial<RigTune> = {};
if (flag('mouth') !== undefined) tune.mouthFrac = flag('mouth');
if (flag('eyes') !== undefined) tune.eyeFrac = flag('eyes');
if (flag('spread') !== undefined) tune.eyeSpread = flag('spread');
if (flag('jaw') !== undefined) tune.jawAngle = flag('jaw');

const g = readGlb(src);
const json: Gltf = g.json;
const live = sceneNodes(json);
const bones: string[] = [...new Set<string>((json.skins ?? []).flatMap((s: Gltf) => s.joints.map((j: number) => json.nodes[j].name ?? '')))];
const allMorphs = (json.meshes ?? []).flatMap((m: Gltf) => targetNames(m));
const before = bindFace(allMorphs, bones);
if ((before.mouthMode !== 'none' || before.hasBlink) && !args.includes('--force')) {
  console.error(`face:rig: ${src} already has face channels (mouth=${before.mouthMode}, blink=${before.blink.join(',') || 'none'}). Use --force to add generated ones anyway.`);
  process.exit(1);
}
if (!before.headBone) { console.error('face:rig: no Head bone in the skeleton — rig the mesh (Meshy/Mixamo/AccuRIG/Rigify) first.'); process.exit(1); }

let best: { mesh: number; prim: number; res: ReturnType<typeof proceduralFaceRig> } | null = null;
json.meshes.forEach((m: Gltf, mi: number) => {
  const rendered = json.nodes.some((nd: Gltf, k: number) => nd.mesh === mi && live.has(k));
  if (!rendered) return;
  m.primitives.forEach((_: Gltf, pi: number) => {
    const inp = headRigInput(g, mi, pi, before.headBone!);
    if (!inp) return;
    const headIdx: number[] = [];
    const n = inp.positions.length / 3;
    for (let i = 0; i < n; i++) { let w = 0; for (let k = 0; k < 4; k++) if (inp.headJoints.has(inp.skinIndex[i * 4 + k])) w += inp.skinWeight[i * 4 + k]; if (w >= 0.35) headIdx.push(i); }
    const up = inferUp(inp.positions, headIdx);
    const res = proceduralFaceRig({ ...inp, up, forward: Math.abs(up[2]) === 1 ? [0, -1, 0] : [0, 0, 1], tune });
    if (res.targets.length && (!best || res.landmarks.headVerts > best.res.landmarks.headVerts)) best = { mesh: mi, prim: pi, res };
  });
});
if (!best) { console.error('face:rig: no rendered skinned primitive is weighted to the Head bone.'); process.exit(1); }
const { mesh, prim, res } = best as { mesh: number; prim: number; res: ReturnType<typeof proceduralFaceRig> };
const m = json.meshes[mesh];
const names = targetNames(m);
// every primitive of the mesh needs the same number of targets: zero deltas on the others
m.primitives.forEach((p: Gltf, pi: number) => {
  const count = json.accessors[p.attributes.POSITION].count;
  const hasNormals = (p.targets ?? []).some((t: Gltf) => t.NORMAL !== undefined);
  p.targets ??= [];
  for (const t of res.targets) {
    const deltas = pi === prim ? t.deltas : new Float32Array(count * 3);
    const tgt: Gltf = { POSITION: appendVec3(g, deltas) };
    if (hasNormals) tgt.NORMAL = appendVec3(g, new Float32Array(count * 3));
    p.targets.push(tgt);
  }
});
m.extras = { ...(m.extras ?? {}), targetNames: [...names, ...res.targets.map((t) => t.name)] };
if (Array.isArray(m.weights)) m.weights.push(...res.targets.map(() => 0));
json.asset = { ...json.asset, extras: { ...(json.asset?.extras ?? {}), faceRig: 'funnier face:rig (procedural jawOpen/eyeBlinkLeft/eyeBlinkRight/browInnerUp/browDownLeft/browDownRight/mouthSmileLeft/mouthSmileRight)' } };
writeGlb(dst, g);
console.log(JSON.stringify({ out: dst, mesh: m.name ?? mesh, targets: res.targets.map((t) => ({ name: t.name, verts: t.moved })), landmarks: res.landmarks, warnings: res.warnings }, null, 1));
