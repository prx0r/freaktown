import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bindFace, normFaceName, proceduralFaceRig, FaceChannel, arkitToFace } from '../src/face';
import { GlbAvatar } from '../src/avatars/GlbAvatar';
import { faceCheck } from '../cli/faceCheck';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const ZE = { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 };
const ZV = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };

function morphMesh(names: string[]): THREE.Mesh {
  const geo = new THREE.BoxGeometry();
  geo.morphAttributes.position = names.map(() => geo.attributes.position.clone());
  const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial());
  mesh.updateMorphTargets();
  mesh.morphTargetDictionary = Object.fromEntries(names.map((n, i) => [n, i]));
  mesh.morphTargetInfluences = names.map(() => 0);
  return mesh;
}

/** A skinned "body + sphere head" with a Head bone and no morphs (a Meshy-style export). */
function skinnedHeadless(): { scene: THREE.Group; mesh: THREE.SkinnedMesh } {
  const body = new THREE.CylinderGeometry(0.25, 0.25, 1.2, 16, 8).translate(0, 0.6, 0);
  const head = new THREE.SphereGeometry(0.2, 32, 24).translate(0, 1.42, 0);
  // a nose so the profile has a forward-most point
  const nose = new THREE.SphereGeometry(0.035, 8, 6).translate(0, 1.40, 0.2);
  const parts = [body, head, nose];
  const pos: number[] = [], idx: number[] = [], wts: number[] = [];
  let offset = 0; const index: number[] = [];
  parts.forEach((g, pi) => {
    const p = g.getAttribute('position');
    for (let i = 0; i < p.count; i++) { pos.push(p.getX(i), p.getY(i), p.getZ(i)); idx.push(pi === 0 ? 0 : 1, 0, 0, 0); wts.push(1, 0, 0, 0); }
    const gi = g.getIndex()!; for (let i = 0; i < gi.count; i++) index.push(gi.getX(i) + offset);
    offset += p.count;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4));
  geo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wts, 4));
  geo.setIndex(index);
  const hips = new THREE.Bone(); hips.name = 'Hips';
  const headBone = new THREE.Bone(); headBone.name = 'Head'; headBone.position.y = 1.3; hips.add(headBone);
  const mesh = new THREE.SkinnedMesh(geo, new THREE.MeshBasicMaterial());
  mesh.name = 'Mesh_0';
  const scene = new THREE.Group(); scene.add(hips); scene.add(mesh);
  scene.updateMatrixWorld(true);
  mesh.bind(new THREE.Skeleton([hips, headBone]));
  return { scene, mesh };
}

describe('meshBinding: names → face channels', () => {
  it('normalises exporter prefixes and separators', () => {
    expect(normFaceName('blendShape1.jawOpen')).toBe('jawopen');
    expect(normFaceName('Key 1|Mouth_Open')).toBe('mouthopen');
    expect(normFaceName('vrc.v_aa')).toBe('vaa');
  });
  it('ARKit, CC4, VRoid, Oculus and prefixed names all bind', () => {
    expect(bindFace(['jawOpen', 'eyeBlinkLeft', 'eyeBlinkRight']).mouthMode).toBe('morph');
    const cc4 = bindFace(['Mouth_Open', 'Eye_Blink_L', 'Eye_Blink_R', 'Mouth_Smile_L']);
    expect(cc4.open).toEqual(['Mouth_Open']);
    expect(cc4.blinkLeft).toEqual(['Eye_Blink_L']);
    expect(cc4.emotions.happy).toEqual(['Mouth_Smile_L']);
    const vroid = bindFace(['Fcl_MTH_A', 'Fcl_MTH_I', 'Fcl_MTH_U', 'Fcl_EYE_Close']);
    expect(vroid.mouthMode).toBe('viseme');
    expect(vroid.hasBlink).toBe(true);
    const oculus = bindFace(['viseme_aa', 'viseme_O', 'blendShape1.eyeBlinkLeft', 'blendShape1.eyeBlinkRight']);
    expect(oculus.mouthMode).toBe('viseme');
    expect(oculus.blink).toHaveLength(2);
  });
  it('jaw bone fallback, helpers ignored, and an honest warning when nothing fits', () => {
    expect(bindFace([], ['Hips', 'Head', 'head_end', 'mixamorig:Jaw']).mouthMode).toBe('jaw');
    expect(bindFace([], ['Hips', 'Head', 'headfront', 'head_end']).headBone).toBe('Head');
    const none = bindFace(['Key 1'], ['Hips', 'Head']);
    expect(none.mouthMode).toBe('none');
    expect(none.warnings.join(' ')).toMatch(/no mouth channel/);
    expect(none.unbound).toEqual(['Key 1']);
  });
});

describe('GlbAvatar: mouth is never clobbered', () => {
  it('jawOpen survives the second (prosody) setExpression pass — the "Buddha doesn\'t move" bug', () => {
    const mesh = morphMesh(['jawOpen', 'browInnerUp', 'eyeBlinkLeft', 'eyeBlinkRight']);
    const glb = new GlbAvatar(mesh, [], 'arkit', { warn: () => {} });
    // exactly the StageRuntime.renderFrame order: apply(), then prosody setExpression()
    FaceChannel.apply(glb, { open: 0.8, visemes: { ...ZV, aa: 0.8 }, emotions: { ...ZE }, blink: 0 });
    glb.setExpression({ ...ZE }, { brow: 0.3, eye: 0 });
    expect(mesh.morphTargetInfluences![0]).toBeGreaterThan(0.6); // jawOpen
    expect(mesh.morphTargetInfluences![1]).toBeCloseTo(0.3); // brow still flashes
  });
  it('surprise still drops the jaw a little, through the mouth channel', () => {
    const mesh = morphMesh(['jawOpen', 'browInnerUp']);
    const glb = new GlbAvatar(mesh, [], 'arkit', { warn: () => {} });
    glb.setExpression({ ...ZE, surprised: 1 });
    glb.setMouth(0, { ...ZV });
    expect(mesh.morphTargetInfluences![0]).toBeCloseTo(0.35);
  });
  it('a jaw-bone-only GLB rotates the jaw', () => {
    const g = new THREE.Group(); const head = new THREE.Bone(); head.name = 'Head'; const jaw = new THREE.Bone(); jaw.name = 'Jaw'; head.add(jaw); g.add(head);
    const glb = new GlbAvatar(g, [], 'jawrig', { warn: () => {} });
    expect(glb.caps.mouthMode).toBe('jaw');
    glb.setMouth(1, { ...ZV });
    expect(jaw.rotation.x).toBeCloseTo(0.35);
  });
  it('a static mesh with nothing warns once, loudly', () => {
    const warns: string[] = [];
    const glb = new GlbAvatar(new THREE.Mesh(new THREE.BoxGeometry()), [], 'statue', { warn: (m) => warns.push(m) });
    expect(glb.caps.mouthMode).toBe('none');
    expect(warns.join('\n')).toMatch(/NO mouth channel/);
  });
  it('a one-key rest-pose clip does not take over the bones', () => {
    const g = new THREE.Group(); const head = new THREE.Bone(); head.name = 'Head'; g.add(head);
    const clip = new THREE.AnimationClip('Armature|clip0|baselayer', 0.03, [new THREE.QuaternionKeyframeTrack('Head.quaternion', [0.033], [0, 0, 0, 1])]);
    const glb = new GlbAvatar(g, [clip], 'meshy', { warn: () => {} }) as unknown as { mixer: unknown };
    expect(glb.mixer).toBeNull();
  });
});

describe('procedural face rig (no morphs, Head bone)', () => {
  it('GlbAvatar generates jawOpen + eyeBlinkLeft/Right and they move vertices', () => {
    const { scene, mesh } = skinnedHeadless();
    const warns: string[] = [];
    const glb = new GlbAvatar(scene, [], 'meshy', { warn: (m) => warns.push(m) });
    expect(glb.caps.faceRig).toBe('procedural');
    expect(glb.caps.mouthMode).toBe('morph');
    expect(glb.caps.hasBlink).toBe(true);
    expect(warns[0]).toMatch(/procedural jawOpen/);
    const jaw = mesh.geometry.morphAttributes.position[mesh.morphTargetDictionary!.jawOpen];
    let moved = 0; for (let i = 0; i < jaw.count; i++) if (Math.abs(jaw.getY(i)) > 1e-4) moved++;
    expect(moved).toBeGreaterThan(30);
    // body vertices (bone 0) never move
    for (let i = 0; i < 50; i++) expect(jaw.getY(i)).toBe(0);
  });
  it("faceRig 'off' drives only the bytes", () => {
    const { scene } = skinnedHeadless();
    const glb = new GlbAvatar(scene, [], 'meshy', { faceRig: 'off', warn: () => {} });
    expect(glb.caps.mouthMode).toBe('none');
  });
  it('pure rig refuses a mesh with no head weighting', () => {
    const r = proceduralFaceRig({ positions: new Float32Array(30), skinIndex: new Float32Array(40), skinWeight: new Float32Array(40), headJoints: new Set([1]) });
    expect(r.targets).toHaveLength(0);
    expect(r.warnings[0]).toMatch(/head-weighted/);
  });
});

describe('face:check on the repo avatars', () => {
  it('buddha.glb drives mouth + blink + head', () => {
    const r = faceCheck(path.join(root, 'static/avatars/buddha.glb'));
    expect(r.verdict).toBe('ok');
    expect(r.binding.mouthMode).toBe('morph');
    expect(r.binding.blink).toEqual(['eyeBlinkLeft', 'eyeBlinkRight']);
    expect(r.binding.headBone).toBe('Head');
    expect(r.emptyMorphs).toEqual([]);
  });
  it('the VRM sample goes down the VRM path', () => {
    const r = faceCheck(path.join(root, 'static/avatars/default-v1.vrm'));
    expect(r.kind).toBe('vrm');
    expect(r.verdict).toBe('ok');
  });
  it('arkitToFace output still reaches a GLB through apply()', () => {
    const mesh = morphMesh(['jawOpen']);
    const glb = new GlbAvatar(mesh, [], 'x', { warn: () => {} });
    FaceChannel.apply(glb, arkitToFace({ jawOpen: 0.7 }));
    expect(mesh.morphTargetInfluences![0]).toBeGreaterThan(0.5);
  });
});
