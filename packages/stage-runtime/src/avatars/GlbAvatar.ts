/**
 * Plain GLB body (three.ws / Meshy / character-meshes). Capabilities are
 * sniffed from the bytes, same doctrine as face_profiles.py:
 *   visemes (Oculus viseme_* / ARKit / VRM0 A-I-U-E-O) → 'viseme'
 *   jawOpen / mouthOpen morph                         → 'morph'
 *   a jaw bone                                        → 'jaw'
 *   nothing                                           → 'none' (body bob only, never a fake mouth)
 */

import * as THREE from 'three';
import type { AvatarCapabilities, AvatarDriver, Emotions, PoseState, Visemes, VisemeKey } from './types';

type MorphRef = { mesh: THREE.Mesh; index: number };

const VISEME_NAMES: Record<VisemeKey, string[]> = {
  aa: ['viseme_aa', 'v_aa', 'aa', 'A', 'mouth_a', 'Fcl_MTH_A'],
  ih: ['viseme_I', 'viseme_ih', 'v_ih', 'ih', 'I', 'mouth_i', 'Fcl_MTH_I'],
  ou: ['viseme_U', 'viseme_ou', 'v_ou', 'ou', 'U', 'mouth_u', 'Fcl_MTH_U'],
  ee: ['viseme_E', 'viseme_ee', 'v_e', 'ee', 'E', 'mouth_e', 'Fcl_MTH_E'],
  oh: ['viseme_O', 'viseme_oh', 'v_oh', 'oh', 'O', 'mouth_o', 'Fcl_MTH_O'],
};
const OPEN_NAMES = ['jawOpen', 'JawOpen', 'jaw_open', 'mouthOpen', 'MouthOpen', 'mouth_open', 'Mouth_Open'];
const BLINK_NAMES = ['eyeBlinkLeft', 'eyeBlinkRight', 'blink', 'Blink', 'eyesClosed', 'Eyes_Closed', 'Fcl_EYE_Close'];
const EMOTION_NAMES: Record<keyof Emotions, string[]> = {
  // FACS-calibrated (AUBlendNet Table 2; see face_profiles.py):
  // Happy AU6+12, Anger AU4+5+7+9+23, Sad AU1+4+15, Surprise AU1+2+5+27.
  happy: ['mouthSmileLeft', 'mouthSmileRight', 'cheekSquintLeft', 'cheekSquintRight', 'happy', 'smile', 'Smile'],
  angry: ['browDownLeft', 'browDownRight', 'eyeSquintLeft', 'eyeSquintRight', 'noseSneerLeft', 'noseSneerRight', 'mouthPressLeft', 'mouthPressRight', 'angry'],
  sad: ['mouthFrownLeft', 'mouthFrownRight', 'browInnerUp', 'sad'],
  surprised: ['jawOpen', 'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'eyeWideLeft', 'eyeWideRight', 'surprised'],
  relaxed: ['relaxed'],
};

// AU-prosody morphs (aus.json track): brow flash on accent (AU1+AU2),
// eye widening on arousal (AU5). Bound by exact ARKit name when present;
// VRM0/MMD variants intentionally excluded (these shapes are ARKit-only).
const PROSODY_BROW = ['browInnerUp', 'browOuterUpLeft', 'browOuterUpRight'];
const PROSODY_EYE = ['eyeWideLeft', 'eyeWideRight'];

function findBone(root: THREE.Object3D, re: RegExp): THREE.Object3D | null {
  let hit: THREE.Object3D | null = null;
  root.traverse((o) => { if (!hit && (o as THREE.Bone).isBone && re.test(o.name)) hit = o; });
  return hit;
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

  constructor(scene: THREE.Object3D, animations: THREE.AnimationClip[], name: string) {
    // Wrap so procedural bob never fights the asset's own root transform.
    this.body.add(scene);
    this.root = new THREE.Group();
    this.root.add(this.body);
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
    const pick = (names: string[]) => names.flatMap((n) => this.morphs.get(n) ?? []);
    for (const k of Object.keys(VISEME_NAMES) as VisemeKey[]) {
      const refs = pick(VISEME_NAMES[k]);
      if (refs.length) this.visemes[k] = refs;
    }
    this.open = pick(OPEN_NAMES);
    this.blink = pick(BLINK_NAMES);
    for (const k of Object.keys(EMOTION_NAMES) as (keyof Emotions)[]) {
      const refs = pick(EMOTION_NAMES[k]);
      if (refs.length) this.emotions[k] = refs;
    }
    this.prosodyBrow = pick(PROSODY_BROW);
    this.prosodyEye = pick(PROSODY_EYE);
    {
      const seen = new Set<MorphRef>();
      const all: MorphRef[] = [];
      const add = (refs: MorphRef[]) => {
        for (const r of refs) if (!seen.has(r)) { seen.add(r); all.push(r); }
      };
      for (const k of Object.keys(EMOTION_NAMES) as (keyof Emotions)[]) add(pick(EMOTION_NAMES[k]));
      add(this.prosodyBrow);
      add(this.prosodyEye);
      this.faceMorphs = all;
    }
    this.jaw = findBone(scene, /jaw/i);
    if (this.jaw) this.jawRest.copy(this.jaw.rotation);
    this.head = findBone(scene, /head$|head_|:head/i);
    this.spine = findBone(scene, /spine2|spine1|spine|chest/i);
    if (this.head) this.headRest.copy(this.head.rotation);
    if (this.spine) this.spineRest.copy(this.spine.rotation);

    const visemeCount = Object.keys(this.visemes).length;
    const mouthMode = visemeCount >= 2 ? 'viseme' : this.open.length ? 'morph' : this.jaw ? 'jaw' : 'none';
    let hasSkeleton = false;
    scene.traverse((o) => { if ((o as THREE.SkinnedMesh).isSkinnedMesh) hasSkeleton = true; });
    this.caps = {
      kind: 'glb', name, mouthMode, hasBlink: this.blink.length > 0,
      hasExpressions: Object.keys(this.emotions).length > 0, hasSkeleton,
      morphNames: [...this.morphs.keys()],
    };

    if (animations.length) {
      const clip = animations.find((a) => /idle|breath|stand/i.test(a.name)) ?? animations[0];
      this.mixer = new THREE.AnimationMixer(scene);
      this.mixer.clipAction(clip).play();
    }
  }

  private setRefs(refs: MorphRef[] | undefined, v: number): void {
    if (!refs) return;
    for (const r of refs) if (r.mesh.morphTargetInfluences) r.mesh.morphTargetInfluences[r.index] = Math.max(0, Math.min(1, v));
  }

  setMouth(open: number, vis: Visemes): void {
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
   */
  setExpression(em: Emotions, prosody?: { brow: number; eye: number }): void {
    const goals = new Map<MorphRef, number>();
    const put = (refs: MorphRef[] | undefined, v: number) => {
      if (!refs || v <= 0) return;
      for (const r of refs) goals.set(r, Math.max(goals.get(r) ?? 0, v));
    };
    for (const k of Object.keys(this.emotions) as (keyof Emotions)[]) put(this.emotions[k], em[k] ?? 0);
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
