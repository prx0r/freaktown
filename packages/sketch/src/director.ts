/**
 * Sketch director — the newsroom's BBC-R&D "Ed" director, re-grammared for
 * scripted comedy.
 *
 * Timing is Ed's (shared helpers from @funnier/newsroom): cuts laid evenly at
 * (lmax+lmin)/2 inside each free interval and snapped toward the nearest
 * speech boundary by ≤ (lmax−lmin)/4; never inside a word or a line's tail.
 * Cadence profile `sketch`: lmin 1.8 s, lmax 5 s.
 *
 * Grammar (fixed shots, laid first):
 *   open          establishing wide
 *   game reveal   wide on the first line of the `game` beat (the audience sees the whole board)
 *   look/react    cut to the looker/reactor (reaction close-up) when the direction lands
 *   headline/prop the wall / board shot when a card or board change lands
 *   laugh hold    after the punch the picture HOLDS: a cut may land at the hold's start
 *                 (to the reaction), never inside it
 *   button        close on whoever delivers the button; blackout → no cuts after
 *   camera items  manual overrides win
 * Free intervals: Ed sequencing over dialogue coverage — single on the speaker,
 * over-the-shoulder from the listener onto the speaker, two-shot of the pair,
 * occasional wide — speaker always in frame, variety + recency penalties.
 *
 * Pure + deterministic (seeded): same script → same shots.
 */
import { isLegalCut, type CadenceProfile, type TimedLine } from '@funnier/newsroom';
import { DEFAULT_NEWS } from '@funnier/newsroom';
import { seedOf } from './gaze';
import { seatAt, type SketchLayout, type SketchLine } from './timing';

/** The `sketch` cadence profile (newsroom CadenceProfile shape; lmin 1.8 s, lmax 5 s). */
export const SKETCH_CADENCE: CadenceProfile = {
  ...DEFAULT_NEWS.cadence,
  lmin_ms: 1800,
  lmax_ms: 5000,
  wpm: 165,
  line_gap_ms: 260,
  story_gap_ms: 380,
  tail_hold_ms: 140,
  move_ms: 0,
  creep: 0.04,
  establish_every: 7,
  reaction_chance: 0,
  recent_window: 3,
};

export type SketchShotClass = 'wide' | 'two' | 'ots' | 'one' | 'reaction' | 'prop';
export type SketchShotReason = 'open' | 'game-reveal' | 'look' | 'reaction' | 'double-take' | 'headline' | 'prop' | 'laugh-hold' | 'button' | 'manual' | 'ed' | 'establish' | 'blackout';

export interface SketchShot {
  start_ms: number;
  end_ms: number;
  cue: string;
  cls: SketchShotClass;
  reason: SketchShotReason;
  /** Seats visible (speaker-in-shot checks). For OTS the near shoulder seat is listed second. */
  seats: string[];
  /** Role this reaction shot belongs to (look/react directions). */
  reactRole?: string;
  creep?: number;
  creep_ms?: number;
  forced?: boolean;
}

export interface SketchCameraTable {
  wide: string;
  /** Cue for a wall/board shot when the set has one (news: wall-ots, poker: board). */
  prop?: string;
  /** Single on a seat (medium) and tighter close. */
  single: (seat: string) => string;
  close: (seat: string) => string;
  reaction: (seat: string) => string;
  two: (a: string, b: string) => string;
  ots: (from: string, to: string) => string;
}

export function cameraTableFor(setId: string): SketchCameraTable {
  const base: SketchCameraTable = {
    wide: 'wide',
    single: (s) => `single:${s}`,
    close: (s) => `close:${s}`,
    reaction: (s) => `reaction:${s}`,
    two: (a, b) => `two-shot:${a}+${b}`,
    ots: (a, b) => `ots:${a}>${b}`,
  };
  if (setId === 'news-studio') return { ...base, prop: 'wall-ots' };
  if (setId === 'poker-table') return { ...base, prop: 'board' };
  return base;
}

export interface SketchDirectorResult { shots: SketchShot[]; warnings: string[] }

interface CutPoint { t: number; strength: number }
interface Fixed { start: number; cue: string; cls: SketchShotClass; reason: SketchShotReason; seats: string[]; reactRole?: string; minEnd?: number; rank: number }

function mulberry32(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

const RANK: Record<SketchShotReason, number> = { open: 9, blackout: 9, manual: 8, 'game-reveal': 7, 'double-take': 7, 'laugh-hold': 6, reaction: 6, look: 5, headline: 6, prop: 5, button: 6, establish: 1, ed: 1 };

export function directSketch(layout: SketchLayout, cams: SketchCameraTable, C: CadenceProfile = SKETCH_CADENCE, seed = 'sketch', roles: string[] = []): SketchDirectorResult {
  const warnings: string[] = [];
  const rng = mulberry32(seedOf(seed));
  const L = layout.lines;
  const asNews = L as unknown as TimedLine[]; // isLegalCut reads start/end/words only
  const lmin = C.lmin_ms, lmax = C.lmax_ms;
  const end = layout.duration_ms;
  const allRoles = roles.length ? roles : [...new Set(L.map((l) => l.role))];
  const seat = (role: string, t: number) => seatAt(layout, role, t);
  const inLaugh = (t: number) => layout.laughs.some((w) => t > w.start_ms + 1 && t < w.end_ms - 1);
  const legal = (t: number) => isLegalCut(t, asNews, C.tail_hold_ms) && !inLaugh(t) && (!layout.blackout || t <= layout.blackout.t_ms);
  const speakingIn = (a: number, b: number) => L.filter((l) => l.start_ms < b && l.end_ms > a);

  // cut points: line ends (speaker changes strongest), sentence ends, commas, word gaps, pause/laugh starts
  const pts: CutPoint[] = [];
  L.forEach((l, i) => {
    const next = L[i + 1];
    const gapEnd = next ? next.start_ms : end;
    pts.push({ t: Math.round(Math.min(gapEnd, l.end_ms + Math.min(220, (gapEnd - l.end_ms) / 2))), strength: next && next.role !== l.role ? 3 : 2.5 });
    for (let k = 0; k < l.words.length - 1; k++) {
      const w = l.words[k], nx = l.words[k + 1];
      const t = Math.round((w.end_ms + nx.start_ms) / 2);
      pts.push({ t, strength: /[.!?]["'”’)]*$/.test(w.word) ? 2 : /[,;:—–]["'”’)]*$/.test(w.word) ? 1 : 0 });
    }
  });
  for (const w of layout.laughs) pts.push({ t: w.start_ms, strength: 3 }, { t: w.end_ms, strength: 2.5 });
  const P = pts.filter((c) => legal(c.t)).sort((a, b) => a.t - b.t);
  /** Nearest legal instant to x (prefer ≥ x within `ahead`, else ≤ x within `back`). */
  const legalNear = (x: number, ahead = 450, back = 450): number => {
    if (legal(x)) return x;
    const fwd = P.find((c) => c.t >= x && c.t <= x + ahead);
    if (fwd) return fwd.t;
    const bwd = [...P].reverse().find((c) => c.t <= x && c.t >= x - back);
    return bwd ? bwd.t : NaN;
  };

  const partnerOf = (l: SketchLine): string | null => {
    if (l.to && l.to !== 'camera' && l.to !== 'audience') return l.to;
    const prev = [...L].reverse().find((x) => x.start_ms < l.start_ms && x.role !== l.role);
    if (prev) return prev.role;
    const next = L.find((x) => x.start_ms > l.start_ms && x.role !== l.role);
    return next ? next.role : allRoles.find((r) => r !== l.role) ?? null;
  };

  // 1) grammar ────────────────────────────────────────────────────────
  const fixed: Fixed[] = [{ start: 0, cue: cams.wide, cls: 'wide', reason: 'open', seats: allRoles.map((r) => seat(r, 0)), rank: RANK.open }];
  const gameBeat = layout.beats.find((b) => b.kind === 'game');
  const gameLine = gameBeat ? L.find((l) => l.id === gameBeat.firstLine) : undefined;
  if (gameLine) {
    const t = legalNear(gameLine.start_ms - 60, 200, 600);
    if (Number.isFinite(t)) fixed.push({ start: t, cue: cams.wide, cls: 'wide', reason: 'game-reveal', seats: allRoles.map((r) => seat(r, t)), rank: RANK['game-reveal'] });
  }
  for (const d of layout.directions) {
    const it = d.item;
    if ((it.type === 'look' || it.type === 'react') && d.role) {
      // a look AT the camera plays on the looker's close-up: the turn to the lens is the joke.
      // A reaction that lands in (or just before) a laugh hold takes the hold's start: cut on the laugh.
      const hold = layout.laughs.find((w) => d.t_ms >= w.start_ms - 400 && d.t_ms < w.end_ms);
      const t = hold && legal(hold.start_ms) ? hold.start_ms : legalNear(d.t_ms, 500, 350);
      if (!Number.isFinite(t)) { warnings.push(`no legal cut for ${it.type} by ${d.role} @${d.t_ms}ms (mid-word); kept the running shot`); continue; }
      const st = seat(d.role, t);
      const reason: SketchShotReason = it.type === 'react' ? 'reaction' : it.double_take ? 'double-take' : 'look';
      fixed.push({ start: t, cue: it.type === 'look' && it.at === 'camera' ? cams.close(st) : cams.reaction(st), cls: 'reaction', reason, seats: [st], reactRole: d.role, minEnd: Math.max(t + lmin, d.end_ms), rank: RANK[reason] });
    } else if (it.type === 'headline' && cams.prop) {
      const t = legalNear(d.t_ms, 600, 300);
      if (Number.isFinite(t)) fixed.push({ start: t, cue: cams.prop, cls: 'prop', reason: 'headline', seats: allRoles.map((r) => seat(r, t)), minEnd: t + lmin, rank: RANK.headline });
    } else if (it.type === 'prop' && cams.prop && /board|deal|showdown/.test(it.event)) {
      const t = legalNear(d.t_ms, 600, 300);
      if (Number.isFinite(t)) fixed.push({ start: t, cue: cams.prop, cls: 'prop', reason: 'prop', seats: allRoles.map((r) => seat(r, t)), minEnd: t + lmin, rank: RANK.prop });
    } else if (it.type === 'camera') {
      const t = legalNear(d.t_ms, 300, 300);
      const cue = it.cue.replace(/(^|[:>+])([a-z][\w-]*)/g, (m, p, r) => (allRoles.includes(r) ? p + seat(r, d.t_ms) : m));
      if (Number.isFinite(t)) fixed.push({ start: t, cue, cls: /^(close|single)/.test(cue) ? 'one' : /^two/.test(cue) ? 'two' : /^ots/.test(cue) ? 'ots' : cue === cams.wide ? 'wide' : 'prop', reason: 'manual', seats: allRoles.map((r) => seat(r, t)).filter((s) => cue.includes(s) || cue === cams.wide), minEnd: t + Math.max(lmin, it.hold_ms ?? 0), rank: RANK.manual });
    } else if (it.type === 'button') {
      const next = L.find((l) => l.start_ms >= d.t_ms - 1);
      const who = next ?? [...L].reverse().find((l) => l.start_ms <= d.t_ms);
      if (who) {
        const t = legalNear(Math.max(d.t_ms, who.start_ms) - 80, 300, 500);
        // the button holds to the end (through the blackout): no cut after it
        if (Number.isFinite(t)) fixed.push({ start: t, cue: cams.close(who.seat), cls: 'one', reason: 'button', seats: [who.seat], minEnd: end, rank: RANK.button });
      }
    }
  }
  // laugh holds: if a reaction lands inside the hold, it takes the hold's start; else the running shot holds
  for (const w of layout.laughs) {
    const inside = fixed.filter((f) => f.cls === 'reaction' && f.start > w.start_ms && f.start < w.end_ms);
    for (const f of inside) {
      f.start = legal(w.start_ms) ? w.start_ms : f.start; f.reason = f.reason === 'reaction' ? 'reaction' : f.reason; f.minEnd = Math.max(f.minEnd ?? 0, w.end_ms);
    }
    // anything else starting strictly inside the hold moves to its end
    for (const f of fixed) if (f.start > w.start_ms + 1 && f.start < w.end_ms - 1 && !inside.includes(f)) f.start = w.end_ms;
  }
  // the game-reveal wide waits for a reaction shot that is already up (then reveals), if the line is long enough
  const reveal = fixed.find((f) => f.reason === 'game-reveal');
  if (reveal && gameLine) {
    const r = fixed.find((f) => f !== reveal && f.cls === 'reaction' && f.start <= reveal.start && (f.minEnd ?? f.start + lmin) > reveal.start);
    if (r) {
      const after = legalNear(Math.max(r.start + lmin, r.minEnd ?? 0), 900, 0);
      reveal.start = Number.isFinite(after) && after <= gameLine.end_ms - lmin * 0.5 ? after : -1;
    }
  }
  if (layout.blackout) for (const f of fixed) if (f.start > layout.blackout.t_ms) f.start = -1;
  const F = fixed.filter((f) => f.start >= 0).sort((a, b) => a.start - b.start || b.rank - a.rank);
  // collapse collisions (< lmin apart): keep the higher-ranked beat; the open never moves
  for (let i = F.length - 2; i >= 0; i--) {
    const a = F[i], b = F[i + 1];
    if (b.start - a.start >= lmin) continue;
    if (a.reason === 'open') { if (b.rank >= 6 && b.start >= 900) { a.minEnd = b.start; continue; } F.splice(i + 1, 1); continue; }
    if (b.rank > a.rank) F.splice(i, 1); else F.splice(i + 1, 1);
  }

  // 2) Ed sequencing in the free time after each fixed shot ─────────────
  const shots: SketchShot[] = [];
  const avg = (lmax + lmin) / 2, pull = (lmax - lmin) / 4;
  const snap = (x: number, lo: number, hi: number): number => {
    const win = P.filter((c) => c.t >= Math.max(lo, x - pull) && c.t <= Math.min(hi, x + pull));
    for (const minS of [2.5, 2, 1, 0]) {
      const c = win.filter((q) => q.strength >= minS);
      if (c.length) return c.reduce((b, q) => (Math.abs(q.t - x) < Math.abs(b.t - x) ? q : b)).t;
    }
    return NaN;
  };
  for (let i = 0; i < F.length; i++) {
    const f = F[i];
    const stop = i + 1 < F.length ? F[i + 1].start : end;
    const holdEnd = Math.min(stop, Math.max(f.start + lmin, f.minEnd ?? 0));
    const cuts: number[] = [];
    let prev = f.start;
    // the fixed shot holds lmin (or its own minimum); free time after it gets Ed cuts
    const firstCut = f.reason === 'open' ? Math.min(stop, Math.max(f.minEnd ?? 0, firstLineStart(L) + 600, f.start + lmin)) : holdEnd;
    if (stop - firstCut >= lmin && firstCut > f.start) {
      const c0 = legal(firstCut) ? firstCut : snap(firstCut, f.start + lmin, stop - lmin);
      if (Number.isFinite(c0) && c0 - prev >= lmin && stop - c0 >= lmin) { cuts.push(c0); prev = c0; }
      const free = stop - prev;
      const n = Math.max(1, Math.round(free / avg));
      const step = free / n;
      const base = prev;
      for (let k = 1; k < n; k++) {
        const c = snap(base + k * step, prev + lmin, stop - lmin);
        if (Number.isFinite(c) && c - prev >= lmin && stop - c >= lmin) { cuts.push(c); prev = c; }
      }
    }
    const bounds = [f.start, ...cuts, stop];
    for (let k = 0; k < bounds.length - 1; k++) {
      const s = bounds[k], e = bounds[k + 1];
      if (e <= s) continue;
      if (k === 0) shots.push({ start_ms: s, end_ms: e, cue: f.cue, cls: f.cls, reason: f.reason, seats: f.seats, reactRole: f.reactRole });
      else shots.push({ ...choose(s, e), start_ms: s, end_ms: e });
    }
  }

  function choose(s: number, e: number, history: SketchShot[] = shots): Omit<SketchShot, 'start_ms' | 'end_ms'> {
    const sp = speakingIn(s, e);
    const speakers = [...new Set(sp.map((l) => l.role))];
    const prev = history[history.length - 1];
    const recent = history.slice(-C.recent_window);
    const sinceWide = (() => { let n = 0; for (let i = history.length - 1; i >= 0 && history[i].cls !== 'wide'; i--) n++; return n; })();
    type Cand = { cue: string; cls: SketchShotClass; seats: string[]; score: number; reason: SketchShotReason };
    const cands: Cand[] = [];
    const wideSeats = allRoles.map((r) => seat(r, s));
    cands.push({ cue: cams.wide, cls: 'wide', seats: wideSeats, score: speakers.length ? 0.4 : 2.6, reason: 'ed' });
    if (speakers.length === 1) {
      const line = sp.find((l) => l.role === speakers[0])!;
      const sSeat = seat(line.role, s);
      const partner = partnerOf(line);
      cands.push({ cue: cams.single(sSeat), cls: 'one', seats: [sSeat], score: 3, reason: 'ed' });
      if (e - s <= lmax && line.end_ms - line.start_ms > 2600) cands.push({ cue: cams.close(sSeat), cls: 'one', seats: [sSeat], score: 2.2, reason: 'ed' });
      // a line addressed to camera/audience plays frontal (single/close/wide), not over a shoulder
      if (partner && line.to !== 'camera' && line.to !== 'audience') {
        const pSeat = seat(partner, s);
        cands.push({ cue: cams.ots(pSeat, sSeat), cls: 'ots', seats: [sSeat, pSeat], score: 2.9, reason: 'ed' });
        cands.push({ cue: cams.two(sSeat, pSeat), cls: 'two', seats: [sSeat, pSeat], score: 2.1, reason: 'ed' });
      }
    } else if (speakers.length === 2) {
      const [a, b] = speakers.map((r) => seat(r, s));
      cands.push({ cue: cams.two(a, b), cls: 'two', seats: [a, b], score: 3, reason: 'ed' });
    } else if (speakers.length === 0 && allRoles.length >= 2) {
      const [a, b] = allRoles.slice(0, 2).map((r) => seat(r, s));
      cands.push({ cue: cams.two(a, b), cls: 'two', seats: [a, b], score: 2, reason: 'ed' });
    }
    let best: Cand | null = null;
    for (const c of cands) {
      if (!speakers.every((r) => c.seats.includes(seat(r, s)))) continue; // hard: speakers in frame
      let score = c.score;
      if (prev && prev.cls === c.cls) score -= 2.2;
      if (prev && prev.cue === c.cue) score -= 6;
      recent.forEach((r, i) => { if (r.cue === c.cue) score -= 2.5 * ((i + 1) / recent.length); });
      if (c.cls === 'wide' && C.establish_every && sinceWide >= C.establish_every) { score += 5; c.reason = 'establish'; }
      score += rng() * 0.3;
      if (!best || score > best.score) best = c;
    }
    const b = best ?? cands[0];
    return { cue: b.cue, cls: b.cls, seats: b.seats, reason: b.reason };
  }

  // 3) repair: speakers in frame, except reaction shots tied to a direction of that role
  const fits = (sh: SketchShot): boolean => {
    const sp = speakingIn(sh.start_ms, sh.end_ms);
    if (sh.cls === 'reaction' || sh.reason === 'manual') return true;
    return sp.every((l) => sh.seats.includes(seat(l.role, Math.max(sh.start_ms, l.start_ms))));
  };
  const out: SketchShot[] = [];
  for (const sh of shots) {
    if (fits(sh)) { out.push(sh); continue; }
    // split at a speaker change if both halves hold ≥ lmin
    const ch = P.filter((q) => q.strength >= 2.5 && q.t >= sh.start_ms + lmin && q.t <= sh.end_ms - lmin);
    const first = ch.find((q) => fits({ ...sh, end_ms: q.t }));
    if (first && sh.reason !== 'open') {
      out.push({ ...sh, end_ms: first.t });
      out.push({ ...choose(first.t, sh.end_ms, out), start_ms: first.t, end_ms: sh.end_ms });
      continue;
    }
    // else widen: two-shot of everyone speaking, or the wide
    const sp = [...new Set(speakingIn(sh.start_ms, sh.end_ms).map((l) => seat(l.role, sh.start_ms)))];
    if (sp.length === 2) out.push({ ...sh, cue: cams.two(sp[0], sp[1]), cls: 'two', seats: sp });
    else out.push({ ...sh, cue: cams.wide, cls: 'wide', seats: allRoles.map((r) => seat(r, sh.start_ms)) });
  }
  // merge identical neighbours (an invisible cut) when the result stays within lmax
  for (let i = out.length - 1; i > 0; i--) {
    const a = out[i - 1], b = out[i];
    if (a.cue === b.cue && b.end_ms - a.start_ms <= lmax) { a.end_ms = b.end_ms; out.splice(i, 1); }
  }
  // slow creep on singles/reactions; flag shots outside the bounds (never hide)
  for (const s of out) {
    const d = s.end_ms - s.start_ms;
    if ((s.cls === 'one' || s.cls === 'reaction') && d >= lmin) { s.creep = C.creep; s.creep_ms = d; }
    const silent = speakingIn(s.start_ms, s.end_ms).length === 0;
    if (s.reason === 'open' || silent || s.start_ms >= (layout.blackout?.t_ms ?? Infinity)) continue;
    if (s.reason === 'button' && d >= lmin) continue; // the ending holds through the blackout by design
    if (d < lmin || d > lmax) { s.forced = true; warnings.push(`shot ${s.cue} @${s.start_ms}ms lasts ${d}ms (outside ${lmin}–${lmax})`); }
  }
  return { shots: out, warnings };
}

function firstLineStart(L: SketchLine[]): number { return L[0]?.start_ms ?? 0; }
