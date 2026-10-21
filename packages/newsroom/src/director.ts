/**
 * Newsroom camera director.
 *
 * Shot TIMING follows BBC R&D's "Ed" (Wright et al., IBC 2018, "AI in
 * production: video analysis and machine learning for expanded live events
 * coverage"): lay out evenly spaced cuts at (lmax+lmin)/2, then move each
 * toward the nearest speech event (sentence end / speaker change) by at
 * most (lmax−lmin)/4. Shot SELECTION follows Ed's guidelines: keep the
 * speaker in shot, switch between one-shots and two-shots for variety,
 * occasional establishing wide, occasional reaction shot, prefer crops not
 * used recently; closer crops when someone speaks, wider when nobody does.
 *
 * On top of Ed, broadcast-news grammar (hard constraints, laid first):
 *   open        wide under the jingle → slow push-in to the anchor
 *   new story   wall headline on a wide / 3/4 over-the-shoulder first, then the single
 *   reporter    remote reporter = the wall (country card) + lower third
 *   numbers     a figure line → over-the-shoulder on the full-wall numbers card
 *   section     sting + wide
 *   close       slow pull-out to the wide
 * Cuts never land inside a word, nor in the last tail_hold_ms of a line.
 *
 * Pure + deterministic (seeded PRNG): same input → same shots.
 */
import type { CadenceProfile } from './styles';
import { figureTime, type Program, type TimedLine } from './timing';

export type ShotClass = 'wide' | 'two' | 'ots' | 'one' | 'reaction';

export interface CueInfo {
  cue: string;
  cls: ShotClass;
  /** Seats visible in the frame. */
  seats: string[];
  /** The video wall is visible + legible in this frame. */
  wall: boolean;
}

export type ShotReason = 'open' | 'push-in' | 'story-wall' | 'story-single' | 'numbers' | 'sting' | 'close' | 'ed' | 'establish' | 'reaction';

export interface Shot {
  start_ms: number;
  end_ms: number;
  cue: string;
  cls: ShotClass;
  reason: ShotReason;
  move_ms?: number;
  creep?: number;
  creep_ms?: number;
  /** Shot length outside [lmin,lmax] because no legal cut point existed (reported, not hidden). */
  forced?: boolean;
  /** Grammar shot whose framing must not change (section sting wide). */
  locked?: boolean;
  storyId?: string;
}

export interface DirectorResult { shots: Shot[]; warnings: string[] }

/** Default cue table for the news-studio set, filtered to the seats actually cast. */
export function newsStudioCameras(castSeats: string[]): CueInfo[] {
  const has = (s: string) => castSeats.includes(s);
  const out: CueInfo[] = [
    { cue: 'wide', cls: 'wide', seats: castSeats, wall: true },
    { cue: 'wall-ots', cls: 'ots', seats: castSeats.filter((s) => s === 'anchor1' || s === 'anchor2'), wall: true },
  ];
  if (has('anchor1') && has('anchor2')) out.push({ cue: 'two-shot', cls: 'two', seats: ['anchor1', 'anchor2'], wall: false });
  for (const s of ['anchor1', 'anchor2']) if (has(s)) {
    out.push({ cue: `${s}-single`, cls: 'one', seats: [s], wall: false });
    out.push({ cue: `reaction:${s}`, cls: 'reaction', seats: [s], wall: false });
  }
  return out;
}

// ── cut points ─────────────────────────────────────────────────────────

interface CutPoint { t: number; strength: number } // 3 speaker/line boundary · 2 sentence end · 1 comma · 0 word gap · 4 silence (no speech)

function mulberry32(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
export function seedOf(s: string): number { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

/** Is t a legal cut instant? Not inside a word, not inside a line's tail hold. */
export function isLegalCut(t: number, lines: TimedLine[], tailHold: number): boolean {
  for (const l of lines) {
    if (t <= l.start_ms || t >= l.end_ms) continue;
    if (t > l.end_ms - tailHold) return false;
    for (const w of l.words) if (t > w.start_ms && t < w.end_ms) return false;
  }
  return true;
}

function cutPoints(p: Program, C: CadenceProfile): CutPoint[] {
  const pts: CutPoint[] = [];
  const L = p.lines;
  for (let i = 0; i < L.length; i++) {
    const l = L[i];
    const next = L[i + 1];
    const gapEnd = next ? next.start_ms : p.duration_ms;
    // speaker / line boundary: just after the line ends (the hold is over), well before the next starts
    pts.push({ t: Math.round(Math.min(gapEnd, l.end_ms + Math.min(400, (gapEnd - l.end_ms) / 2))), strength: next && next.chair !== l.chair ? 3 : 2.5 });
    for (let k = 0; k < l.words.length - 1; k++) {
      const w = l.words[k], nx = l.words[k + 1];
      const t = Math.round((w.end_ms + nx.start_ms) / 2);
      if (t > l.end_ms - C.tail_hold_ms) continue;
      const s = /[.!?]["'”’)]*$/.test(w.word) ? 2 : /[,;:—–]["'”’)]*$/.test(w.word) ? 1 : 0;
      pts.push({ t, strength: s });
    }
  }
  return pts.filter((c) => isLegalCut(c.t, L, C.tail_hold_ms)).sort((a, b) => a.t - b.t);
}

/** Snap x toward the nearest strong boundary within ±w (Ed); fall back to any legal point. */
function snap(x: number, w: number, pts: CutPoint[], lo: number, hi: number, silent: (t: number) => boolean): number {
  if (silent(x)) return x;
  const inWin = pts.filter((c) => c.t >= Math.max(lo, x - w) && c.t <= Math.min(hi, x + w));
  for (const minS of [2, 1, 0]) {
    const c = inWin.filter((q) => q.strength >= minS);
    if (c.length) return c.reduce((b, q) => (Math.abs(q.t - x) < Math.abs(b.t - x) ? q : b)).t;
  }
  const any = pts.filter((c) => c.t > lo && c.t < hi);
  if (any.length) return any.reduce((b, q) => (Math.abs(q.t - x) < Math.abs(b.t - x) ? q : b)).t;
  return NaN;
}

// ── director ───────────────────────────────────────────────────────────

export interface DirectorOptions {
  cadence: CadenceProfile;
  cameras: CueInfo[];
  seed?: string;
}

interface Fixed { start: number; cue: string; reason: ShotReason; move_ms?: number; minEnd?: number; storyId?: string; locked?: boolean }

export function directShots(p: Program, o: DirectorOptions): DirectorResult {
  const C = o.cadence;
  const cams = o.cameras;
  const warnings: string[] = [];
  const rng = mulberry32(seedOf(o.seed ?? 'newsroom'));
  const pts = cutPoints(p, C);
  const L = p.lines;
  const lmin = C.lmin_ms, lmax = C.lmax_ms;
  const cueByName = new Map(cams.map((c) => [c.cue, c]));
  const wide = cams.find((c) => c.cls === 'wide')!;
  const ots = cams.find((c) => c.cls === 'ots' && c.wall) ?? wide;
  const firstSeat = L.find((l) => l.seat)?.seat ?? null;
  const singleOf = (seat: string) => cams.find((c) => c.cls === 'one' && c.seats.length === 1 && c.seats[0] === seat);
  const silentAt = (t: number) => !L.some((l) => t > l.start_ms - 1 && t < l.end_ms + 1);
  const speakingIn = (a: number, b: number) => L.filter((l) => l.start_ms < b && l.end_ms > a);
  const legalAfter = (t: number, hi = Infinity): number => {
    if (isLegalCut(t, L, C.tail_hold_ms)) return t;
    const c = pts.find((q) => q.t >= t && q.t <= hi);
    return c ? c.t : NaN;
  };
  /** First boundary (sentence/speaker preferred) at or after lo, not later than hi. */
  const boundaryIn = (lo: number, hi: number): number => {
    if (lo >= hi) return NaN;
    for (const minS of [2, 1, 0]) { const c = pts.find((q) => q.t >= lo && q.t <= hi && q.strength >= minS); if (c) return c.t; }
    return NaN;
  };

  /** Last boundary in [lo, hi] (strongest kind first). */
  const latestBoundary = (lo: number, hi: number): number => {
    for (const minS of [2, 1, 0]) { const c = pts.filter((q) => q.t >= lo && q.t <= hi && q.strength >= minS); if (c.length) return c[c.length - 1].t; }
    return NaN;
  };

  // 1) grammar: fixed shots (start times) ──────────────────────────────
  const fixed: Fixed[] = [];
  const firstRead = L[0]?.start_ms ?? 0;
  fixed.push({ start: 0, cue: wide.cue, reason: 'open' });
  if (firstSeat && singleOf(firstSeat)) fixed.push({ start: Math.max(C.open_wide_ms, firstRead - Math.round(C.open_push_ms * 0.5)), cue: singleOf(firstSeat)!.cue, reason: 'push-in', move_ms: C.open_push_ms });
  // stings → wide
  for (const j of p.jingles) if (j.kind === 'sting') fixed.push({ start: j.start_ms, cue: wide.cue, reason: 'sting', locked: true });
  // stories (not the open/close ritual): headline shot, then the single
  let altWall = 0;
  for (const st of p.stories) {
    if (st.segmentKind !== 'section' || st.firstRead_ms === null) continue;
    const inSting = fixed.find((f) => f.reason === 'sting' && f.start <= st.start_ms && st.start_ms - f.start < lmax);
    let wallStart: number, wallCue: CueInfo;
    if (inSting) { wallStart = inSting.start; wallCue = wide; inSting.reason = 'story-wall'; inSting.storyId = st.id; inSting.locked = true; }
    else {
      wallStart = legalAfter(Math.max(0, st.firstRead_ms - Math.min(700, C.story_gap_ms / 2)), st.firstRead_ms);
      if (!Number.isFinite(wallStart)) wallStart = st.firstRead_ms;
      wallCue = altWall++ % 3 === 2 ? wide : ots;
      fixed.push({ start: wallStart, cue: wallCue.cue, reason: 'story-wall', storyId: st.id });
    }
    const storyLines = L.filter((l) => l.storyId === st.id);
    const studio = storyLines.find((l) => l.seat);
    const single = studio?.seat ? singleOf(studio.seat) : undefined;
    if (!single) continue;
    // the single must leave both shots inside [lmin, lmax]: after the wall has held lmin,
    // and at least lmin before the next story's wall shot
    const nextStory = p.stories.find((x) => x.index === st.index + 1);
    const storyOut = (nextStory?.firstRead_ms ?? p.duration_ms) - 700;
    let lo = wallStart + lmin;
    const hi = Math.min(wallStart + lmax, storyOut - lmin);
    // keep the wall up while a numbers line is being read, until its figure has been spoken (if the bounds allow)
    const numLine = storyLines.find((l) => l.numbers && l.start_ms < hi && l.end_ms > lo);
    if (numLine) lo = Math.max(lo, Math.min(figureTime(numLine) + 1500, hi));
    let singleAt = boundaryIn(lo, hi);
    if (!Number.isFinite(singleAt) && storyOut - wallStart > lmax) singleAt = latestBoundary(wallStart + lmin, hi > wallStart + lmin ? hi : Math.min(wallStart + lmax, st.end_ms));
    // only cut to the single if the speaker at that moment is the one we frame (or nobody speaks)
    if (Number.isFinite(singleAt)) {
      const who = speakingIn(singleAt, singleAt + lmin)[0];
      if (!who || who.seat === single.seats[0]) fixed.push({ start: singleAt, cue: single.cue, reason: 'story-single', storyId: st.id, move_ms: C.move_ms || undefined });
    }
  }
  // numbers lines → OTS on the full-wall numbers card
  for (const l of L) if (l.numbers) {
    if (!l.seat) continue; // remote reporter: every shot already shows the wall (country card → figure)
    const at = legalAfter(l.start_ms - 1);
    if (!Number.isFinite(at)) continue;
    if (fixed.some((f) => Math.abs(f.start - at) < lmin)) {
      // a story-wall shot already shows the wall: upgrade it rather than stacking a short shot
      const near = fixed.find((f) => Math.abs(f.start - at) < lmin && (f.reason === 'story-wall'));
      if (near) { near.cue = ots.cue; continue; }
      const blocking = fixed.filter((f) => Math.abs(f.start - at) < lmin && f.reason === 'story-single');
      blocking.forEach((b) => fixed.splice(fixed.indexOf(b), 1));
    }
    fixed.push({ start: at, cue: ots.cue, reason: 'numbers', storyId: l.storyId });
  }
  // close: settle on the anchor for the close bones, then a slow pull-out to the wide
  const closeSeg = p.segments.find((s) => s.kind === 'close');
  const lastLine = L[L.length - 1];
  let closeSingleAt = -Infinity;
  const closeFirst = closeSeg ? L.find((l) => l.segmentIndex === closeSeg.index) : undefined;
  if (closeFirst?.seat && singleOf(closeFirst.seat)) {
    const at = legalAfter(Math.max(0, closeFirst.start_ms - 700), closeFirst.start_ms);
    if (Number.isFinite(at)) { closeSingleAt = at; fixed.push({ start: at, cue: singleOf(closeFirst.seat)!.cue, reason: 'story-single', storyId: closeFirst.storyId, move_ms: C.move_ms || undefined }); }
  }
  if (lastLine) {
    const want = Math.max(closeSeg ? closeSeg.start_ms : 0, closeSingleAt + lmin, lastLine.end_ms - C.close_pull_ms - lmin * 0.5);
    let at = want >= lastLine.end_ms - C.tail_hold_ms ? Math.max(want, lastLine.end_ms + 200) : snap(want, (lmax - lmin) / 4, pts, Math.max(closeSingleAt + lmin, want - (lmax - lmin) / 4), lastLine.end_ms, silentAt);
    if (!Number.isFinite(at)) at = Math.max(want, lastLine.end_ms + 200);
    fixed.push({ start: at, cue: wide.cue, reason: 'close', move_ms: C.close_pull_ms });
  }
  fixed.sort((a, b) => a.start - b.start);
  // collapse fixed shots that collide (keep the later grammar beat, it carries the new information)
  for (let i = fixed.length - 2; i >= 0; i--) {
    if (fixed[i + 1].start - fixed[i].start < Math.min(lmin, 2500) && fixed[i].reason !== 'open') {
      const keep = rank(fixed[i]) >= rank(fixed[i + 1]) ? i : i + 1;
      const drop = keep === i ? i + 1 : i;
      if (keep === i) fixed[i].start = Math.min(fixed[i].start, fixed[i + 1].start);
      fixed.splice(drop, 1);
    }
  }

  // 2) Ed sequencing inside each free interval ──────────────────────────
  const shots: Shot[] = [];
  const avg = (lmax + lmin) / 2, pull = (lmax - lmin) / 4;
  for (let i = 0; i < fixed.length; i++) {
    const f = fixed[i];
    const end = i + 1 < fixed.length ? fixed[i + 1].start : p.duration_ms;
    const info = cueByName.get(f.cue) ?? wide;
    // the fixed shot holds for at least lmin (or until the next fixed beat)
    const cuts: number[] = [];
    const span = end - f.start;
    const firstFree = f.reason === 'open' || f.reason === 'close' ? end : f.start + Math.max(lmin, Math.min(avg, span));
    if (end - firstFree >= lmin && f.reason !== 'close' && f.reason !== 'open') {
      const free = end - f.start;
      const n = Math.max(1, Math.round(free / avg));
      const step = free / n;
      let prev = f.start;
      for (let k = 1; k < n; k++) {
        const x = f.start + k * step;
        const c = snap(x, pull, pts, prev + lmin, end - lmin, silentAt);
        if (Number.isFinite(c) && c - prev >= lmin && end - c >= lmin) { cuts.push(c); prev = c; }
      }
    }
    const bounds = [f.start, ...cuts, end];
    for (let k = 0; k < bounds.length - 1; k++) {
      const s = bounds[k], e = bounds[k + 1];
      if (e <= s) continue;
      if (k === 0) {
        shots.push({ start_ms: s, end_ms: e, cue: info.cue, cls: info.cls, reason: f.reason, move_ms: f.move_ms, storyId: f.storyId, locked: f.locked });
      } else {
        const pick = choose(s, e, shots, k === bounds.length - 2 ? fixed[i + 1]?.cue : undefined);
        shots.push({ start_ms: s, end_ms: e, cue: pick.c.cue, cls: pick.c.cls, reason: pick.reason });
      }
    }
  }

  function choose(s: number, e: number, history: Shot[] = shots, nextCue?: string): { c: CueInfo; reason: ShotReason } {
    const sp = speakingIn(s, e);
    const studioSeats = [...new Set(sp.map((l) => l.seat).filter((x): x is string => !!x))];
    const remote = sp.some((l) => !l.seat);
    const recent = history.slice(-C.recent_window);
    const prev = history[history.length - 1];
    const sinceWide = (() => { let n = 0; for (let i = history.length - 1; i >= 0 && history[i].cls !== 'wide'; i--) n++; return n; })();
    const reactionRoll = rng();
    let best: { c: CueInfo; score: number; reason: ShotReason } | null = null;
    for (const c of cams) {
      // hard: keep the speaker in shot (a remote reporter is "in shot" when the wall is)
      if (!studioSeats.every((x) => c.seats.includes(x))) continue;
      if (c.cls === 'reaction') {
        // reaction cut-away: only while a remote reporter speaks (the anchor listens), never over studio speech
        if (!remote || studioSeats.length) continue;
      } else if (remote && !c.wall) continue;
      let score = 0;
      const speech = sp.length > 0;
      score += speech ? ({ one: 3, two: 2.2, ots: 2.2, wide: 0.6, reaction: 0 } as const)[c.cls] : ({ wide: 3, two: 2, ots: 2, one: 0.5, reaction: 0 } as const)[c.cls];
      if (prev && prev.cls === c.cls) score -= 2.5; // variety: one-shot ↔ two-shot
      if (prev && prev.cue === c.cue) score -= 6;
      if (nextCue && nextCue === c.cue) score -= 6; // the next grammar beat already uses this framing
      recent.forEach((r, i) => { if (r.cue === c.cue) score -= 3 * ((i + 1) / recent.length); });
      let reason: ShotReason = 'ed';
      if (c.cls === 'wide' && C.establish_every && sinceWide >= C.establish_every) { score += 6; reason = 'establish'; }
      if (c.cls === 'reaction') { if (reactionRoll < C.reaction_chance && e - s <= lmax) { score += 5; reason = 'reaction'; } else score -= 10; }
      if (!best || score > best.score) best = { c, score, reason };
    }
    return best ? { c: best.c, reason: best.reason } : { c: wide, reason: 'ed' };
  }

  // 2b) repair: every shot must keep its speakers in frame. Split at the
  // speaker change when both halves can hold ≥ lmin, else re-pick a cue that
  // frames everyone speaking in the shot (e.g. the 3/4 with the wall).
  const fits = (c: CueInfo, a: number, b: number) => {
    const sp = speakingIn(a, b);
    for (const l of sp) {
      if (l.seat ? !c.seats.includes(l.seat) : !(c.wall || c.cls === 'reaction')) return false;
      if (c.cls === 'reaction' && l.seat) return false;
    }
    return true;
  };
  const repaired: Shot[] = [];
  const queue = [...shots];
  while (queue.length) {
    const sh = queue.shift()!;
    const info = cueByName.get(sh.cue) ?? wide;
    if (fits(info, sh.start_ms, sh.end_ms)) { repaired.push(sh); continue; }
    // speaker-change boundaries inside the shot
    const changes = pts.filter((q) => q.strength >= 2.5 && q.t > sh.start_ms + lmin && q.t < sh.end_ms - lmin);
    const split = changes.find((q) => fits(info, sh.start_ms, q.t));
    if (split && sh.reason !== 'close' && sh.reason !== 'open') {
      repaired.push({ ...sh, end_ms: split.t });
      const pick = choose(split.t, sh.end_ms, repaired);
      queue.unshift({ start_ms: split.t, end_ms: sh.end_ms, cue: pick.c.cue, cls: pick.c.cls, reason: pick.reason, storyId: sh.storyId });
      continue;
    }
    const alt = cams.filter((c) => c.cls !== 'reaction' && fits(c, sh.start_ms, sh.end_ms));
    const prevCue = repaired[repaired.length - 1]?.cue;
    const prefer = alt.find((c) => c.cls === 'ots' && c.cue !== prevCue) ?? alt.find((c) => c.cls === 'two' && c.cue !== prevCue) ?? alt.find((c) => c.cue !== prevCue) ?? alt[0] ?? wide;
    repaired.push({ ...sh, cue: prefer.cue, cls: prefer.cls, reason: sh.reason === 'story-single' || sh.reason === 'push-in' ? 'ed' : sh.reason });
  }
  shots.length = 0;
  shots.push(...repaired);
  // a grammar wall shot that repeats the previous framing flips to the other wall framing (wide ↔ 3/4)
  for (let i = 1; i < shots.length; i++) {
    const sh = shots[i];
    if ((sh.reason === 'story-wall' || sh.reason === 'numbers') && !sh.locked && sh.cue === shots[i - 1].cue) {
      const other = cams.find((c) => c.wall && c.cue !== sh.cue && c.cue !== shots[i + 1]?.cue && fits(c, sh.start_ms, sh.end_ms));
      if (other) { sh.cue = other.cue; sh.cls = other.cls; }
    }
  }

  // 3) moves: eased push-ins into one-shots + creep while they hold ─────
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i], prev = shots[i - 1];
    const d = s.end_ms - s.start_ms;
    if (C.move_ms && prev && !s.move_ms && (s.cls === 'one' || s.cls === 'reaction') && (prev.cls === 'wide' || prev.cls === 'ots' || prev.cls === 'two')) s.move_ms = Math.min(C.move_ms, Math.round(d * 0.4));
    if (s.move_ms) s.move_ms = Math.min(s.move_ms, Math.max(0, d - 200));
    if (C.creep && (s.cls === 'one' || s.cls === 'ots') && d >= lmin) { s.creep = C.creep; s.creep_ms = d; }
  }
  // same framing back to back is an invisible cut: merge when the result stays ≤ lmax (or is a grammar-free Ed slot),
  // otherwise re-frame the later shot (the other wall framing / the best fitting cue)
  for (let i = shots.length - 1; i > 0; i--) {
    const a = shots[i - 1], b = shots[i];
    if (a.cue !== b.cue || b.move_ms) continue;
    const grammar = b.reason === 'story-wall' || b.reason === 'numbers';
    if (b.end_ms - a.start_ms <= lmax) {
      a.end_ms = b.end_ms;
      if (a.creep) a.creep_ms = a.end_ms - a.start_ms;
      shots.splice(i, 1);
    } else {
      const other = cams.find((c) => c.cue !== b.cue && c.cls !== 'reaction' && (grammar ? c.wall : true) && c.cue !== shots[i + 1]?.cue && fits(c, b.start_ms, b.end_ms));
      if (other) { b.cue = other.cue; b.cls = other.cls; continue; }
      // else re-frame the earlier shot (keeping wall grammar if it had it)
      const aGrammar = a.reason === 'story-wall' || a.reason === 'numbers';
      const otherA = !a.locked && cams.find((c) => c.cue !== a.cue && c.cls !== 'reaction' && (aGrammar ? c.wall : true) && c.cue !== shots[i - 2]?.cue && fits(c, a.start_ms, a.end_ms));
      if (otherA) { a.cue = otherA.cue; a.cls = otherA.cls; }
    }
  }
  // flag (never hide) shots outside the cadence bounds; the open/close holds and jingles are exempt
  for (const s of shots) {
    const d = s.end_ms - s.start_ms;
    const silent = speakingIn(s.start_ms, s.end_ms).length === 0;
    if (s.reason === 'open' || s.reason === 'close' || silent) continue;
    if (d < lmin || d > lmax) { s.forced = true; warnings.push(`shot ${s.cue} @${s.start_ms}ms lasts ${d}ms (outside ${lmin}–${lmax}): no legal cut point`); }
  }
  return { shots, warnings };
}

function rank(f: Fixed): number {
  return ({ open: 9, close: 8, 'story-wall': 7, numbers: 6, sting: 5, 'story-single': 4, 'push-in': 3, ed: 1, establish: 1, reaction: 1 } as Record<ShotReason, number>)[f.reason];
}
