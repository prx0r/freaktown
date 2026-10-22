/**
 * Gaze — who each character looks at, moment to moment.
 *
 * Precedence (highest first), the same order the stage applies:
 *   1. scripted look      look / double-take / eye-roll / laugh-break (gaze.look events)
 *   2. life touches       idle glances (listeners, seeded per sketch), camera glance on the turn
 *   3. default            listeners watch the current speaker, else the last speaker;
 *                         the speaker addresses their scene partner (2-hander) or the room
 *
 * Plus non-gaze life: micro nods from listeners at sentence ends, blinks (the
 * stage's own channel). Everything here is pure + deterministic: the plan is a
 * list of timed looks the compiler turns into events; gazeTargetAt() answers
 * "who is X looking at at t" for tests and tools.
 */
import type { LookTarget, ReactionKind, SketchTiming } from './schema';
import type { ResolvedCast } from './identities';
import type { SketchLayout, SketchLine } from './timing';

export type LookSource = 'scripted' | 'double-take' | 'reaction' | 'idle' | 'camera-turn' | 'address';

export interface PlannedLook {
  role: string;
  /** Role id, or camera/audience/up/down/prop:<name>, or a world point. */
  target: LookTarget;
  start_ms: number;
  end_ms: number;
  snap: number;
  source: LookSource;
}

export interface PlannedNod { role: string; t_ms: number; ms: number }

export interface GazePlan { looks: PlannedLook[]; nods: PlannedNod[] }

function mulberry32(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export function seedOf(s: string): number { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

/** Reaction kinds that move the eyes (others are face/body only). */
const REACTION_LOOK: Partial<Record<ReactionKind, { target: LookTarget; frac: number; snap: number }>> = {
  'eye-roll': { target: 'up', frac: 0.45, snap: 1.6 },
  'laugh-break': { target: 'down', frac: 0.8, snap: 1.2 },
};

export function planGaze(layout: SketchLayout, cast: ResolvedCast[], T: SketchTiming, seed = 'sketch'): GazePlan {
  const rng = mulberry32(seedOf(seed));
  const looks: PlannedLook[] = [];
  const nods: PlannedNod[] = [];
  const roles = cast.map((c) => c.role);
  const byRole = new Map(cast.map((c) => [c.role, c]));

  // 1) scripted looks, double-takes, reaction looks
  for (const d of layout.directions) {
    const it = d.item;
    if (it.type === 'look') {
      if (it.double_take) {
        const g = T.double_take;
        const t0 = d.t_ms, t1 = t0 + g.glance_ms, t2 = t1 + g.away_ms;
        const away = speakerAt(layout, t1) && speakerAt(layout, t1)!.role !== it.who && speakerAt(layout, t1)!.role !== it.at ? speakerAt(layout, t1)!.role : 'down';
        looks.push({ role: it.who, target: it.at, start_ms: t0, end_ms: t1, snap: 1.4, source: 'double-take' });
        looks.push({ role: it.who, target: away, start_ms: t1, end_ms: t2, snap: 1.6, source: 'double-take' });
        looks.push({ role: it.who, target: it.at, start_ms: t2, end_ms: d.end_ms, snap: 3, source: 'double-take' });
      } else looks.push({ role: it.who, target: it.at, start_ms: d.t_ms, end_ms: d.end_ms, snap: 1, source: 'scripted' });
    } else if (it.type === 'react') {
      const rl = REACTION_LOOK[it.kind];
      if (rl) looks.push({ role: it.who, target: rl.target, start_ms: d.t_ms, end_ms: d.t_ms + Math.round((d.end_ms - d.t_ms) * rl.frac), snap: rl.snap, source: 'reaction' });
    }
  }
  const busy = (role: string, a: number, b: number) => looks.some((l) => l.role === role && l.start_ms < b && l.end_ms > a);

  // 2a) camera glance on the turn: the first free listener, right after the turn's first line
  if (T.camera_glance_on_turn) {
    for (const b of layout.beats.filter((x) => x.kind === 'turn')) {
      const line = layout.lines.find((l) => l.id === b.firstLine);
      if (!line) continue;
      if (layout.directions.some((d) => d.beatId === b.id && d.item.type === 'look' && d.item.at === 'camera')) continue;
      const who = roles.find((r) => r !== line.role && !busy(r, line.end_ms - 100, line.end_ms + 900));
      if (who) looks.push({ role: who, target: 'camera', start_ms: line.end_ms - 80, end_ms: line.end_ms + 820, snap: 1.8, source: 'camera-turn' });
    }
  }

  // 2b) idle glances + micro nods for listeners, per line (seeded)
  for (const l of layout.lines) {
    const listeners = roles.filter((r) => r !== l.role);
    for (const r of listeners) {
      const c = byRole.get(r)!;
      const len = l.end_ms - l.start_ms;
      if (len > 1600 && rng() < T.idle_glance_chance * c.restlessness) {
        const at = Math.round(l.start_ms + len * (0.3 + rng() * 0.35));
        const end = Math.min(l.end_ms - 250, at + T.idle_glance_ms);
        const others = listeners.filter((x) => x !== r);
        const target: LookTarget = others.length && rng() < 0.6 ? others[Math.floor(rng() * others.length)] : rng() < 0.5 ? 'down' : 'audience';
        if (end - at > 250 && !busy(r, at - 200, end + 200)) looks.push({ role: r, target, start_ms: at, end_ms: end, snap: 1, source: 'idle' });
      }
      if (rng() < T.nod_chance * (0.6 + 0.6 * c.energy)) {
        const sentEnd = l.words.find((w, i) => i > 2 && /[.!?,]["'”’)]*$/.test(w.word) && w.end_ms < l.end_ms - 300);
        const t = sentEnd ? sentEnd.end_ms + 60 : Math.round(l.start_ms + len * 0.6);
        if (!busy(r, t - 100, t + 800)) nods.push({ role: r, t_ms: t, ms: 800 });
      }
    }
  }
  // 3) speakers address their scene partner (the previous speaker, if recent) or the line's `to`;
  //    split around anything already planned for them so the scripted look wins and the address resumes.
  for (const l of layout.lines) {
    let to: LookTarget | null = l.to ?? null;
    if (!to) {
      const prevL = [...layout.lines].reverse().find((x) => x.start_ms < l.start_ms && x.role !== l.role);
      if (prevL && l.start_ms - prevL.end_ms < 6000) to = prevL.role;
    }
    if (!to || to === l.role) continue;
    let segs: Array<[number, number]> = [[l.start_ms, l.end_ms]];
    for (const o of looks.filter((x) => x.role === l.role && x.source !== 'address' && x.start_ms < l.end_ms && x.end_ms > l.start_ms)) {
      segs = segs.flatMap(([a, b]) => (o.end_ms <= a || o.start_ms >= b ? [[a, b] as [number, number]] : [[a, o.start_ms], [o.end_ms, b]] as Array<[number, number]>)).filter(([a, b]) => b - a > 200);
    }
    for (const [a, b] of segs) looks.push({ role: l.role, target: to, start_ms: a, end_ms: b, snap: 1, source: 'address' });
  }
  looks.sort((a, b) => a.start_ms - b.start_ms);
  nods.sort((a, b) => a.t_ms - b.t_ms);
  return { looks, nods };
}

export function speakerAt(layout: Pick<SketchLayout, 'lines'>, t: number): SketchLine | null {
  return layout.lines.find((l) => t >= l.start_ms && t < l.end_ms) ?? null;
}

function lastSpeakerBefore(layout: Pick<SketchLayout, 'lines'>, t: number, not?: string): SketchLine | null {
  let best: SketchLine | null = null;
  for (const l of layout.lines) if (l.start_ms <= t && l.role !== not) best = l;
  return best;
}

/**
 * Who/what `role` looks at at time t under the plan: a role id, camera, audience,
 * up, down, prop:<name>, a point, or null (addresses the room / camera).
 */
export function gazeTargetAt(plan: GazePlan, layout: Pick<SketchLayout, 'lines'>, role: string, t: number): LookTarget | null {
  const active = plan.looks.filter((l) => l.role === role && t >= l.start_ms && t < l.end_ms);
  if (active.length) {
    const rank = (s: LookSource) => (s === 'address' ? 0 : s === 'idle' || s === 'camera-turn' ? 1 : 2);
    return active.reduce((b, l) => (rank(l.source) > rank(b.source) || (rank(l.source) === rank(b.source) && l.start_ms >= b.start_ms) ? l : b)).target;
  }
  const sp = speakerAt(layout, t);
  if (sp && sp.role !== role) return sp.role;
  if (sp && sp.role === role) return null; // addresses the room / camera (the stage default)
  const last = lastSpeakerBefore(layout, t, role);
  return last ? last.role : null;
}
