/**
 * Seat-aware camera targeting (pure maths, no three.js).
 *
 *   resolveCameraCue(def, "close:seat2")            → { position, target, fov }
 *   "wide" / "<preset>"   preset of the set (seat-bound presets follow the seat)
 *   "close:<seat>"        head-and-shoulders, 1.05 m in front of the seat
 *   "single:<seat>"       medium single
 *   "reaction:<seat>"     tight 3/4 close (reaction shots)
 *   "two-shot:a+b"        both heads framed, camera on the open side
 *   "overhead" / "orbit"  preset if the set has one, else generic around the centre
 */
import type { CameraPresetDef, SeatAnchor, SetDefinition, Vec3 } from './types';
import { findSeat } from './registry';

export interface CameraShot { position: Vec3; target: Vec3; fov: number; cue: string; seats: string[] }

export const HEAD_HEIGHT: Record<SeatAnchor['pose'], number> = { seated: 1.3, standing: 1.6 };

const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k];
const len = (a: Vec3) => Math.hypot(a[0], a[1], a[2]);
const norm = (a: Vec3): Vec3 => { const l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

export function seatHead(s: SeatAnchor): Vec3 { return [s.position[0], s.position[1] + HEAD_HEIGHT[s.pose], s.position[2]]; }
export function seatForward(s: SeatAnchor): Vec3 { return [Math.sin(s.rotation), 0, Math.cos(s.rotation)]; }
/** Lateral axis (the character's left at yaw 0 is +X). */
export function seatSide(s: SeatAnchor): Vec3 { return [Math.cos(s.rotation), 0, -Math.sin(s.rotation)]; }

/** Seat-local offset → world (x = side, y = up, z = forward). */
export function seatLocal(s: SeatAnchor, o: Vec3, from: Vec3 = seatHead(s)): Vec3 {
  return add(add(add(from, scale(seatSide(s), o[0])), [0, o[1], 0]), scale(seatForward(s), o[2]));
}

export function presetShot(def: SetDefinition, name: string, p: CameraPresetDef, timeSec = 0): CameraShot {
  if (p.seat) {
    const s = findSeat(def, p.seat)!;
    return { position: seatLocal(s, p.position), target: seatLocal(s, p.target), fov: p.fov, cue: name, seats: [s.id] };
  }
  let position = p.position;
  if (p.orbit) {
    const dx = p.position[0] - p.target[0];
    const dz = p.position[2] - p.target[2];
    const r = Math.hypot(dx, dz);
    const a0 = Math.atan2(dx, dz) + timeSec * p.orbit;
    position = [p.target[0] + Math.sin(a0) * r, p.position[1], p.target[2] + Math.cos(a0) * r];
  }
  return { position, target: p.target, fov: p.fov, cue: name, seats: [] };
}

function centre(def: SetDefinition): Vec3 {
  const n = def.seats.length;
  const c = def.seats.reduce<Vec3>((acc, s) => add(acc, s.position), [0, 0, 0]);
  return [c[0] / n, 0.9, c[2] / n];
}

export class UnknownCameraCue extends Error {}

export function resolveCameraCue(def: SetDefinition, cue: string, timeSec = 0): CameraShot {
  const raw = cue.trim();
  const [kind, arg = ''] = raw.includes(':') ? [raw.slice(0, raw.indexOf(':')), raw.slice(raw.indexOf(':') + 1)] : [raw, ''];
  const preset = def.cameras[raw];
  if (preset) return presetShot(def, raw, preset, timeSec);

  const need = (ref: string): SeatAnchor => {
    const s = findSeat(def, ref);
    if (!s) throw new UnknownCameraCue(`set ${def.id}: no seat "${ref}" for cue "${cue}"`);
    return s;
  };

  switch (kind) {
    case 'wide': {
      const p = def.cameras[def.defaultCamera];
      if (p) return presetShot(def, 'wide', p, timeSec);
      const c = centre(def);
      return { position: [c[0], 2.4, c[2] + 6], target: c, fov: 44, cue: 'wide', seats: [] };
    }
    case 'close':
    case 'single':
    case 'reaction': {
      const s = need(arg);
      const off: Vec3 = kind === 'close' ? [0.12, 0.03, 1.05] : kind === 'reaction' ? [0.45, 0.02, 0.95] : [0.32, 0.05, 1.85];
      const fov = kind === 'single' ? 32 : 28;
      return { position: seatLocal(s, off), target: seatLocal(s, [0, kind === 'single' ? -0.12 : -0.02, 0]), fov, cue: raw, seats: [s.id] };
    }
    case 'two-shot': {
      const refs = arg.split('+').map((x) => x.trim()).filter(Boolean);
      if (refs.length !== 2) {
        const p = def.cameras['two-shot'];
        if (p && !arg) return presetShot(def, 'two-shot', p, timeSec);
        throw new UnknownCameraCue(`two-shot needs "a+b", got "${arg}"`);
      }
      const [a, b] = refs.map(need);
      const ha = seatHead(a), hb = seatHead(b);
      const mid = scale(add(ha, hb), 0.5);
      let dir = norm(add(seatForward(a), seatForward(b)));
      const sep = len([ha[0] - hb[0], 0, ha[2] - hb[2]]);
      if (len(add(seatForward(a), seatForward(b))) < 0.35) {
        // facing each other: shoot from the side of the a→b line nearer the main camera (+Z)
        const ab = norm([hb[0] - ha[0], 0, hb[2] - ha[2]]);
        dir = [ab[2], 0, -ab[0]];
        if (dir[2] < 0) dir = scale(dir, -1);
      }
      const dist = Math.max(2.1, sep * 1.25 + 1.0);
      return { position: add(add(mid, scale(dir, dist)), [0, 0.18, 0]), target: add(mid, [0, -0.1, 0]), fov: 34, cue: raw, seats: [a.id, b.id] };
    }
    case 'overhead': {
      const c = centre(def);
      return { position: [c[0], 5.2, c[2] + 0.3], target: [c[0], 0.78, c[2]], fov: 48, cue: 'overhead', seats: [] };
    }
    case 'orbit': {
      const c = centre(def);
      return presetShot(def, 'orbit', { position: [c[0], 2.4, c[2] + 4.2], target: c, fov: 42, orbit: 0.18 }, timeSec);
    }
    default:
      throw new UnknownCameraCue(`set ${def.id}: unknown camera cue "${cue}"`);
  }
}

/** True when the cue resolves on this set (used by control/room validation). */
export function isValidCameraCue(def: SetDefinition, cue: string): boolean {
  if (cue === 'auto') return true;
  try { resolveCameraCue(def, cue); return true; } catch { return false; }
}
