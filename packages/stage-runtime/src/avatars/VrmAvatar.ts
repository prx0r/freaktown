/** VRM body: humanoid bones + VRM expression presets (visemes, blink, emotions). */

import * as THREE from 'three';
import type { VRM } from '@pixiv/three-vrm';
import { attachMouthAnchor } from './mouthAnchor';
import { ExpressiveFace, type Channels, type FaceCheck } from '../face/expressive';
import type { AvatarCapabilities, AvatarDriver, Emotions, PoseState, Visemes } from './types';

const VISEMES = ['aa', 'ih', 'ou', 'ee', 'oh'] as const;
const EMOTIONS = ['happy', 'angry', 'sad', 'surprised', 'relaxed'] as const;
const PRESETS = new Set<string>([...VISEMES, ...EMOTIONS, 'blink', 'blinkLeft', 'blinkRight', 'neutral', 'lookUp', 'lookDown', 'lookLeft', 'lookRight']);

export class VrmAvatar implements AvatarDriver {
  readonly root: THREE.Object3D;
  readonly caps: AvatarCapabilities;
  private vrm: VRM;
  private has = new Set<string>();
  private baseHipsY = 0;
  private seated = false;

  constructor(vrm: VRM, name: string) {
    this.vrm = vrm;
    this.root = vrm.scene;
    const em = vrm.expressionManager;
    for (const e of em?.expressions ?? []) this.has.add(e.expressionName);
    const visemes = VISEMES.filter((v) => this.has.has(v));
    this.caps = {
      kind: 'vrm',
      name,
      mouthMode: visemes.length >= 2 ? 'viseme' : this.has.has('jawOpen') ? 'jaw' : 'none',
      hasBlink: this.has.has('blink'),
      hasExpressions: EMOTIONS.some((e) => this.has.has(e)),
      hasSkeleton: !!vrm.humanoid,
      morphNames: [...this.has],
    };
    const hips = vrm.humanoid?.getNormalizedBoneNode('hips');
    this.baseHipsY = hips?.position.y ?? 0;
  }

  private set(name: string, v: number): void {
    // in expressive mode the raw morphs carry mouth/blink/emotion; the presets stay at 0 so nothing doubles
    if (this.expressiveFace && PRESETS.has(name)) v = 0;
    if (this.has.has(name)) this.vrm.expressionManager?.setValue(name, Math.max(0, Math.min(1, v)));
  }

  /**
   * Expressive mode (face/expressive.ts): for VRMs whose meshes carry a rig in expressive-map.json (VRoid Fcl_*,
   * ARKit), the face is written as raw morphs with the map's gains (aa reaches 1.35, one-sided smiles are
   * generated) AFTER vrm.update(), because the expression manager rewrites every bound morph each update.
   */
  private expressiveFace: ExpressiveFace | null = null;
  private pending: Channels | null = null;
  setExpressive(ch: Channels): void {
    if (!this.expressiveFace) {
      const f = new ExpressiveFace(this.vrm.scene);
      if (!f.binding.rig || f.binding.rig === 'vrm' || f.check.level === 'fail') return;
      this.expressiveFace = f;
    }
    this.pending = ch;
  }
  get faceCheck(): FaceCheck { return (this.expressiveFace ?? new ExpressiveFace(this.vrm.scene, { generate: false })).check; }

  setMouth(open: number, vis: Visemes): void {
    if (this.caps.mouthMode === 'viseme') {
      for (const k of VISEMES) this.set(k, vis[k]);
    } else if (this.caps.mouthMode === 'jaw') {
      this.set('jawOpen', open);
    }
  }

  setBlink(amount: number): void { this.set('blink', amount); }

  setExpression(em: Emotions): void {
    for (const k of EMOTIONS) this.set(k, em[k]);
  }

  private mouth: THREE.Object3D | null = null;
  mouthAnchor(): THREE.Object3D | null {
    if (!this.mouth) {
      const h = this.vrm.humanoid;
      const raw = (n: 'head' | 'leftEye' | 'rightEye') => h?.getRawBoneNode(n) ?? null;
      this.mouth = attachMouthAnchor(this.root, raw('head'), [raw('leftEye'), raw('rightEye')].filter((x): x is THREE.Object3D => !!x));
    }
    return this.mouth;
  }

  setGazeTarget(target: THREE.Object3D): void {
    if (this.vrm.lookAt) this.vrm.lookAt.target = target;
  }

  setPose(p: PoseState): void {
    const h = this.vrm.humanoid;
    if (!h) return;
    const bone = (n: Parameters<typeof h.getNormalizedBoneNode>[0]) => h.getNormalizedBoneNode(n);
    const hips = bone('hips');
    if (hips) {
      hips.position.y = this.baseHipsY + p.bob - (this.seated ? this.baseHipsY * 0.46 : 0);
      hips.position.x = p.swayX;
      hips.rotation.z = -p.swayX * 0.6;
    }
    const spine = bone('spine');
    if (spine) { spine.rotation.x = p.spinePitch * 0.5 + p.breath * 0.01; spine.rotation.z = p.spineRoll * 0.5 + p.swayX * 0.4; }
    const chest = bone('chest') ?? bone('upperChest');
    if (chest) chest.rotation.x = p.spinePitch * 0.5 + p.breath * 0.02;
    const neck = bone('neck');
    if (neck) { neck.rotation.x = p.headPitch * 0.4; neck.rotation.y = p.headYaw * 0.4; }
    const head = bone('head');
    if (head) { head.rotation.x = p.headPitch * 0.6; head.rotation.y = p.headYaw * 0.6; head.rotation.z = p.headRoll; }

    // VRM normalized rest = T-pose, facing +Z. Left arm points +X.
    const arm = (side: 'left' | 'right', a: PoseState['armL']) => {
      const s = side === 'left' ? 1 : -1;
      const sh = bone(`${side}Shoulder` as any);
      if (sh) sh.rotation.z = s * p.shoulderUp * 0.25;
      const up = bone(`${side}UpperArm` as any);
      if (up) {
        // down ≈ 1.25 rad from horizontal; raise lifts toward forward/side
        const drop = 1.25 * (1 - a.raise);
        up.rotation.set(0, 0, 0);
        up.rotation.z = -s * drop;
        up.rotation.y = s * (1 - a.out) * 0.9 * (0.35 + a.raise);
      }
      const low = bone(`${side}LowerArm` as any);
      if (low) {
        low.rotation.set(0, 0, 0);
        low.rotation.y = s * (a.bend * 1.6);
        low.rotation.z = s * a.wave;
      }
    };
    arm('left', p.armL);
    arm('right', p.armR);
    // seated: thighs forward (-X rot lifts the foot to +Z), shins back down
    for (const side of ['left', 'right'] as const) {
      const ul = bone(`${side}UpperLeg` as any);
      const ll = bone(`${side}LowerLeg` as any);
      if (ul) { ul.rotation.x = this.seated ? -1.45 : 0; ul.rotation.z = this.seated ? (side === 'left' ? 0.08 : -0.08) : 0; }
      if (ll) ll.rotation.x = this.seated ? 1.45 : 0;
    }
  }

  setSeated(seated: boolean): void { this.seated = seated; }

  /** ARKit names that the VRM carries as custom expressions (VRM1 allows any name). Presets are untouched. */
  setBlendshapes(weights: Partial<Record<string, number>>): void {
    for (const [name, v] of Object.entries(weights)) {
      if (v === undefined || !this.has.has(name) || PRESETS.has(name)) continue;
      this.set(name, v);
    }
  }

  update(dt: number): void {
    this.vrm.update(dt);
    if (this.expressiveFace && this.pending) this.expressiveFace.apply(this.pending);
  }

  dispose(): void {
    this.root.parent?.remove(this.root);
    this.root.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
    });
  }
}
