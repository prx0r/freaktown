/**
 * face:check — which face channels a GLB/VRM can drive on the stage.
 *
 *   npm run face:check -- static/avatars/buddha.glb [--json]
 *
 * Runs the SAME binding the stage runs (face/meshBinding.ts) on the names
 * in the file, then checks the things names alone can't: morphs that sit
 * on a mesh the scene never renders, morphs whose deltas are empty, and
 * whether the procedural fallback (face/proceduralRig.ts) could rig it.
 * Exit code 0 = mouth + blink drivable; 1 = mouth or blink missing; 2 = bad file.
 */
import { bindFace, describeBinding } from '../src/face/meshBinding';
import { proceduralFaceRig, inferUp } from '../src/face/proceduralRig';
import { readGlb, readAccessor, targetNames, sceneNodes, headRigInput, type Gltf } from './glb';

export interface FaceCheckReport {
  file: string;
  kind: 'vrm' | 'glb';
  driver: string;
  meshes: { mesh: number; name: string; rendered: boolean; skinned: boolean; primitives: number; morphs: string[] }[];
  bones: string[];
  morphNames: string[];
  binding: ReturnType<typeof bindFace>;
  vrmExpressions?: string[];
  emptyMorphs: string[];
  procedural: { eligible: boolean; reason: string; jawVerts?: number; blinkVerts?: [number, number] };
  channels: { mouth: string; blink: string; expressions: string; head: string };
  verdict: 'ok' | 'partial' | 'none';
  warnings: string[];
}

export function faceCheck(file: string): FaceCheckReport {
  const g = readGlb(file);
  const json: Gltf = g.json;
  const warnings: string[] = [];
  const isVrm = !!(json.extensions?.VRM || json.extensions?.VRMC_vrm);
  const live = sceneNodes(json);
  const meshes = (json.meshes ?? []).map((m: Gltf, i: number) => {
    const nodes = (json.nodes ?? []).map((nd: Gltf, k: number) => ({ nd, k })).filter(({ nd }: Gltf) => nd.mesh === i);
    return {
      mesh: i, name: m.name ?? `mesh${i}`,
      rendered: nodes.some(({ k }: Gltf) => live.has(k)),
      skinned: nodes.some(({ nd }: Gltf) => nd.skin !== undefined),
      primitives: m.primitives.length,
      morphs: targetNames(m),
    };
  });
  const bones: string[] = [...new Set<string>((json.skins ?? []).flatMap((s: Gltf) => s.joints.map((j: number) => json.nodes[j].name ?? `node${j}`)))];
  const morphNames = [...new Set<string>(meshes.filter((m: Gltf) => m.rendered).flatMap((m: Gltf) => m.morphs))];
  for (const m of meshes) if (!m.rendered && m.morphs.length) warnings.push(`mesh "${m.name}" has ${m.morphs.length} morphs but no scene node renders it — they can never move anything`);
  const binding = bindFace(morphNames, bones);

  // empty-delta check on every bound morph
  const bound = new Set<string>([...binding.open, ...binding.blink, ...Object.values(binding.visemes).flat() as string[]]);
  const emptyMorphs: string[] = [];
  json.meshes?.forEach((m: Gltf) => {
    const names = targetNames(m);
    names.forEach((nm, ti) => {
      if (!bound.has(nm)) return;
      let max = 0;
      for (const p of m.primitives) {
        const acc = p.targets?.[ti]?.POSITION;
        if (acc === undefined) continue;
        const a = json.accessors[acc];
        if (a.max && a.min) max = Math.max(max, ...a.max.map(Math.abs), ...a.min.map(Math.abs));
        else { const d = readAccessor(g, acc).data; for (const v of d) max = Math.max(max, Math.abs(v)); }
      }
      if (max < 1e-6) emptyMorphs.push(nm);
    });
  });
  for (const e of emptyMorphs) warnings.push(`morph "${e}" is bound but its deltas are all zero — it will move nothing (re-export with shape keys applied)`);

  let vrmExpressions: string[] | undefined;
  if (isVrm) {
    const v1 = json.extensions?.VRMC_vrm?.expressions;
    const v0 = json.extensions?.VRM?.blendShapeMaster?.blendShapeGroups;
    vrmExpressions = v1 ? [...Object.keys(v1.preset ?? {}), ...Object.keys(v1.custom ?? {})] : (v0 ?? []).map((b: Gltf) => b.presetName && b.presetName !== 'unknown' ? b.presetName : b.name);
  }

  // procedural fallback eligibility
  let procedural: FaceCheckReport['procedural'] = { eligible: false, reason: 'not needed: the file carries face channels' };
  if (!isVrm && binding.mouthMode === 'none' && !binding.hasBlink) {
    procedural = { eligible: false, reason: binding.headBone ? 'no skinned primitive weighted to the Head bone' : 'no Head bone in the skeleton (rig the mesh first)' };
    if (binding.headBone) {
      for (const m of meshes) {
        if (!m.rendered || !m.skinned) continue;
        for (let p = 0; p < m.primitives; p++) {
          const inp = headRigInput(g, m.mesh, p, binding.headBone);
          if (!inp) continue;
          const headIdx: number[] = [];
          const n = inp.positions.length / 3;
          for (let i = 0; i < n; i++) { let w = 0; for (let k = 0; k < 4; k++) if (inp.headJoints.has(inp.skinIndex[i * 4 + k])) w += inp.skinWeight[i * 4 + k]; if (w >= 0.35) headIdx.push(i); }
          const up = inferUp(inp.positions, headIdx);
          const r = proceduralFaceRig({ ...inp, up, forward: Math.abs(up[2]) === 1 ? [0, -1, 0] : [0, 0, 1] });
          if (r.targets.length) {
            procedural = { eligible: true, reason: `stage will generate jawOpen/eyeBlinkLeft/eyeBlinkRight/browInnerUp/browDownLeft/browDownRight/mouthSmileLeft/mouthSmileRight at load on "${m.name}" (bake them with: npm run face:rig -- <in.glb> <out.glb>)`, jawVerts: r.targets[0].moved, blinkVerts: [r.targets[1].moved, r.targets[2].moved] };
            break;
          } else procedural.reason = r.warnings.join('; ');
        }
        if (procedural.eligible) break;
      }
    }
  }

  const vis = Object.keys(binding.visemes);
  const ch = isVrm
    ? { mouth: 'VRM expressions aa/ih/ou/ee/oh (VrmAvatar)', blink: 'VRM blink expression', expressions: (vrmExpressions ?? []).join(',') || 'none', head: 'VRM humanoid head' }
    : {
        mouth: binding.mouthMode === 'viseme' ? `viseme (${vis.join(', ')})${binding.open.length ? ` + ${binding.open.join(',')}` : ''}` : binding.mouthMode === 'morph' ? `morph (${binding.open.join(', ')})` : binding.mouthMode === 'jaw' ? `jaw bone "${binding.jawBone}" (rotates on X)` : procedural.eligible ? 'NONE in file → procedural jawOpen at load' : 'NONE',
        blink: binding.hasBlink ? binding.blink.join(', ') : procedural.eligible ? 'NONE in file → procedural eyeBlinkLeft/Right at load' : 'NONE',
        expressions: Object.entries(binding.emotions).map(([k, v]) => `${k}(${(v as string[]).length})`).join(' ') || 'none',
        head: binding.headBone ? `bone "${binding.headBone}" (nods/turns)` : 'none (whole-body sway)',
      };
  const mouthOk = isVrm || binding.mouthMode !== 'none';
  const blinkOk = isVrm || binding.hasBlink;
  const verdict: FaceCheckReport['verdict'] = mouthOk && blinkOk ? 'ok' : mouthOk || blinkOk || procedural.eligible ? 'partial' : 'none';
  return {
    file, kind: isVrm ? 'vrm' : 'glb', driver: isVrm ? 'VrmAvatar' : 'GlbAvatar',
    meshes, bones, morphNames, binding, vrmExpressions, emptyMorphs, procedural, channels: ch, verdict,
    warnings: [...(isVrm ? [] : binding.warnings), ...warnings],
  };
}

export function formatReport(r: FaceCheckReport): string {
  const L: string[] = [];
  L.push(`face:check ${r.file}`);
  L.push(`  kind      ${r.kind} → ${r.driver}`);
  for (const m of r.meshes) L.push(`  mesh      #${m.mesh} "${m.name}" ${m.rendered ? 'rendered' : 'NOT RENDERED'}${m.skinned ? ', skinned' : ''}, ${m.primitives} prim, ${m.morphs.length} morphs${m.morphs.length ? `: ${m.morphs.slice(0, 12).join(', ')}${m.morphs.length > 12 ? ', …' : ''}` : ''}`);
  L.push(`  bones     ${r.bones.length}${r.bones.length ? ` (head: ${r.binding.headBone ?? '—'}, jaw: ${r.binding.jawBone ?? '—'}, spine: ${r.binding.spineBone ?? '—'})` : ''}`);
  L.push(`  MOUTH     ${r.channels.mouth}`);
  L.push(`  BLINK     ${r.channels.blink}`);
  L.push(`  EXPRESS   ${r.channels.expressions}`);
  L.push(`  HEAD      ${r.channels.head}`);
  if (r.kind === 'glb') L.push(`  ARKit     ${r.binding.arkitCount}/52 names${r.binding.unbound.length ? `; unrecognised: ${r.binding.unbound.slice(0, 10).join(', ')}` : ''}`);
  if (r.procedural.eligible || r.binding.mouthMode === 'none') L.push(`  fallback  ${r.procedural.reason}${r.procedural.jawVerts !== undefined ? ` [jaw ${r.procedural.jawVerts} verts, blink ${r.procedural.blinkVerts?.join('/')} verts]` : ''}`);
  for (const w of r.warnings) L.push(`  WARN      ${w}`);
  L.push(`  verdict   ${r.verdict.toUpperCase()}${r.kind === 'glb' ? ` — ${describeBinding(r.binding)}` : ''}`);
  return L.join('\n');
}

