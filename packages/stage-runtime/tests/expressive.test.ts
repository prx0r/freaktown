import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import gold from '../../../tests/fixtures/face-expressive-golden.json';
import {
  bindRig, channelsFromState, checkFace, shapesFor, sideMask, ExpressiveFace, FaceChannel, MAX_GAIN,
  type ExpressiveState, type Channels,
} from '../src/face';
import { GlbAvatar } from '../src/avatars/GlbAvatar';

type Mesh = { names: string[]; bones: string[] };
const G = gold as unknown as {
  states: Record<string, ExpressiveState>; meshes: Record<string, Mesh>;
  channels: Record<string, Record<string, number>>; shapes: Record<string, Record<string, Record<string, number>>>;
  checks: Record<string, unknown>;
};
const close = (a: Record<string, number>, b: Record<string, number>) => {
  expect(Object.keys(a).sort()).toEqual(Object.keys(b).sort());
  for (const k of Object.keys(a)) expect(Math.abs(a[k] - b[k])).toBeLessThan(1e-6);
};

describe('expressive face: three.js runtime == Blender bake (golden from sets/blender/face_express.py)', () => {
  it('channelsFromState matches the Python mirror for every golden state', () => {
    for (const [k, s] of Object.entries(G.states)) close(channelsFromState(s) as Record<string, number>, G.channels[k]);
  });
  it('shapesFor + checkFace match for VRoid, ARKit, the lantern GLB and a bare mesh', () => {
    for (const [m, d] of Object.entries(G.meshes)) {
      const b = bindRig(d.names, d.bones);
      expect(checkFace(d.names, d.bones)).toEqual(G.checks[m]);
      for (const k of Object.keys(G.states)) close(shapesFor(b, G.channels[k] as Channels), G.shapes[m][k]);
    }
  });
  it('VRoid mouth gain: aa drives Fcl_MTH_A to 1.35 (the old 0.85 barely parted the lips), clamped at max_gain', () => {
    const d = G.meshes.vroid;
    const b = bindRig(d.names, d.bones);
    expect(shapesFor(b, channelsFromState({ visemes: { aa: 1 }, speaking: true }))['Face_Blendshape.Fcl_MTH_A']).toBeGreaterThanOrEqual(1.3);
    expect(Math.max(...Object.values(shapesFor(b, { aa: 9 } as Channels)))).toBeLessThanOrEqual(MAX_GAIN);
  });
  it('check: fails a mesh that cannot express, warns on missing range', () => {
    expect(checkFace(G.meshes.lantern.names).level).toBe('fail');
    expect(checkFace(G.meshes.lantern.names).missingCore).toEqual(['brow']);
    expect(checkFace(G.meshes.vroid.names, G.meshes.vroid.bones).level).toBe('ok');
    const noGaze = checkFace(G.meshes.vroid.names);
    expect(noGaze.level).toBe('warn');
    expect(noGaze.warnings).toEqual(['no gaze']);
  });
});

function faceMesh(): THREE.Mesh {
  // a strip of 5 vertices across the mouth (x = -0.04 .. 0.04) with a symmetric "smile" target lifting all by 0.01
  const g = new THREE.BufferGeometry();
  const xs = [-0.04, -0.02, 0, 0.02, 0.04];
  g.setAttribute('position', new THREE.Float32BufferAttribute(xs.flatMap((x) => [x, 0, 0]), 3));
  g.morphAttributes.position = [
    new THREE.Float32BufferAttribute(xs.flatMap(() => [0, 0.01, 0]), 3),
    new THREE.Float32BufferAttribute(xs.flatMap(() => [0, -0.005, 0]), 3),
    new THREE.Float32BufferAttribute(xs.flatMap(() => [0, 0, 0]), 3),
    new THREE.Float32BufferAttribute(xs.flatMap(() => [0, 0, 0]), 3),
    new THREE.Float32BufferAttribute(xs.flatMap(() => [0, 0, 0]), 3),
  ];
  g.morphTargetsRelative = true;
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial());
  m.name = 'Face';
  m.morphTargetDictionary = { 'Face_Blendshape.Fcl_MTH_Fun': 0, 'Face_Blendshape.Fcl_MTH_A': 1, 'Face_Blendshape.Fcl_EYE_Close_L': 2, 'Face_Blendshape.Fcl_EYE_Close_R': 3, 'Face_Blendshape.Fcl_BRW_Angry': 4 };
  m.morphTargetInfluences = [0, 0, 0, 0, 0];
  return m;
}

describe('ExpressiveFace on a three.js mesh', () => {
  it('generates the one-sided smirk shapes from the symmetric smile with the same mask as the bake', () => {
    const root = new THREE.Group();
    const m = faceMesh();
    root.add(m);
    const f = new ExpressiveFace(root);
    expect(f.binding.rig).toBe('vroid');
    expect(m.morphTargetDictionary!['Fcl_MTH_Fun_L']).toBe(5);
    expect(m.morphTargetInfluences).toHaveLength(7);
    const L = m.geometry.morphAttributes.position[5] as THREE.BufferAttribute;
    // +x is the face's own left: full lift (x gain 2.0) there, none on the right, half in the middle
    expect(L.getY(4)).toBeCloseTo(0.01 * 2.0 * sideMask(0.04, 'L'));
    expect(L.getY(0)).toBeCloseTo(0);
    expect(L.getY(2)).toBeCloseTo(0.01 * 2.0 * 0.5);
    const w = f.apply(channelsFromState({ smirk: 0.8 }));
    expect(w['Fcl_MTH_Fun_L']).toBeCloseTo(0.8);
    expect(m.morphTargetInfluences![5]).toBeCloseTo(0.8);
    f.apply({});               // decays: nothing sticks
    expect(m.morphTargetInfluences![5]).toBe(0);
  });
  it('GlbAvatar: FaceChannel.apply writes the expressive channels last (mouth gain, brows, per-eye blink)', () => {
    const scene = new THREE.Group();
    const m = faceMesh();
    scene.add(m);
    const glb = new GlbAvatar(scene, [], 'vroid-strip');
    expect(glb.faceCheck.rig).toBe('vroid');
    FaceChannel.apply(glb, {
      open: 1, visemes: { aa: 1, ih: 0, ou: 0, ee: 0, oh: 0 }, emotions: { happy: 0, angry: 1, sad: 0, surprised: 0, relaxed: 0 }, blink: 0,
      expressive: { blinkL: 1 },
    });
    const dict = m.morphTargetDictionary!;
    expect(m.morphTargetInfluences![dict['Face_Blendshape.Fcl_MTH_A']]).toBeCloseTo(1.35);
    expect(m.morphTargetInfluences![dict['Face_Blendshape.Fcl_BRW_Angry']]).toBeCloseTo(Math.min(1.5, 0.9 * 1.5));  // angry 1 -> browDown 0.9 x VRoid brow gain 1.5
    expect(m.morphTargetInfluences![dict['Face_Blendshape.Fcl_EYE_Close_L']]).toBe(1);
    expect(m.morphTargetInfluences![dict['Face_Blendshape.Fcl_EYE_Close_R']]).toBe(0);
  });
});
