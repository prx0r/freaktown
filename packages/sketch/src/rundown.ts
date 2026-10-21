/**
 * Show rundown template + cast-size defaults, derived from public sketch-show
 * STRUCTURE metadata (data/structure-stats.json — aggregate counts from
 * hhllcks/snldb, itself scraped from snlarchives.net; no scripts or names).
 *
 * What the stats say (≈900 episodes, 46 seasons):
 *   - the cold open is first in ~99.6% of shows; the monologue follows it in ~97%
 *   - goodnights close ~96.5%; the news desk sits in the back half in ~95%
 *     (median relative position ≈ 0.53)
 *   - median 6 live sketches + 2 filmed pieces per show (IQR 5–7 live)
 *   - median live-sketch cast 5 (IQR 4–7); cold opens 4; news desk 4
 *   - ~21% of live sketches are installments of a recurring sketch
 *
 * So the default show: cold open → monologue → N sketches (filmed piece
 * mixed in) → news-desk segment → more sketches → closer.
 */
import stats from '../data/structure-stats.json';

export type SegmentType = 'cold_open' | 'monologue' | 'sketch' | 'filmed' | 'news_desk' | 'closer';

export interface RundownSlot {
  index: number;
  type: SegmentType;
  /** Set this slot plays in by default. */
  set: string;
  /** Suggested cast size (performers on stage). */
  cast: number;
  /** Rough target running time (s) for a generated/written piece. */
  target_s: number;
  /** Slot is a candidate for a recurring sketch installment. */
  recurring_candidate: boolean;
}

export interface ShowRundown { title: string; slots: RundownSlot[]; source: string }

const S = stats as unknown as {
  per_episode: { live_sketches: { median: number }; filmed_pieces: { median: number } };
  cast_size_per_segment: Record<string, { median: number; p25: number; p75: number }>;
  recurring: Record<string, { share: number }>;
  order: { median_relative_position: Record<string, number> };
};

/** Median cast size per segment type (from the stats), clamped to what a set can seat. */
export function defaultCastSize(type: SegmentType, maxSeats = 8): number {
  const key = type === 'closer' ? 'other' : type;
  const m = S.cast_size_per_segment[key]?.median ?? 3;
  return Math.max(1, Math.min(maxSeats, Math.round(m)));
}

/** Cast-size range [p25, p75] for a segment type. */
export function castSizeRange(type: SegmentType): [number, number] {
  const c = S.cast_size_per_segment[type === 'closer' ? 'other' : type];
  return c ? [Math.round(c.p25), Math.round(c.p75)] : [2, 4];
}

export const RECURRING_SKETCH_SHARE: number = S.recurring.sketch?.share ?? 0.2;
export const NEWS_DESK_POSITION: number = S.order.median_relative_position.news_desk ?? 0.53;

const SET_FOR: Record<SegmentType, string> = {
  cold_open: 'news-studio', monologue: 'comedy-club', sketch: 'podcast', filmed: 'podcast', news_desk: 'news-studio', closer: 'comedy-club',
};
const TARGET_S: Record<SegmentType, number> = { cold_open: 300, monologue: 300, sketch: 330, filmed: 120, news_desk: 600, closer: 90 };

/**
 * cold open → monologue → N sketches (filmed pieces interleaved) → news desk → remaining sketches → closer.
 * N defaults to the median live-sketch count; the news desk lands at the stats' median relative position.
 */
export function showRundownTemplate(opts: { title?: string; sketches?: number; filmed?: number; sets?: Partial<Record<SegmentType, string>> } = {}): ShowRundown {
  const n = Math.max(1, opts.sketches ?? Math.round(S.per_episode.live_sketches.median));
  const f = Math.max(0, opts.filmed ?? Math.round(S.per_episode.filmed_pieces.median));
  const middle: SegmentType[] = [];
  let fl = f;
  for (let i = 0; i < n; i++) {
    middle.push('sketch');
    if (fl > 0 && i % Math.max(1, Math.floor(n / (f + 1))) === 0 && i < n - 1) { middle.push('filmed'); fl--; }
  }
  // news desk at the median relative position of the whole show
  const total = middle.length + 4;
  const deskAt = Math.max(1, Math.min(middle.length - 1, Math.round(NEWS_DESK_POSITION * total) - 2));
  middle.splice(deskAt, 0, 'news_desk');
  const types: SegmentType[] = ['cold_open', 'monologue', ...middle, 'closer'];
  let sk = 0;
  const slots = types.map((type, index) => {
    if (type === 'sketch') sk++;
    return {
      index, type,
      set: opts.sets?.[type] ?? SET_FOR[type],
      cast: defaultCastSize(type),
      target_s: TARGET_S[type],
      // spread recurring installments at the stats' share (deterministic: every k-th live sketch)
      recurring_candidate: type === 'sketch' && sk % Math.max(1, Math.round(1 / RECURRING_SKETCH_SHARE)) === 0,
    };
  });
  return { title: opts.title ?? 'Untitled show', slots, source: 'packages/sketch/data/structure-stats.json (hhllcks/snldb metadata, snlarchives.net)' };
}
