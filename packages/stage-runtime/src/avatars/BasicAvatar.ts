/**
 * BASIC procedural body — the guaranteed instant fallback (NORTHSTAR tier 0).
 * Built from primitives, so it always has a mouth, blink and brows: the one
 * tier where the face is ours by construction, not sniffed.
 */

import * as THREE from 'three';
import type { AvatarCapabilities, AvatarDriver, Emotions, PoseState, Visemes } from './types';

export interface BasicAvatarOptions {
  name?: string;
  variant?: 'human' | 'robot';
  /** Seed for the palette (e.g. character id). */
  seed?: string;
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

const PALETTES = [
  { skin: 0xf0c4a0, shirt: 0x2d6cdf, pants: 0x23263a, accent: 0xffcc33 },
  { skin: 0xc68a62, shirt: 0xd8442f, pants: 0x1f2a24, accent: 0x3fe0c5 },
  { skin: 0x8fd16a, shirt: 0x6b3fa0, pants: 0x2a2233, accent: 0xff5ea8 },
  { skin: 0xb7c3d0, shirt: 0x333a48, pants: 0x1a1d24, accent: 0x33ddff },
];

function mat(color: number, rough = 0.6, metal = 0.05, emissive = 0): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, emissive: emissive ? color : 0x000000, emissiveIntensity: emissive });
}

function capsule(r: number, len: number, m: THREE.Material): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 14), m);
  mesh.castShadow = true;
  return mesh;
}

export class BasicAvatar implements AvatarDriver {
  readonly root = new THREE.Group();
  readonly caps: AvatarCapabilities;
  private torso = new THREE.Group();
  private head = new THREE.Group();
  private shoulderL = new THREE.Group();
  private shoulderR = new THREE.Group();
  private elbowL = new THREE.Group();
  private elbowR = new THREE.Group();
  private lids: THREE.Mesh[] = [];
  private browL!: THREE.Mesh;
  private browR!: THREE.Mesh;
  private mouth!: THREE.Mesh;
  private jaw!: THREE.Mesh;
  private pupils: THREE.Mesh[] = [];
  private emotions: Emotions = { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 };
  private mouthOpen = 0;
  private legsStanding = new THREE.Group();
  private legsSeated = new THREE.Group();
  private hipY = 0.88;

  constructor(opts: BasicAvatarOptions = {}) {
    const variant = opts.variant ?? 'human';
    const pal = PALETTES[hash(opts.seed ?? opts.name ?? 'basic') % PALETTES.length];
    const skin = variant === 'robot' ? mat(0xb9c4d2, 0.35, 0.6) : mat(pal.skin, 0.7);
    const shirt = mat(pal.shirt, 0.65);
    const pants = mat(pal.pants, 0.8);
    const dark = mat(0x140a0a, 0.9);
    const white = mat(0xffffff, 0.3);

    // legs + shoes (standing) and a seated variant (thighs forward, shins down)
    this.root.add(this.legsStanding, this.legsSeated);
    this.legsSeated.visible = false;
    for (const x of [-0.11, 0.11]) {
      const leg = capsule(0.085, 0.72, pants);
      leg.position.set(x, 0.45, 0);
      this.legsStanding.add(leg);
      const shoe = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.08, 0.26), dark);
      shoe.position.set(x, 0.04, 0.05);
      shoe.castShadow = true;
      this.legsStanding.add(shoe);
      const thigh = capsule(0.088, 0.36, pants);
      thigh.rotation.x = Math.PI / 2;
      thigh.position.set(x, 0.53, 0.2);
      this.legsSeated.add(thigh);
      const shin = capsule(0.075, 0.36, pants);
      shin.position.set(x, 0.27, 0.42);
      this.legsSeated.add(shin);
      const sshoe = shoe.clone();
      sshoe.position.set(x, 0.04, 0.47);
      this.legsSeated.add(sshoe);
    }
    // torso pivot at hips
    this.torso.position.y = 0.88;
    this.root.add(this.torso);
    const body = capsule(0.22, 0.42, shirt);
    body.position.y = 0.3;
    body.scale.set(1.1, 1, 0.8);
    this.torso.add(body);
    const tie = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.28, 0.02), mat(pal.accent, 0.5));
    tie.position.set(0, 0.36, 0.18);
    this.torso.add(tie);

    // arms
    const mkArm = (sh: THREE.Group, el: THREE.Group, x: number) => {
      sh.position.set(x, 0.56, 0);
      this.torso.add(sh);
      const upper = capsule(0.06, 0.24, shirt);
      upper.position.y = -0.16;
      sh.add(upper);
      el.position.y = -0.32;
      sh.add(el);
      const lower = capsule(0.052, 0.22, variant === 'robot' ? skin : shirt);
      lower.position.y = -0.14;
      el.add(lower);
      const hand = new THREE.Mesh(new THREE.SphereGeometry(0.058, 14, 10), skin);
      hand.position.y = -0.3;
      hand.castShadow = true;
      el.add(hand);
    };
    mkArm(this.shoulderL, this.elbowL, 0.29);
    mkArm(this.shoulderR, this.elbowR, -0.29);

    // neck + head
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.1, 12), skin);
    neck.position.y = 0.6;
    this.torso.add(neck);
    this.head.position.y = 0.64;
    this.torso.add(this.head);
    const skull = variant === 'robot'
      ? new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.32, 0.3, 2, 2, 2), skin)
      : new THREE.Mesh(new THREE.SphereGeometry(0.17, 28, 20), skin);
    skull.position.y = 0.17;
    if (variant !== 'robot') skull.scale.set(1, 1.08, 0.98);
    skull.castShadow = true;
    this.head.add(skull);
    if (variant === 'robot') {
      const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.14, 6), skin);
      antenna.position.set(0, 0.39, 0);
      this.head.add(antenna);
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.025, 12, 8), mat(pal.accent, 0.3, 0, 1.5));
      bulb.position.set(0, 0.47, 0);
      this.head.add(bulb);
    } else {
      const hair = new THREE.Mesh(new THREE.SphereGeometry(0.175, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.45), mat(0x2b1b10, 0.9));
      hair.position.y = 0.19;
      hair.rotation.x = -0.25;
      this.head.add(hair);
      const nose = new THREE.Mesh(new THREE.SphereGeometry(0.028, 12, 8), skin);
      nose.position.set(0, 0.15, 0.17);
      this.head.add(nose);
    }
    const faceZ = variant === 'robot' ? 0.155 : 0.145;
    for (const x of [-0.062, 0.062]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(0.042, 16, 12), variant === 'robot' ? mat(pal.accent, 0.3, 0, 1.2) : white);
      eye.position.set(x, 0.2, faceZ);
      eye.scale.z = 0.6;
      this.head.add(eye);
      const pupil = new THREE.Mesh(new THREE.SphereGeometry(0.019, 12, 8), dark);
      pupil.position.set(x, 0.2, faceZ + 0.024);
      this.head.add(pupil);
      this.pupils.push(pupil);
      const lid = new THREE.Mesh(new THREE.SphereGeometry(0.046, 16, 12), skin);
      lid.position.set(x, 0.2, faceZ + 0.004);
      lid.scale.set(1, 0.02, 0.7);
      this.head.add(lid);
      this.lids.push(lid);
    }
    this.browR = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.014, 0.02), dark);
    this.browL = this.browR.clone();
    this.browR.position.set(-0.062, 0.26, faceZ + 0.01);
    this.browL.position.set(0.062, 0.26, faceZ + 0.01);
    this.head.add(this.browL, this.browR);
    this.mouth = new THREE.Mesh(new THREE.SphereGeometry(0.05, 18, 12), mat(0x3a0a12, 0.9));
    this.mouth.position.set(0, 0.075, faceZ + 0.01);
    this.mouth.scale.set(1, 0.12, 0.35);
    this.head.add(this.mouth);
    this.jaw = new THREE.Mesh(new THREE.SphereGeometry(0.075, 16, 10, 0, Math.PI * 2, Math.PI * 0.5, Math.PI * 0.5), skin);
    this.jaw.position.set(0, 0.07, faceZ - 0.05);
    this.jaw.scale.set(1, 0.6, 0.9);
    if (variant !== 'robot') this.head.add(this.jaw);

    this.caps = {
      kind: 'basic', name: opts.name ?? 'BASIC', mouthMode: 'jaw', hasBlink: true,
      hasExpressions: true, hasSkeleton: false, morphNames: [],
    };
  }

  setMouth(open: number, v: Visemes): void {
    this.mouthOpen = open;
    const width = 1 + v.ee * 0.5 + v.ih * 0.3 - v.ou * 0.45 - v.oh * 0.2 + this.emotions.happy * 0.35;
    this.mouth.scale.set(Math.max(0.45, width), 0.1 + open * 0.95, 0.35);
    this.mouth.position.y = 0.075 - open * 0.012 + this.emotions.happy * 0.006;
    this.jaw.position.y = 0.07 - open * 0.03;
  }

  setBlink(amount: number): void {
    for (const l of this.lids) l.scale.y = Math.max(0.02, amount);
  }

  setExpression(e: Emotions): void {
    this.emotions = { ...e };
    const raise = e.surprised * 0.025 - e.angry * 0.01 + e.sad * 0.006;
    const tilt = e.angry * 0.45 - e.sad * 0.4;
    this.browL.position.y = 0.26 + raise;
    this.browR.position.y = 0.26 + raise;
    this.browL.rotation.z = tilt;
    this.browR.rotation.z = -tilt;
    this.setMouth(this.mouthOpen, { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
  }

  setGazeTarget(): void { /* head aim via setPose */ }
  mouthAnchor(): THREE.Object3D | null { return this.mouth; }

  /** BASIC by construction: asymmetric brows, sneer/smile side shift, cheek puff, eye wide. */
  setBlendshapes(w: Partial<Record<string, number>>): void {
    const g = (k: string) => Math.max(0, Math.min(1, w[k] ?? 0));
    this.browL.position.y += (g('browOuterUpLeft') - g('browDownLeft')) * 0.02;
    this.browR.position.y += (g('browOuterUpRight') - g('browDownRight')) * 0.02;
    const side = (g('mouthSmileLeft') - g('mouthSmileRight')) * 0.012 + (g('mouthLeft') - g('mouthRight')) * 0.015;
    this.mouth.position.x = side;
    const wide = Math.max(g('eyeWideLeft'), g('eyeWideRight'));
    for (const p of this.pupils) p.scale.setScalar(1 - wide * 0.25);
    if (this.jaw) this.jaw.scale.x = 1 + g('cheekPuff') * 0.25;
  }

  setSeated(seated: boolean): void {
    this.legsStanding.visible = !seated;
    this.legsSeated.visible = seated;
    this.hipY = seated ? 0.53 : 0.88;
    this.torso.position.y = this.hipY;
  }

  setPose(p: PoseState): void {
    this.root.position.x = p.swayX;
    this.torso.position.y = this.hipY + p.bob;
    this.torso.rotation.set(p.spinePitch, 0, p.spineRoll - p.swayX * 0.4);
    this.torso.scale.set(1 + p.breath * 0.012, 1, 1 + p.breath * 0.02);
    this.head.rotation.set(p.headPitch, p.headYaw, p.headRoll);
    const arm = (sh: THREE.Group, el: THREE.Group, a: PoseState['armL'], s: number) => {
      sh.position.y = 0.56 + p.shoulderUp * 0.05;
      sh.rotation.set(-a.raise * 1.45, 0, s * (0.08 + a.out * 1.1));
      el.rotation.set(-a.bend * 1.7, 0, s * a.wave);
    };
    arm(this.shoulderL, this.elbowL, p.armL, 1);
    arm(this.shoulderR, this.elbowR, p.armR, -1);
    for (const pu of this.pupils) pu.position.x = Math.sign(pu.position.x) * 0.062 + p.headYaw * 0.01;
  }

  update(): void { /* no mixer */ }

  dispose(): void { this.root.parent?.remove(this.root); }
}
