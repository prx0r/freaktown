/**
 * Plain GLB body (three.ws / Meshy / character-meshes). Capabilities are
 * sniffed from the bytes, same doctrine as face_profiles.py:
 *   visemes (Oculus viseme_* / ARKit / VRM0 A-I-U-E-O) → 'viseme'
 *   jawOpen / mouthOpen morph                         → 'morph'
 *   a jaw bone                                        → 'jaw'
 *   nothing, skinned + Head bone                      → procedural jawOpen/blink morphs (faceRig 'auto', warned)
 *   nothing at all                                    → 'none' (body bob only, warned)
 * Name matching lives in face/meshBinding.ts (alias map, shared with `npm run face:check`).
 */

import * as THREE from 'three';
import { attachMouthAnchor } from './mouthAnchor';
import { bindFace, describeBinding, type FaceBinding } from '../face/meshBinding';
import { proceduralFaceRig, inferUp } from '../face/proceduralRig';
import type { AvatarCapabilities, AvatarDriver, Emotions, PoseState, Visemes, VisemeKey } from './types';

type MorphRef = { mesh: THREE.Mesh; index: number };

export interface GlbAvatarOptions {
  /**
   * 'auto' (default): a skinned GLB with a Head bone but NO face channels gets
   * procedural jawOpen + eyeBlinkLeft/Right morphs at load (face/proceduralRig),
   * with a console warning. 'off': drive only what the bytes carry.
   */
  faceRig?: 'auto' | 'off';
  /** Where face warnings go (default console.warn). */
  warn?: (msg: string) => void;
}

/** A clip whose every track holds one key is a baked rest pose (Meshy/Mixamo export), not motion. */
function isStaticClip(clip: THREE.AnimationClip): boolean {
  return clip.tracks.length > 0 && clip.tracks.every((t) => t.times.length <= 1);
}

function findBone(root: THREE.Object3D, re: RegExp): THREE.Object3D | null {
  let hit: THREE.Object3D | null = null;
  root.traverse((o) => { if (!hit && (o as THREE.Bone).isBone && re.test(o.name)) hit = o; });
  return hit;
}

function boneByName(root: THREE.Object3D, name: string | null): THREE.Object3D | null {
  if (!name) return null;
  let hit: THREE.Object3D | null = null;
  root.traverse((o) => { if (!hit && (o as THREE.Bone).isBone && o.name === name) hit = o; });
  return hit;
}

/** Add procedural face morphs to the skinned mesh carrying the most head weight. */
function rigProcedurally(scene: THREE.Object3D, headName: string): { mesh: THREE.SkinnedMesh; warnings: string[] } | null {
  let best: { mesh: THREE.SkinnedMesh; res: ReturnType<typeof proceduralFaceRig> } | null = null;
  scene.traverse((o) => {
    const sm = o as THREE.SkinnedMesh;
    if (!sm.isSkinnedMesh || !sm.skeleton) return;
    const g = sm.geometry;
    const pos = g.getAttribute('position'), si = g.getAttribute('skinIndex'), sw = g.getAttribute('skinWeight');
    if (!pos || !si || !sw) return;
    const head = sm.skeleton.bones.findIndex((b) => b.name === headName);
    if (head < 0) return;
    const headJoints = new Set<number>();
    sm.skeleton.bones[head].traverse((b) => { const k = sm.skeleton.bones.indexOf(b as THREE.Bone); if (k >= 0) headJoints.add(k); });
    const n = pos.count;
    const P = new Float32Array(n * 3), J = new Float32Array(n * 4), W = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
      P[i * 3] = pos.getX(i); P[i * 3 + 1] = pos.getY(i); P[i * 3 + 2] = pos.getZ(i);
      J[i * 4] = si.getX(i); J[i * 4 + 1] = si.getY(i); J[i * 4 + 2] = si.getZ(i); J[i * 4 + 3] = si.getW(i);
      W[i * 4] = sw.getX(i); W[i * 4 + 1] = sw.getY(i); W[i * 4 + 2] = sw.getZ(i); W[i * 4 + 3] = sw.getW(i);
    }
    const headIdx: number[] = [];
    for (let i = 0; i < n; i++) { let w = 0; for (let k = 0; k < 4; k++) if (headJoints.has(J[i * 4 + k])) w += W[i * 4 + k]; if (w >= 0.35) headIdx.push(i); }
    const up = inferUp(P, headIdx);
    const forward: [number, number, number] = Math.abs(up[2]) === 1 ? [0, -1, 0] : [0, 0, 1];
    const res = proceduralFaceRig({ positions: P, skinIndex: J, skinWeight: W, headJoints, up, forward });
    if (!res.targets.length) return;
    if (!best || res.landmarks.headVerts > best.res.landmarks.headVerts) best = { mesh: sm, res };
  });
  if (!best) return null;
  const { mesh, res } = best as { mesh: THREE.SkinnedMesh; res: ReturnType<typeof proceduralFaceRig> };
  const g = mesh.geometry;
  const had = g.morphAttributes.position?.length ?? 0;
  if (!had) g.morphTargetsRelative = true;
  const list = g.morphAttributes.position ?? [];
  for (const t of res.targets) {
    const a = new THREE.Float32BufferAttribute(t.deltas, 3);
    a.name = t.name;
    list.push(a);
    if (g.morphAttributes.normal) g.morphAttributes.normal.push(new THREE.Float32BufferAttribute(new Float32Array(t.deltas.length), 3));
  }
  g.morphAttributes.position = list;
  const prevNames = mesh.morphTargetDictionary ? Object.entries(mesh.morphTargetDictionary) : [];
  mesh.updateMorphTargets();
  // keep names GLTFLoader assigned to pre-existing targets
  for (const [k, i] of prevNames) mesh.morphTargetDictionary![k] = i;
  return { mesh, warnings: res.warnings };
}

export class GlbAvatar implements AvatarDriver {
  readonly root: THREE.Object3D;
  readonly caps: AvatarCapabilities;
  private morphs = new Map<string, MorphRef[]>();
  private visemes: Partial<Record<VisemeKey, MorphRef[]>> = {};
  private open: MorphRef[] = [];
  private blink: MorphRef[] = [];
  private emotions: Partial<Record<keyof Emotions, MorphRef[]>> = {};
  private prosodyBrow: MorphRef[] = [];
  private prosodyEye: MorphRef[] = [];
  /** Every morph the face channel ever writes (emotion + prosody). */
  private faceMorphs: MorphRef[] = [];
  private jaw: THREE.Object3D | null = null;
  private jawRest = new THREE.Euler();
  private head: THREE.Object3D | null = null;
  private spine: THREE.Object3D | null = null;
  private headRest = new THREE.Euler();
  private spineRest = new THREE.Euler();
  private bodyRestY = 0;
  private mixer: THREE.AnimationMixer | null = null;
  private body = new THREE.Group();

  /** The name binding the stage drives (same function face:check prints). */
  readonly binding: FaceBinding;
  /** Morphs the mouth/blink channels own; emotion/prosody writes never touch them. */
  private owned = new Set<MorphRef>();
  private exprJaw = 0;

  constructor(scene: THREE.Object3D, animations: THREE.AnimationClip[], name: string, opts: GlbAvatarOptions = {}) {
    const warn = opts.warn ?? ((m: string) => console.warn(m));
    // Wrap so procedural bob never fights the asset's own root transform.
    this.body.add(scene);
    this.root = new THREE.Group();
    this.root.add(this.body);
    const boneNames: string[] = [];
    scene.traverse((o) => { if ((o as THREE.Bone).isBone) boneNames.push(o.name); });
    const collect = () => {
      this.morphs.clear();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.isMesh) { m.castShadow = true; m.frustumCulled = false; }
        if (m.isMesh && m.morphTargetDictionary && m.morphTargetInfluences) {
          for (const [k, i] of Object.entries(m.morphTargetDictionary)) {
            const list = this.morphs.get(k) ?? [];
            list.push({ mesh: m, index: i });
            this.morphs.set(k, list);
          }
        }
      });
      return bindFace([...this.morphs.keys()], boneNames);
    };
    let binding = collect();
    let faceRig: 'bytes' | 'procedural' | 'none' = binding.mouthMode !== 'none' || binding.hasBlink ? 'bytes' : 'none';
    if (faceRig === 'none' && (opts.faceRig ?? 'auto') === 'auto' && binding.headBone) {
      const rigged = rigProcedurally(scene, binding.headBone);
      if (rigged) {
        binding = collect();
        faceRig = 'procedural';
        warn(`[face] ${name}: mesh has no face channels — generated procedural jawOpen/eyeBlinkLeft/eyeBlinkRight/browInnerUp/browDownLeft/browDownRight/mouthSmileLeft/mouthSmileRight on "${rigged.mesh.name}". Bake real shapes for a better face: docs/MESH-FACE-HOOKUP.md (npm run face:check <glb>)`);
        for (const w of rigged.warnings) warn(`[face] ${name}: ${w}`);
      }
    }
    this.binding = binding;
    if (binding.mouthMode === 'none') warn(`[face] ${name}: NO mouth channel — lip sync cannot move this mesh. ${describeBinding(binding)}. See docs/MESH-FACE-HOOKUP.md`);
    else if (!binding.hasBlink) warn(`[face] ${name}: no blink channel. ${describeBinding(binding)}`);

    const refs = (names: string[]) => names.flatMap((k) => this.morphs.get(k) ?? []);
    for (const [k, names] of Object.entries(binding.visemes) as [VisemeKey, string[]][]) this.visemes[k] = refs(names);
    this.open = refs(binding.open);
    this.blink = refs(binding.blink);
    for (const [k, names] of Object.entries(binding.emotions) as [keyof Emotions, string[]][]) this.emotions[k] = refs(names);
    this.prosodyBrow = refs(binding.prosodyBrow);
    this.prosodyEye = refs(binding.prosodyEye);
    for (const r of [...this.open, ...this.blink, ...Object.values(this.visemes).flat()]) if (r) this.owned.add(r);
    {
      const seen = new Set<MorphRef>();
      const all: MorphRef[] = [];
      const add = (rs: MorphRef[] | undefined) => {
        for (const r of rs ?? []) if (!seen.has(r) && !this.owned.has(r)) { seen.add(r); all.push(r); }
      };
      for (const k of Object.keys(this.emotions) as (keyof Emotions)[]) add(this.emotions[k]);
      add(this.prosodyBrow);
      add(this.prosodyEye);
      this.faceMorphs = all;
    }
    this.jaw = boneByName(scene, binding.jawBone);
    if (this.jaw) this.jawRest.copy(this.jaw.rotation);
    this.head = boneByName(scene, binding.headBone) ?? findBone(scene, /head$|head_|:head/i);
    this.spine = findBone(scene, /spine2|spine1|spine|chest/i);
    if (this.head) this.headRest.copy(this.head.rotation);
    if (this.spine) this.spineRest.copy(this.spine.rotation);

    let hasSkeleton = false;
    scene.traverse((o) => { if ((o as THREE.SkinnedMesh).isSkinnedMesh) hasSkeleton = true; });
    this.caps = {
      kind: 'glb', name, mouthMode: binding.mouthMode, hasBlink: binding.hasBlink,
      hasExpressions: binding.hasExpressions, hasSkeleton,
      morphNames: [...this.morphs.keys()],
      faceRig, faceWarnings: binding.warnings,
    };

    // A one-key clip is a baked rest pose; playing it adds nothing and would
    // own every bone the procedural pose writes. Real idle clips still play.
    const clips = animations.filter((a) => !isStaticClip(a));
    if (clips.length) {
      const clip = clips.find((a) => /idle|breath|stand/i.test(a.name)) ?? clips[0];
      this.mixer = new THREE.AnimationMixer(scene);
      this.mixer.clipAction(clip).play();
    }
  }

  private setRefs(refs: MorphRef[] | undefined, v: number): void {
    if (!refs) return;
    for (const r of refs) if (r.mesh.morphTargetInfluences) r.mesh.morphTargetInfluences[r.index] = Math.max(0, Math.min(1, v));
  }

  setMouth(openIn: number, vis: Visemes): void {
    // a surprised face drops the jaw a little; the mouth channel owns jawOpen
    const open = Math.max(openIn, this.exprJaw);
    if (this.caps.mouthMode === 'viseme') {
      for (const k of Object.keys(vis) as VisemeKey[]) this.setRefs(this.visemes[k], vis[k]);
      if (this.open.length) this.setRefs(this.open, open * 0.5);
    } else if (this.caps.mouthMode === 'morph') {
      this.setRefs(this.open, open);
    } else if (this.caps.mouthMode === 'jaw' && this.jaw) {
      this.jaw.rotation.x = this.jawRest.x + open * 0.35;
    }
  }

  setBlink(amount: number): void { this.setRefs(this.blink, amount); }

  /**
   * Beat/reactor emotions + AU-prosody lifts, resolved per morph with
   * max() so a brow flash never clears a surprised brow and vice versa.
   * Every bound face morph is written every call (goal or 0), so nothing
   * sticks when its source decays. Unknown morphs were never bound.
   * Mouth/blink morphs (jawOpen, visemes, blink) are NEVER written here: the
   * stage calls this a second time after setMouth() (AU prosody), and a
   * "goal or 0" write on jawOpen used to zero the mouth every frame.
   */
  setExpression(em: Emotions, prosody?: { brow: number; eye: number }): void {
    const goals = new Map<MorphRef, number>();
    const put = (refs: MorphRef[] | undefined, v: number) => {
      if (!refs || v <= 0) return;
      for (const r of refs) goals.set(r, Math.max(goals.get(r) ?? 0, v));
    };
    for (const k of Object.keys(this.emotions) as (keyof Emotions)[]) put(this.emotions[k], em[k] ?? 0);
    this.exprJaw = Math.min(0.35, (em.surprised ?? 0) * 0.35);
    if (prosody) {
      put(this.prosodyBrow, Math.min(0.4, prosody.brow));
      put(this.prosodyEye, Math.min(0.4, prosody.eye));
    }
    for (const r of this.faceMorphs) {
      const v = goals.get(r) ?? 0;
      if (r.mesh.morphTargetInfluences) r.mesh.morphTargetInfluences[r.index] = Math.max(0, Math.min(1, v));
    }
  }

  setGazeTarget(): void { /* head aim comes through setPose().headYaw */ }

  private mouth: THREE.Object3D | null = null;
  mouthAnchor(): THREE.Object3D | null {
    if (!this.mouth) this.mouth = attachMouthAnchor(this.root, this.head);
    return this.mouth;
  }

  setPose(p: PoseState): void {
    this.body.position.y = this.bodyRestY + p.bob + p.breath * 0.004;
    this.body.position.x = p.swayX;
    if (this.head) {
      this.head.rotation.set(this.headRest.x + p.headPitch, this.headRest.y + p.headYaw, this.headRest.z + p.headRoll);
    }
    if (this.spine) {
      this.spine.rotation.set(this.spineRest.x + p.spinePitch, this.spineRest.y, this.spineRest.z + p.spineRoll);
    }
    if (!this.head && !this.spine) {
      // Static mesh: whole-body puppet motion (procedural bob, never a fake mouth).
      this.body.rotation.x = p.spinePitch * 0.6 + p.headPitch * 0.3;
      this.body.rotation.y = p.headYaw * 0.5;
      this.body.rotation.z = p.spineRoll + p.headRoll * 0.4 - p.swayX * 0.5;
    }
  }

  /** ARKit (or any) morph names straight onto the meshes — only names present in the bytes. */
  setBlendshapes(weights: Partial<Record<string, number>>): void {
    for (const [name, v] of Object.entries(weights)) {
      const refs = this.morphs.get(name);
      if (!refs || v === undefined) continue;
      for (const r of refs) if (r.mesh.morphTargetInfluences) r.mesh.morphTargetInfluences[r.index] = Math.max(0, Math.min(1, v));
    }
  }

  update(dt: number): void { this.mixer?.update(dt); }

  dispose(): void { this.root.parent?.remove(this.root); }
}
