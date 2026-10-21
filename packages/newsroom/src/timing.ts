/**
 * Timing — turns a rundown into a program clock: every read gets absolute
 * word times, every jingle/graphic a time, every story/segment a span.
 *
 * Preferred input: measured word timings (words.json, the face layer's
 * {word,start_ms,end_ms} format) — per line on the piece, per line id in
 * `timings.lines`, or one episode-wide list in `timings.episodeWords`
 * (aligned to the reads in order). Fallback: an estimate from the text at
 * the style's wpm (105 for goodnight), flagged `estimated: true` on every
 * line and on the program.
 */
import type { Piece, ReadPiece, RundownV1, WordTiming, SegmentKind } from './schema';
import { isRead } from './schema';
import type { ShowStyle } from './styles';

export interface TimingsInput {
  /** Measured words per read, keyed by line id (piece.id or "<storyId>#<pieceIndex>"). Relative to line start. */
  lines?: Record<string, WordTiming[]>;
  /** Episode-wide measured words (absolute ms on the audio clock), aligned to reads in order. */
  episodeWords?: WordTiming[];
  /** Force estimates even when words exist (debug). */
  forceEstimate?: boolean;
}

/** A word on the absolute show clock. */
export interface ClockWord { word: string; start_ms: number; end_ms: number }

export interface TimedLine {
  id: string;
  kind: 'anchor' | 'reporter';
  chair: string;
  /** Seat on the set, or null for a remote reporter (shown on the wall). */
  seat: string | null;
  name: string;
  locale?: string;
  country?: string;
  text: string;
  start_ms: number;
  end_ms: number;
  words: ClockWord[];
  estimated: boolean;
  segmentIndex: number;
  storyIndex: number; // global story index
  storyId: string;
  segmentId: string;
  pieceIndex: number;
  emotion?: string;
  numbers?: { figure: string; label?: string };
  /** Relative words (for dialogue.line payloads). */
  relWords: WordTiming[];
}

export interface TimedGraphic { t_ms: number; piece: Piece; storyId: string; storyIndex: number; segmentIndex: number }
export interface TimedJingle { start_ms: number; end_ms: number; kind: 'open' | 'sting' | 'close'; asset?: string; segmentIndex: number }
export interface TimedStory { id: string; index: number; segmentIndex: number; segmentKind: SegmentKind; title?: string; start_ms: number; end_ms: number; firstRead_ms: number | null }
export interface TimedSegment { id: string; index: number; kind: SegmentKind; title: string; start_ms: number; end_ms: number }

export interface Program {
  lines: TimedLine[];
  graphics: TimedGraphic[];
  jingles: TimedJingle[];
  stories: TimedStory[];
  segments: TimedSegment[];
  duration_ms: number;
  /** True when ANY line used estimated timings. */
  estimated: boolean;
  timingSource: 'measured' | 'estimated' | 'mixed';
}

const SENT_END = /[.!?]["'”’)]*$/;
const COMMA = /[,;:—–-]["'”’)]*$/;

export function tokenize(text: string): string[] {
  return text.replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
}
export const normWord = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');

/**
 * Estimated word timings for a line at `wpm`: total = words × 60000/wpm,
 * shared by word length, with silent pauses after commas / sentence ends
 * carved out of the same budget (so the overall pace stays at wpm).
 */
export function estimateWords(text: string, wpm: number): WordTiming[] {
  const toks = tokenize(text);
  if (!toks.length) return [];
  const total = (toks.length * 60000) / wpm;
  const speak = toks.map((t) => normWord(t).length + 3);
  const pause: number[] = toks.map((t, i) => (i === toks.length - 1 ? 0 : SENT_END.test(t) ? 7 : COMMA.test(t) ? 3 : 0));
  const unit = total / (speak.reduce((a, b) => a + b, 0) + pause.reduce((a, b) => a + b, 0));
  const out: WordTiming[] = [];
  let t = 0;
  toks.forEach((w, i) => {
    const d = speak[i] * unit;
    out.push({ word: w, start_ms: Math.round(t), end_ms: Math.round(t + d) });
    t += d + pause[i] * unit;
  });
  return out;
}

export function lineIdOf(storyId: string, pieceIndex: number, p: Piece): string {
  return p.id ?? `${storyId}#${pieceIndex}`;
}

/** Greedy sequential alignment of episode words to the reads' tokens. Returns relative words per line (or null). */
export function alignEpisodeWords(reads: Array<{ id: string; text: string }>, ep: WordTiming[]): Map<string, { start: number; words: WordTiming[] } | null> {
  const out = new Map<string, { start: number; words: WordTiming[] } | null>();
  let k = 0;
  for (const r of reads) {
    const toks = tokenize(r.text);
    const got: WordTiming[] = [];
    for (const tok of toks) {
      const n = normWord(tok);
      // look ahead a little to resync after a skipped/inserted word
      let hit = -1;
      for (let j = k; j < Math.min(ep.length, k + 6); j++) if (normWord(ep[j].word) === n) { hit = j; break; }
      if (hit < 0) { if (k < ep.length) { got.push({ word: tok, start_ms: ep[k].start_ms, end_ms: ep[k].end_ms }); k++; } continue; }
      got.push({ word: tok, start_ms: ep[hit].start_ms, end_ms: ep[hit].end_ms });
      k = hit + 1;
    }
    if (got.length !== toks.length || !got.length) { out.set(r.id, null); continue; }
    const start = got[0].start_ms;
    out.set(r.id, { start, words: got.map((w) => ({ word: w.word, start_ms: w.start_ms - start, end_ms: w.end_ms - start })) });
  }
  return out;
}

/** Lay the rundown on a clock. */
export function layoutProgram(rd: RundownV1, style: ShowStyle, timings: TimingsInput = {}): Program {
  const C = style.cadence;
  const anchors = new Map(rd.cast.anchors.map((a) => [a.chair, a]));
  const reporters = new Map((rd.cast.reporters ?? []).map((r) => [r.chair, r]));
  const firstAnchor = rd.cast.anchors[0];

  const allReads: Array<{ id: string; text: string }> = [];
  rd.segments.forEach((s) => s.stories.forEach((st) => st.pieces.forEach((p, pi) => { if (isRead(p)) allReads.push({ id: lineIdOf(st.id, pi, p), text: p.text }); })));
  const aligned = timings.episodeWords?.length && !timings.forceEstimate ? alignEpisodeWords(allReads, timings.episodeWords) : null;

  const lines: TimedLine[] = [];
  const graphics: TimedGraphic[] = [];
  const jingles: TimedJingle[] = [];
  const stories: TimedStory[] = [];
  const segments: TimedSegment[] = [];
  let t = 0;
  let storyIndex = 0;
  let measured = 0, estimated = 0;
  let prevWasRead = false;

  rd.segments.forEach((seg, si) => {
    const segStart = t;
    seg.stories.forEach((st, sti) => {
      if (sti > 0 || si > 0) t += prevWasRead ? C.story_gap_ms - C.line_gap_ms : 0;
      const storyStart = t;
      let firstRead: number | null = null;
      let pending: Piece[] = [];
      const flush = (at: number) => { for (const g of pending) graphics.push({ t_ms: at, piece: g, storyId: st.id, storyIndex, segmentIndex: si }); pending = []; };
      st.pieces.forEach((p, pi) => {
        if (p.type === 'jingle') {
          flush(t); // graphics placed before a jingle go up with it (title card under the open)
          const d = p.duration_ms ?? (p.kind === 'open' ? C.jingle_open_ms : p.kind === 'close' ? C.jingle_close_ms : C.jingle_sting_ms);
          jingles.push({ start_ms: t, end_ms: t + d, kind: p.kind, asset: p.asset ?? style.jingles[p.kind], segmentIndex: si });
          t += d;
          prevWasRead = false;
          return;
        }
        if (!isRead(p)) { pending.push(p); return; }
        const r = p as ReadPiece;
        const id = lineIdOf(st.id, pi, p);
        let rel: WordTiming[] | null = null;
        let start = t;
        if (!timings.forceEstimate) {
          if (r.words?.length) rel = r.words;
          else if (timings.lines?.[id]?.length) rel = timings.lines[id];
          else if (aligned?.get(id)) { const a = aligned.get(id)!; rel = a.words; start = Math.max(t, a.start); }
        }
        const isEst = !rel;
        if (isEst) { rel = estimateWords(r.text, C.wpm); estimated++; } else measured++;
        flush(start);
        const words = rel!.map((w) => ({ word: w.word, start_ms: start + w.start_ms, end_ms: start + w.end_ms }));
        const end = words.length ? words[words.length - 1].end_ms : start;
        let chair: string, seat: string | null, name: string, locale: string | undefined, kind: 'anchor' | 'reporter';
        if (r.type === 'anchor_read') {
          const a = anchors.get(r.chair ?? firstAnchor.chair) ?? firstAnchor;
          chair = a.chair; seat = a.seat; name = a.name; kind = 'anchor';
        } else {
          const rc = reporters.get(r.chair);
          chair = r.chair; kind = 'reporter';
          name = r.name ?? rc?.name ?? r.chair;
          locale = r.locale ?? rc?.locale;
          seat = rc?.presence === 'studio' ? rc.seat ?? null : null;
        }
        lines.push({
          id, kind, chair, seat, name, locale, country: r.type === 'reporter_read' ? r.country ?? st.country : st.country,
          text: r.text, start_ms: start, end_ms: end, words, estimated: isEst,
          segmentIndex: si, storyIndex, storyId: st.id, segmentId: seg.id, pieceIndex: pi,
          emotion: r.type === 'anchor_read' ? r.emotion ?? style.anchorEmotion : undefined, numbers: r.numbers, relWords: rel!,
        });
        if (firstRead === null) firstRead = start;
        t = end + C.line_gap_ms;
        prevWasRead = true;
      });
      flush(t);
      const storyEnd = prevWasRead ? t - C.line_gap_ms : t;
      stories.push({ id: st.id, index: storyIndex, segmentIndex: si, segmentKind: seg.kind, title: st.title, start_ms: storyStart, end_ms: Math.max(storyStart, storyEnd), firstRead_ms: firstRead });
      storyIndex++;
    });
    segments.push({ id: seg.id, index: si, kind: seg.kind, title: seg.title, start_ms: segStart, end_ms: Math.max(segStart, prevWasRead ? t - C.line_gap_ms : t) });
  });
  const lastEnd = Math.max(prevWasRead ? t - C.line_gap_ms : t, ...jingles.map((j) => j.end_ms));
  // end-card hold: let the close pull-out land on a still wide
  const duration = lastEnd + Math.max(1500, Math.round(C.close_pull_ms * 0.5));
  return {
    lines, graphics, jingles, stories, segments, duration_ms: Math.round(duration),
    estimated: estimated > 0,
    timingSource: estimated && measured ? 'mixed' : estimated ? 'estimated' : 'measured',
  };
}

const NUM_WORDS = new Set('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion'.split(' '));
/** When the line's first spoken number starts (digits or number words); line start if none. */
export function figureTime(l: { start_ms: number; words: Array<{ word: string; start_ms: number }> }): number {
  for (const w of l.words) {
    const n = w.word.toLowerCase().replace(/[^a-z0-9-]/g, '');
    if (/\d/.test(n) || n.split('-').some((p) => NUM_WORDS.has(p))) return w.start_ms;
  }
  return l.start_ms;
}

