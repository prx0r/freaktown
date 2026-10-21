/**
 * AvatarDriver — one interface over every body tier (NORTHSTAR):
 *   VRM (humanoid + expressions) → GLB (sniffed morphs/jaw/bones) → BASIC.
 * The Performer computes a PoseState + face channels; each driver maps
 * them onto whatever the bytes actually contain. Never fake a mouth the
 * rig does not have: GLBs without morphs/jaw report mouthMode 'none'.
 */

import type * as THREE from 'three';

export type AvatarKind = 'vrm' | 'glb' | 'basic';
export type MouthMode = 'viseme' | 'jaw' | 'morph' | 'none';
export type VisemeKey = 'aa' | 'ih' | 'ou' | 'ee' | 'oh';
export type Visemes = Record<VisemeKey, number>;
export type EmotionKey = 'happy' | 'angry' | 'sad' | 'surprised' | 'relaxed';
export type Emotions = Record<EmotionKey, number>;

export const ZERO_VISEMES: Visemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
export const ZERO_EMOTIONS: Emotions = { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 };

export interface ArmPose {
  /** 0 = hanging, 1 = horizontal forward/side */
  raise: number;
  /** 0 = in front, 1 = out to the side */
  out: number;
  /** elbow bend 0..1 */
  bend: number;
  /** forearm wave oscillation (radians offset) */
  wave: number;
}

export interface PoseState {
  breath: number;      // -1..1
  swayX: number;       // metres-ish lateral weight shift
  bob: number;         // vertical bob (m)
  spinePitch: number;  // + = lean forward (rad)
  spineRoll: number;
  headPitch: number;   // + = nod down (rad)
  headYaw: number;     // + = look to character's left (rad)
  headRoll: number;
  shoulderUp: number;  // shrug 0..1
  armL: ArmPose;
  armR: ArmPose;
}

export function neutralPose(): PoseState {
  const arm = (): ArmPose => ({ raise: 0, out: 0.12, bend: 0.15, wave: 0 });
  return {
    breath: 0, swayX: 0, bob: 0, spinePitch: 0, spineRoll: 0,
    headPitch: 0, headYaw: 0, headRoll: 0, shoulderUp: 0, armL: arm(), armR: arm(),
  };
}

export interface AvatarCapabilities {
  kind: AvatarKind;
  name: string;
  mouthMode: MouthMode;
  hasBlink: boolean;
  hasExpressions: boolean;
  hasSkeleton: boolean;
  morphNames: string[];
}

export interface AvatarDriver {
  readonly root: THREE.Object3D;
  readonly caps: AvatarCapabilities;
  /** open 0..1 + viseme weights (already scaled by open). */
  setMouth(open: number, visemes: Visemes): void;
  setBlink(amount: number): void;
  setExpression(emotions: Emotions, prosody?: { brow: number; eye: number }): void;
  setPose(pose: PoseState): void;
  /** Gaze target in world space (VRM lookAt; others ignore or aim head). */
  setGazeTarget(target: THREE.Object3D): void;
  /** Optional seated variant (sets): bend hips/knees, drop the pelvis onto a 0.48 m seat. */
  setSeated?(seated: boolean): void;
  /**
   * Optional raw ARKit-52 weights (face/FaceChannel). Drivers write only names their
   * bytes carry (GLB morphs, VRM custom expressions); BASIC maps a few by construction.
   */
  setBlendshapes?(weights: Partial<Record<string, number>>): void;
  update(dt: number): void;
  dispose(): void;
}
