/**
 * Show styles — the look + pace of a show. A style is pure data: palette,
 * fonts, wall layout, jingle asset refs, overlay flavour and a cadence
 * profile the camera director reads. Ship: `goodnight` (calm, sleep) and
 * `default-news` (brisk). Add your own with registerShowStyle().
 */
import type { SetThemePayloadV1 } from '@funnier/contracts';

export interface CadenceProfile {
  /** Ed: minimum / maximum shot length (ms). Even spacing = (lmax+lmin)/2, pull ≤ (lmax−lmin)/4. */
  lmin_ms: number;
  lmax_ms: number;
  /** Words per minute for estimated timings (no measured words). */
  wpm: number;
  /** Silence between consecutive reads (ms). */
  line_gap_ms: number;
  /** Extra breath at a story / segment boundary (ms). */
  story_gap_ms: number;
  /** No cut inside the last N ms of a line (hold the tail). */
  tail_hold_ms: number;
  /** Eased camera move into most shots (0 = hard cuts). */
  move_ms: number;
  /** Slow push-in while a one-shot holds (fraction of camera→target distance). */
  creep: number;
  /** Open: hold the wide this long under the jingle, then push in over open_push_ms. */
  open_wide_ms: number;
  open_push_ms: number;
  /** Close: slow pull-out to the wide. */
  close_pull_ms: number;
  /** Jingle durations when the rundown does not say (ms). */
  jingle_open_ms: number;
  jingle_sting_ms: number;
  jingle_close_ms: number;
  /** An establishing wide at least every N shots (0 = never forced). */
  establish_every: number;
  /** Chance of a reaction shot per eligible slot (deterministic PRNG). */
  reaction_chance: number;
  /** Recently-used penalty: how many shots back a cue still costs. */
  recent_window: number;
}

export interface ShowStyle {
  id: string;
  name: string;
  /** Set this style dresses (the venue). */
  set: string;
  brand: string;
  palette: { bg: string; paper: string; ink: string; accent: string; accent2: string; muted: string; glow: string };
  fonts: { display: string; body: string };
  /** Wall painter layout family. */
  wall: { family: 'paper-sunrise' | 'broadcast'; brandLine: string };
  lighting: { ambient: string; key: string; fill: string; rim: string; background: string; exposure: number };
  overlay: { lowerThird: 'paper' | 'broadcast'; ticker: { enabled: boolean; label: string; speed_px_s: number }; bug?: string };
  jingles: { open?: string; sting?: string; close?: string };
  /** Face expression the anchor carries through reads. */
  anchorEmotion: string;
  cadence: CadenceProfile;
}

const SERIF = "Georgia, 'C059', 'Century Schoolbook', 'DejaVu Serif', serif";
const SANS = "Inter, 'Helvetica Neue', Arial, 'DejaVu Sans', sans-serif";

/** Calm sleep-channel news: long held shots, slow eased moves, no strobe, no wipes. */
export const GOODNIGHT: ShowStyle = {
  id: 'goodnight',
  name: 'Goodnight (calm)',
  set: 'news-studio',
  brand: 'Goodnight News',
  palette: { bg: '#07060a', paper: '#f6efe2', ink: '#2a2420', accent: '#F5C86B', accent2: '#e9a77a', muted: '#1a1612', glow: '#3a2a12' },
  fonts: { display: SERIF, body: SERIF },
  wall: { family: 'paper-sunrise', brandLine: 'GOODNIGHT NEWS' },
  lighting: { ambient: '#6b5a4a', key: '#ffe6c2', fill: '#d9c2a6', rim: '#F5C86B', background: '#07060a', exposure: 0.95 },
  overlay: { lowerThird: 'paper', ticker: { enabled: true, label: 'GOODNIGHT NEWS', speed_px_s: 26 }, bug: 'Goodnight News' },
  jingles: {},
  anchorEmotion: 'warm',
  cadence: {
    lmin_ms: 7000, lmax_ms: 16000, wpm: 105,
    line_gap_ms: 900, story_gap_ms: 1600, tail_hold_ms: 500,
    move_ms: 2400, creep: 0.07,
    open_wide_ms: 4500, open_push_ms: 5200, close_pull_ms: 7000,
    jingle_open_ms: 5000, jingle_sting_ms: 3500, jingle_close_ms: 5000,
    establish_every: 5, reaction_chance: 0.25, recent_window: 3,
  },
};

/** Brisk conventional news: short shots, hard cuts. */
export const DEFAULT_NEWS: ShowStyle = {
  id: 'default-news',
  name: 'Default news (brisk)',
  set: 'news-studio',
  brand: 'FUNNIER News',
  palette: { bg: '#04070f', paper: '#ffffff', ink: '#0b1426', accent: '#ffcc33', accent2: '#e8112d', muted: '#0c3a8c', glow: '#0a2a6a' },
  fonts: { display: SANS, body: SANS },
  wall: { family: 'broadcast', brandLine: 'FUNNIER NEWS' },
  lighting: { ambient: '#9fb4d8', key: '#ffffff', fill: '#b8d0ff', rim: '#3a7bff', background: '#04070f', exposure: 1.1 },
  overlay: { lowerThird: 'broadcast', ticker: { enabled: true, label: 'FUNNIER NEWS', speed_px_s: 90 } },
  jingles: {},
  anchorEmotion: 'neutral',
  cadence: {
    lmin_ms: 2500, lmax_ms: 6000, wpm: 160,
    line_gap_ms: 250, story_gap_ms: 500, tail_hold_ms: 500,
    move_ms: 0, creep: 0,
    open_wide_ms: 1500, open_push_ms: 1200, close_pull_ms: 2500,
    jingle_open_ms: 3000, jingle_sting_ms: 1500, jingle_close_ms: 3000,
    establish_every: 6, reaction_chance: 0.2, recent_window: 3,
  },
};

const STYLES = new Map<string, ShowStyle>([[GOODNIGHT.id, GOODNIGHT], [DEFAULT_NEWS.id, DEFAULT_NEWS]]);

export function registerShowStyle(style: ShowStyle): void { STYLES.set(style.id, style); }
export function getShowStyle(id: string): ShowStyle {
  const s = STYLES.get(id);
  if (!s) throw new Error(`unknown show style "${id}" (have: ${[...STYLES.keys()].join(', ')})`);
  return s;
}
export function listShowStyles(): ShowStyle[] { return [...STYLES.values()]; }

/** Derive a style with cadence/palette overrides (tuning without forking). */
export function withOverrides(base: ShowStyle, o: { id?: string; cadence?: Partial<CadenceProfile>; palette?: Partial<ShowStyle['palette']> } = {}): ShowStyle {
  return { ...base, id: o.id ?? base.id, cadence: { ...base.cadence, ...(o.cadence ?? {}) }, palette: { ...base.palette, ...(o.palette ?? {}) } };
}

/** The set.theme wire payload for a style. */
export function themePayload(s: ShowStyle): SetThemePayloadV1 {
  return {
    style: s.id,
    palette: { ...s.palette },
    fonts: { ...s.fonts },
    brand: s.brand,
    wall: { ...s.wall },
    lighting: { ...s.lighting },
    overlay: { lowerThird: s.overlay.lowerThird, ticker: { ...s.overlay.ticker }, bug: s.overlay.bug },
  };
}
