/**
 * Timing — lays a sketch script on one clock.
 *
 *   lines            sequential; measured words win, else an estimate at timing.wpm
 *                    (the newsroom estimator: pauses carved after commas / sentence ends)
 *   pause            owns time (silence at the cursor)
 *   hold_for_laugh   owns time AND opens a laugh window after the previous line:
 *                    the director may cut at its start (to a reaction) but never inside it
 *   move (wait)      owns its walk time; without wait it overlaps what follows
 *   everything else  fires at the cursor (or inside the previous line with during:"prev")
 *                    and overlaps the next line
 *
 * Reactions fire after the reacting identity's own latency (motion-style
 * reaction_delay_ms). Seats are tracked through moves so later lines and
 * camera cues name the mark the character is standing on.
 */
import { estimateWords } from '@funnier/newsroom';
import type { Anchor, Beat, BeatKind, DirectionItem, LineItem, SketchScriptV1, SketchTiming } from './schema';
import type { ResolvedCast } from './identities';

export interface ClockWord { word: string; start_ms: number; end_ms: number }

export interface SketchLine {
  id: string;
  index: number;
  role: string;
  /** Seat/mark the speaker stands on at line start. */
  seat: string;
  text: string;
  emotion?: string;
  to?: string;
  start_ms: number;
  end_ms: number;
  words: ClockWord[];
  relWords: Array<{ word: string; start_ms: number; end_ms: number }>;
  estimated: boolean;
  beatId: string;
  beatKind: BeatKind;
  sceneId: string;
}

export interface SketchDirection {
  item: DirectionItem;
  t_ms: number;
  end_ms: number;
  role?: string;
  seat?: string;
  beatId: string;
  beatKind: BeatKind;
  /** Line this direction is attached to (during:"prev") or follows. */
  afterLine: string | null;
}

export interface LaughWindow { start_ms: number; end_ms: number; afterLine: string; beatId: string }

export interface TimedBeat { id: string; kind: BeatKind; sceneId: string; start_ms: number; end_ms: number; firstLine: string | null }

export interface SketchLayout {
  lines: SketchLine[];
  directions: SketchDirection[];
  laughs: LaughWindow[];
  /** Pauses (silences that own time). */
  pauses: Array<{ start_ms: number; end_ms: number }>;
  beats: TimedBeat[];
  duration_ms: number;
  estimated: boolean;
  /** Seat history per role: [{t, seat}] ascending. */
  seats: Record<string, Array<{ t: number; seat: string }>>;
  blackout: { t_ms: number; fade_ms: number } | null;
}

export function seatAt(layout: Pick<SketchLayout, 'seats'>, role: string, t: number): string {
  const h = layout.seats[role];
  if (!h?.length) return role;
  let s = h[0].seat;
  for (const x of h) if (x.t <= t) s = x.seat; else break;
  return s;
}

const directionMs = (d: DirectionItem, T: SketchTiming): number => {
  switch (d.type) {
    case 'look': return d.double_take ? T.double_take.glance_ms + T.double_take.away_ms + (d.ms ?? T.double_take.hold_ms) : d.ms ?? T.look_ms;
    case 'react': return d.ms ?? T.react_ms;
    case 'gesture': return d.ms ?? 1300;
    case 'move': return d.ms ?? T.move_ms;
    case 'camera': return d.hold_ms ?? 0;
    case 'blackout': return d.fade_ms ?? 900;
    default: return 0;
  }
};

export function layoutSketch(s: SketchScriptV1, cast: ResolvedCast[], T: SketchTiming): SketchLayout {
  const byRole = new Map(cast.map((c) => [c.role, c]));
  const seats: SketchLayout['seats'] = Object.fromEntries(cast.map((c) => [c.role, [{ t: 0, seat: c.seat }]]));
  const lines: SketchLine[] = [];
  const directions: SketchDirection[] = [];
  const laughs: LaughWindow[] = [];
  const pauses: SketchLayout['pauses'] = [];
  const beats: TimedBeat[] = [];
  let blackout: SketchLayout['blackout'] = null;
  let cursor = 900; // a breath of establishing wide before the first line
  let prev: SketchLine | null = null;
  let estimated = false;
  let first = true;

  const anchorTime = (a: Anchor): number => {
    if (a.during !== 'prev' || !prev) return cursor;
    if (typeof a.at_word === 'number' && prev.words.length) return prev.words[Math.max(0, Math.min(prev.words.length - 1, a.at_word))].start_ms;
    if (typeof a.from_end_ms === 'number') return Math.max(prev.start_ms, prev.end_ms - a.from_end_ms);
    return Math.min(prev.end_ms, prev.start_ms + (a.offset_ms ?? 0));
  };

  for (const sc of s.scenes) {
    for (const b of sc.beats as Beat[]) {
      if (!first) cursor += T.beat_gap_ms;
      first = false;
      const tb: TimedBeat = { id: b.id, kind: b.kind, sceneId: sc.id, start_ms: cursor, end_ms: cursor, firstLine: null };
      beats.push(tb);
      for (const it of b.items) {
        if (it.type === 'line') {
          const li = it as LineItem;
          const measured = li.words?.length ? li.words : null;
          const rel = measured ?? estimateWords(li.text, T.wpm);
          if (!measured) estimated = true;
          const start = cursor;
          const dur = (rel.length ? rel[rel.length - 1].end_ms : 400) + 140;
          const line: SketchLine = {
            id: li.id ?? `${b.id}#${lines.length}`, index: lines.length, role: li.who, seat: seatAt({ seats }, li.who, start),
            text: li.text, emotion: li.emotion, to: li.to, start_ms: start, end_ms: start + dur,
            words: rel.map((w) => ({ word: w.word, start_ms: start + w.start_ms, end_ms: start + w.end_ms })), relWords: rel.map((w) => ({ ...w })),
            estimated: !measured, beatId: b.id, beatKind: b.kind, sceneId: sc.id,
          };
          lines.push(line);
          tb.firstLine ??= line.id;
          prev = line;
          cursor = line.end_ms + T.line_gap_ms;
          continue;
        }
        const d = it as DirectionItem;
        if (d.type === 'pause') { pauses.push({ start_ms: cursor, end_ms: cursor + d.ms }); cursor += d.ms; continue; }
        if (d.type === 'hold_for_laugh') {
          const ms = d.ms ?? T.laugh_hold_ms;
          const st = prev ? prev.end_ms : cursor;
          laughs.push({ start_ms: st, end_ms: st + ms, afterLine: prev?.id ?? '', beatId: b.id });
          directions.push({ item: d, t_ms: st, end_ms: st + ms, beatId: b.id, beatKind: b.kind, afterLine: prev?.id ?? null });
          cursor = Math.max(cursor, st + ms + T.line_gap_ms);
          continue;
        }
        const role = 'who' in d ? d.who : undefined;
        let t = anchorTime(d as Anchor);
        if (d.type === 'react' && role) t += byRole.get(role)?.react_delay_ms ?? T.react_delay_ms;
        if (d.type === 'blackout') t = (prev ? Math.max(prev.end_ms, cursor - T.line_gap_ms) : cursor) + (d.delay_ms ?? 250);
        const dur = directionMs(d, T);
        const dir: SketchDirection = { item: d, t_ms: Math.round(t), end_ms: Math.round(t + dur), role, seat: role ? seatAt({ seats }, role, t) : undefined, beatId: b.id, beatKind: b.kind, afterLine: prev?.id ?? null };
        directions.push(dir);
        if (d.type === 'move' && role) {
          seats[role].push({ t: dir.t_ms, seat: d.to }); // the stage re-keys the character to the mark when the walk starts
          if (d.wait) cursor = Math.max(cursor, dir.end_ms + T.line_gap_ms);
        }
        if (d.type === 'blackout') { blackout = { t_ms: dir.t_ms, fade_ms: dur }; cursor = Math.max(cursor, dir.end_ms + 600); }
      }
      tb.end_ms = Math.max(cursor, ...directions.filter((d) => d.beatId === b.id).map((d) => d.end_ms));
    }
  }
  const duration = Math.round(Math.max(cursor + 400, ...directions.map((d) => d.end_ms + 300), ...laughs.map((l) => l.end_ms + 300)));
  return { lines, directions, laughs, pauses, beats, duration_ms: duration, estimated, seats, blackout };
}
