/**
 * Performer — procedural body + face channels from plan cues.
 *
 * Channels never clear each other (LipSync invariant):
 *   mouth  → MouthTrack / analyser (not here)
 *   face   → face.* / reaction.* cues (emotion envelopes)
 *   blink  → own timer (wall clock, keeps going while idle)
 *   body   → idle breath/sway + talking hands + gesture/pose cues
 */

import { neutralPose, type Emotions, type PoseState } from '../avatars/types';

interface Active {
  action: string;
  start: number;     // ms (performer clock)
  duration: number;
  intensity: number;
}

const FACE_MAP: Record<string, Partial<Emotions>> = {
  'face.smile': { happy: 1 },
  'face.smug': { happy: 0.6, relaxed: 0.5 },
  'face.frown': { sad: 1 },
  'face.annoyed': { angry: 1 },
  'face.surprised': { surprised: 1 },
  'face.deadpan': { relaxed: 0.35 },
  'face.disgusted': { angry: 0.6, sad: 0.35 },
  'reaction.confused': { surprised: 0.5 },
  'reaction.annoyed': { angry: 0.8 },
  'reaction.shock': { surprised: 1 },
  'reaction.dead_stare': { relaxed: 0.4 },
  'reaction.laugh': { happy: 0.8 },
  'reaction.groan': { sad: 0.6 },
  'reaction.boo': { sad: 0.5, angry: 0.3 },
};

export const GAZE_TARGETS: Record<string, { yaw: number; pitch: number }> = {
  'gaze.audience': { yaw: 0, pitch: 0 },
  'gaze.stare': { yaw: 0, pitch: -0.03 },
  'gaze.ella': { yaw: 0.5, pitch: 0 },
  'gaze.ground': { yaw: 0, pitch: 0.35 },
  'gaze.sky': { yaw: 0, pitch: -0.35 },
  'gaze.left': { yaw: 0.45, pitch: 0 },
  'gaze.right': { yaw: -0.45, pitch: 0 },
  'gaze.away': { yaw: 0.7, pitch: 0.1 },
};

function env(u: number, attack = 0.18, release = 0.3): number {
  if (u <= 0 || u >= 1) return 0;
  if (u < attack) return Math.sin((u / attack) * Math.PI / 2);
  if (u > 1 - release) return Math.sin(((1 - u) / release) * Math.PI / 2);
  return 1;
}

/** Mulberry32 — seeded so blinks are reproducible in capture mode. */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface PerformerFrame {
  pose: PoseState;
  emotions: Emotions;
  blink: number;
}

export class Performer {
  private active: Active[] = [];
  private gazeYaw = 0;
  private gazePitch = 0;
  private gazeTarget = { yaw: 0, pitch: 0 };
  private talk = 0;
  private rand = rng(7);
  private nextBlink = 1800;
  private blinkStart = -1;
  energy = 0.7;

  reset(): void {
    this.active = [];
    this.gazeTarget = { yaw: 0, pitch: 0 };
  }

  /** Fire a cue (plan cue on the media clock, or a live event). */
  trigger(action: string, intensity: number, durationMs: number, atMs: number): void {
    if (action.startsWith('gaze.')) {
      this.gazeTarget = GAZE_TARGETS[action] ?? this.gazeTarget;
      return;
    }
    // A new face cue replaces the previous face cue (one expression at a time).
    if (action.startsWith('face.') || action.startsWith('reaction.')) {
      this.active = this.active.filter((a) => !(a.action.startsWith('face.') || a.action.startsWith('reaction.')));
    }
    this.active.push({ action, start: atMs, duration: Math.max(200, durationMs), intensity });
  }

  /**
   * @param t      performer clock in ms (media time while playing; wall time idle)
   * @param wallMs wall clock ms (blink)
   * @param mouthOpen current mouth openness 0..1 (drives talking motion)
   */
  update(t: number, wallMs: number, dt: number, mouthOpen: number): PerformerFrame {
    const p = neutralPose();
    const emotions: Emotions = { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 };
    this.active = this.active.filter((a) => t < a.start + a.duration + 50 && t >= a.start - 5000);

    let freeze = 0;
    for (const a of this.active) {
      const u = (t - a.start) / a.duration;
      if (u < 0 || u > 1) continue;
      if (a.action === 'locomotion.freeze') freeze = Math.max(freeze, env(u, 0.1, 0.2));
    }
    const live = 1 - 0.85 * freeze;

    // idle: breath + weight shift + micro head motion
    const s = wallMs / 1000;
    p.breath = Math.sin((s / 3.8) * Math.PI * 2);
    p.swayX = 0.018 * Math.sin((s / 6.5) * Math.PI * 2) * live;
    p.headYaw = 0.04 * Math.sin(s * 0.7) * live;
    p.headRoll = 0.025 * Math.sin(s * 0.45 + 1) * live;

    // talking: nods + hands follow the mouth
    this.talk += (mouthOpen - this.talk) * Math.min(1, dt * 10);
    const e = this.talk * live * (0.6 + this.energy * 0.6);
    p.headPitch += e * 0.07 * Math.sin(t * 0.011) + mouthOpen * 0.03 * live;
    p.bob += e * 0.008 * Math.abs(Math.sin(t * 0.009));
    p.armR.raise += e * (0.22 + 0.12 * Math.sin(t * 0.0023));
    p.armR.bend += e * (0.5 + 0.2 * Math.sin(t * 0.0031));
    p.armR.out += e * 0.15;
    p.armL.raise += e * (0.12 + 0.1 * Math.sin(t * 0.0019 + 2));
    p.armL.bend += e * (0.35 + 0.15 * Math.sin(t * 0.0027 + 1));

    // cues
    for (const a of this.active) {
      const u = (t - a.start) / a.duration;
      if (u < 0 || u > 1) continue;
      const k = a.intensity;
      const w = env(u);
      switch (a.action) {
        case 'gesture.open':
          for (const arm of [p.armL, p.armR]) { arm.raise += 0.4 * k * w; arm.out += 0.55 * k * w; arm.bend += 0.35 * k * w; }
          break;
        case 'gesture.point':
          p.armR.raise += 0.85 * k * w; p.armR.out -= 0.05 * w; p.armR.bend = p.armR.bend * (1 - w) + 0.08 * w;
          break;
        case 'gesture.shrug':
          p.shoulderUp += k * w;
          for (const arm of [p.armL, p.armR]) { arm.bend += 0.8 * k * w; arm.out += 0.45 * k * w; arm.raise += 0.1 * k * w; }
          p.headRoll += 0.12 * k * w;
          break;
        case 'gesture.wave':
          p.armR.raise += 1.25 * k * w; p.armR.bend += 0.6 * w; p.armR.out += 0.4 * w;
          p.armR.wave = Math.sin(t * 0.012) * 0.55 * k * w;
          break;
        case 'pose.lean_forward': p.spinePitch += 0.16 * k * env(u, 0.12, 0.25); break;
        case 'pose.lean_back': p.spinePitch -= 0.1 * k * env(u, 0.12, 0.25); break;
        case 'pose.confident': p.spinePitch -= 0.04 * k * w; p.headPitch -= 0.06 * k * w; break;
        case 'pose.slump': p.spinePitch += 0.18 * k * w; p.headPitch += 0.15 * k * w; break;
        case 'reaction.laugh': p.headPitch -= 0.1 * w * Math.abs(Math.sin(t * 0.015)); break;
        default: break;
      }
      const face = FACE_MAP[a.action];
      if (face) {
        const fw = env(u, 0.1, 0.25) * k;
        for (const [key, v] of Object.entries(face)) {
          emotions[key as keyof Emotions] = Math.max(emotions[key as keyof Emotions], (v as number) * fw);
        }
      }
    }

    // gaze smoothing
    const g = Math.min(1, dt * 4);
    this.gazeYaw += (this.gazeTarget.yaw - this.gazeYaw) * g;
    this.gazePitch += (this.gazeTarget.pitch - this.gazePitch) * g;
    p.headYaw += this.gazeYaw * 0.7;
    p.headPitch += this.gazePitch * 0.7;

    // blink (own channel, wall clock)
    let blink = 0;
    if (this.blinkStart < 0 && wallMs >= this.nextBlink) this.blinkStart = wallMs;
    if (this.blinkStart >= 0) {
      const u = (wallMs - this.blinkStart) / 150;
      if (u >= 1) {
        this.blinkStart = -1;
        this.nextBlink = wallMs + 1800 + this.rand() * 3200;
      } else blink = Math.sin(u * Math.PI);
    }

    for (const arm of [p.armL, p.armR]) {
      arm.raise = Math.min(1.4, Math.max(0, arm.raise));
      arm.out = Math.min(1, Math.max(0, arm.out));
      arm.bend = Math.min(1, Math.max(0, arm.bend));
    }
    return { pose: p, emotions, blink };
  }
}
