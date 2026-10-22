/**
 * compileSketch — script → a timeline of plain set events (the same
 * TimedEvent shape the newsroom compiler emits), so any SetStage host plays
 * it: the /sketch page, the render CLI, a live room.
 *
 *   set.load {setId, cast}          cast resolved from the identity registry
 *   set.theme (news sets)           show style
 *   set.auto_director {on:false}    the sketch director owns the cameras
 *   dialogue.line                   per line (+ face.expression for the line's emotion)
 *   gaze.look                       scripted looks, double-takes, idle glances, addresses
 *   face.expression                 reactions, gestures, micro nods
 *   stage.move                      move-to(mark)
 *   overlay.headline                headline cues on the news wall
 *   <prop events>                   passthrough (poker.deal, poker.board, overlay.lower_third …)
 *   set.camera                      the director's shots
 *   overlay.blackout                the ending
 */
import type { CastMemberV1 } from '@funnier/contracts';
import { getShowStyle, themePayload, type CadenceProfile } from '@funnier/newsroom';
import { assertSketch, DEFAULT_SKETCH_TIMING, type ReactionKind, type GestureKind, type SketchScriptV1, type SketchTiming } from './schema';
import { resolveCast, toCastMembers, type ResolvedCast } from './identities';
import { layoutSketch, seatAt, type SketchLayout } from './timing';
import { planGaze, type GazePlan } from './gaze';
import { cameraTableFor, directSketch, SKETCH_CADENCE, type SketchShot } from './director';

export const SKETCH_TIMELINE_SCHEMA = 'funnier.sketch.timeline/v1' as const;

export interface TimedEvent { t_ms: number; type: string; payload: Record<string, unknown> }

export interface CompiledSketch {
  schema: typeof SKETCH_TIMELINE_SCHEMA;
  sketch_id: string;
  title: string;
  set: string;
  duration_ms: number;
  estimated: boolean;
  timing_source: 'measured' | 'estimated';
  wpm: number;
  cadence: { lmin_ms: number; lmax_ms: number };
  cast: Array<Pick<ResolvedCast, 'role' | 'seat' | 'identity' | 'name' | 'registered' | 'react_delay_ms'>>;
  events: TimedEvent[];
  shots: SketchShot[];
  lines: Array<{ id: string; role: string; seat: string; start_ms: number; end_ms: number; beat: string }>;
  laughs: SketchLayout['laughs'];
  gaze: GazePlan;
  warnings: string[];
}

export interface CompileSketchOptions { timing?: Partial<SketchTiming>; cadence?: CadenceProfile }

export const REACTION_ACTIONS: Record<ReactionKind, Array<{ action: string; k: number; frac?: number }>> = {
  smirk: [{ action: 'face.smug', k: 0.85 }],
  'eye-roll': [{ action: 'face.annoyed', k: 0.7 }, { action: 'gesture.shrug', k: 0.35, frac: 0.6 }],
  shock: [{ action: 'face.surprised', k: 1 }, { action: 'pose.lean_back', k: 0.9, frac: 0.7 }],
  deadpan: [{ action: 'face.deadpan', k: 1 }, { action: 'locomotion.freeze', k: 1 }],
  'laugh-break': [{ action: 'reaction.laugh', k: 1 }, { action: 'gesture.nod', k: 0.6, frac: 0.5 }],
};
export const GESTURE_ACTIONS: Record<GestureKind, string> = {
  point: 'gesture.point', shrug: 'gesture.shrug', open: 'gesture.open', wave: 'gesture.wave', nod: 'gesture.nod',
  'lean-in': 'pose.lean_forward', 'lean-back': 'pose.lean_back', slump: 'pose.slump', freeze: 'locomotion.freeze',
};

const ORDER: Record<string, number> = {
  'set.load': 0, 'set.theme': 1, 'set.auto_director': 2, 'overlay.headline': 4, 'overlay.lower_third': 5,
  'stage.move': 6, 'set.camera': 7, 'gaze.look': 8, 'face.expression': 9, 'dialogue.line': 10, 'overlay.blackout': 11,
};

export function sketchTiming(s: Pick<SketchScriptV1, 'timing'>, o: Partial<SketchTiming> = {}): SketchTiming {
  const t = { ...DEFAULT_SKETCH_TIMING, ...(s.timing ?? {}), ...o };
  t.double_take = { ...DEFAULT_SKETCH_TIMING.double_take, ...(s.timing?.double_take ?? {}), ...(o.double_take ?? {}) };
  return t;
}

export function compileSketch(script: SketchScriptV1, opts: CompileSketchOptions = {}): CompiledSketch {
  assertSketch(script);
  const T = sketchTiming(script, opts.timing);
  const C = opts.cadence ?? SKETCH_CADENCE;
  const cast = resolveCast(script, T);
  const layout = layoutSketch(script, cast, T);
  const gaze = planGaze(layout, cast, T, script.id);
  const cams = cameraTableFor(script.set);
  const dir = directSketch(layout, cams, C, script.id, cast.map((c) => c.role));
  const warnings: string[] = [...dir.warnings];
  if (layout.estimated) warnings.push(`timings ESTIMATED at ${T.wpm} wpm for ${layout.lines.filter((l) => l.estimated).length}/${layout.lines.length} lines (no measured words)`);
  for (const c of cast) if (!c.registered) warnings.push(`cast ${c.role}: "${c.identity}" is not a registered identity (inline name used)`);

  const ev: TimedEvent[] = [];
  const at = (t: number, type: string, payload: Record<string, unknown>) => ev.push({ t_ms: Math.max(0, Math.round(t)), type, payload });
  const seatOf = (role: string, t: number) => seatAt(layout, role, t);
  const members: CastMemberV1[] = toCastMembers(cast);
  const energy = new Map(cast.map((c) => [c.role, c.energy]));

  at(0, 'set.load', { setId: script.set, title: script.title, cast: members });
  if (script.set === 'news-studio') {
    try { at(0, 'set.theme', themePayload(getShowStyle(script.style ?? 'default-news')) as unknown as Record<string, unknown>); } catch { /* unknown style: house look */ }
  }
  at(0, 'set.auto_director', { on: false });

  for (const l of layout.lines) {
    at(l.start_ms, 'dialogue.line', { seat: l.seat, text: l.text, duration_ms: l.end_ms - l.start_ms, line_id: l.id, emotion: l.emotion, words: l.relWords });
    if (l.emotion) at(l.start_ms, 'face.expression', { seat: l.seat, emotion: l.emotion, intensity: 0.6, duration_ms: l.end_ms - l.start_ms });
  }

  for (const d of layout.directions) {
    const it = d.item;
    const k = d.role ? 0.6 + 0.5 * (energy.get(d.role) ?? 0.6) : 1;
    switch (it.type) {
      case 'react': {
        for (const a of REACTION_ACTIONS[it.kind]) {
          const dur = Math.round((d.end_ms - d.t_ms) * (a.frac ?? 1));
          at(d.t_ms, 'face.expression', { seat: seatOf(d.role!, d.t_ms), action: a.action, intensity: Math.min(1, a.k * k), duration_ms: dur });
        }
        break;
      }
      case 'gesture':
        at(d.t_ms, 'face.expression', { seat: seatOf(d.role!, d.t_ms), action: GESTURE_ACTIONS[it.kind], intensity: it.intensity ?? Math.min(1, 0.8 * k), duration_ms: d.end_ms - d.t_ms });
        break;
      case 'look':
        if (it.double_take) at(d.t_ms + T.double_take.glance_ms + T.double_take.away_ms, 'face.expression', { seat: seatOf(d.role!, d.t_ms), action: 'face.surprised', intensity: 0.9, duration_ms: 1200 });
        break;
      case 'move':
        at(d.t_ms, 'stage.move', { seat: d.seat, to: it.to, duration_ms: d.end_ms - d.t_ms });
        break;
      case 'headline':
        at(d.t_ms, 'overlay.headline', { text: it.text, kicker: it.kicker, layout: it.layout ?? 'headline', ...(it.body ? { body: it.body } : {}), ...(it.figure ? { figure: it.figure } : {}) });
        break;
      case 'prop':
        at(d.t_ms, it.event, it.payload);
        break;
      case 'blackout':
        at(d.t_ms, 'overlay.blackout', { on: true, fade_ms: d.end_ms - d.t_ms });
        break;
      default:
        break; // pause / hold_for_laugh / camera / button: timing + director only
    }
  }

  // gaze plan → gaze.look (seat resolved at the look's start; role targets → that role's seat then)
  for (const g of gaze.looks) {
    const target = typeof g.target === 'string' && cast.some((c) => c.role === g.target) ? seatOf(g.target, g.start_ms) : g.target;
    at(g.start_ms, 'gaze.look', { seat: seatOf(g.role, g.start_ms), target, duration_ms: g.end_ms - g.start_ms, ...(g.snap !== 1 ? { snap: g.snap } : {}), source: g.source });
  }
  for (const n of gaze.nods) at(n.t_ms, 'face.expression', { seat: seatOf(n.role, n.t_ms), action: 'gesture.nod', intensity: 0.4, duration_ms: n.ms });

  for (const s of dir.shots) {
    const payload: Record<string, unknown> = { cue: s.cue, source: 'auto_director' };
    if (s.creep) { payload.creep = s.creep; payload.creep_ms = s.creep_ms; }
    at(s.start_ms, 'set.camera', payload);
  }

  ev.sort((a, b) => a.t_ms - b.t_ms || (ORDER[a.type] ?? 5) - (ORDER[b.type] ?? 5));
  return {
    schema: SKETCH_TIMELINE_SCHEMA,
    sketch_id: script.id,
    title: script.title,
    set: script.set,
    duration_ms: layout.duration_ms,
    estimated: layout.estimated,
    timing_source: layout.estimated ? 'estimated' : 'measured',
    wpm: T.wpm,
    cadence: { lmin_ms: C.lmin_ms, lmax_ms: C.lmax_ms },
    cast: cast.map((c) => ({ role: c.role, seat: c.seat, identity: c.identity, name: c.name, registered: c.registered, react_delay_ms: c.react_delay_ms })),
    events: ev,
    shots: dir.shots,
    lines: layout.lines.map((l) => ({ id: l.id, role: l.role, seat: l.seat, start_ms: l.start_ms, end_ms: l.end_ms, beat: l.beatId })),
    laughs: layout.laughs,
    gaze,
    warnings,
  };
}

/** Events due in (from, to] — for players that step a clock. */
export function sketchEventsBetween(c: CompiledSketch, fromMs: number, toMs: number): TimedEvent[] {
  return c.events.filter((e) => e.t_ms > fromMs && e.t_ms <= toMs);
}
