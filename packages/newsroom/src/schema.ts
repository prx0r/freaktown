/**
 * Newsroom rundown — the authoring format for a news show.
 *
 * Modelled on Sofie (NRK / SuperFly.tv open-source broadcast automation):
 *
 *   Sofie      Rundown  → Segment  → Part   → Piece
 *   newsroom   Show     → Segment  → Story  → Piece
 *              (rundown)  (section)  (part)   (anchor read, wall graphic, …)
 *
 * A segment is a section of the show ("around the world", "the numbers").
 * A story is one item inside it (Sofie's part: the unit the director takes).
 * Pieces are the things that happen inside a story, in order: reads (which
 * own time) and graphics/cues (which fire at the start of the next read, or
 * at the story start when nothing follows).
 *
 * Pure data + a dependency-free validator (no zod/ajv: the workspace keeps
 * packages dependency-light). JSON Schema id: freaktown.newsroom.rundown/v1.
 */

export const RUNDOWN_SCHEMA = 'freaktown.newsroom.rundown/v1' as const;

/** One measured word, relative to the start of its line (face layer format). */
export interface WordTiming { word: string; start_ms: number; end_ms: number }

export type LicenseLane = 'verbatim-ok' | 'fact-rewrite' | 'unknown' | (string & {});

export interface SourceRef { name: string; url?: string; license?: LicenseLane }

export interface AnchorChair {
  /** Chair id ("anchor"). Reads name a chair; the chair names a seat. */
  chair: string;
  name: string;
  /** Seat on the set ("anchor1"). */
  seat: string;
  character_id?: string;
  /** "basic" | avatars/<x>.vrm | GLB url. */
  avatar_url?: string;
}

export interface ReporterChair {
  /** Chair id ("reporter:en-ke"). */
  chair: string;
  name: string;
  /** Locale tag ("EN-KE"). */
  locale: string;
  /** "remote" (default): shown on the wall + lower third. "studio": sits in `seat`. */
  presence?: 'remote' | 'studio';
  seat?: string;
  avatar_url?: string;
}

export interface CastV1 {
  anchors: AnchorChair[];
  reporters?: ReporterChair[];
}

interface PieceBase { id?: string }

export interface AnchorReadPiece extends PieceBase {
  type: 'anchor_read';
  /** Anchor chair id (defaults to the first anchor). */
  chair?: string;
  text: string;
  /** Measured words for this line (relative ms). Overrides estimates. */
  words?: WordTiming[];
  emotion?: string;
  /** Marks a line that carries the story's figure (fires the numbers graphic). */
  numbers?: { figure: string; label?: string };
}

export interface ReporterReadPiece extends PieceBase {
  type: 'reporter_read';
  chair: string;
  /** Reporter display name + locale (copied from the chair when omitted). */
  name?: string;
  locale?: string;
  country?: string;
  text: string;
  words?: WordTiming[];
  numbers?: { figure: string; label?: string };
}

export type WallLayout = 'headline' | 'country' | 'numbers' | 'title' | 'close';

export interface WallPiece extends PieceBase {
  type: 'wall';
  layout?: WallLayout;
  headline: string;
  kicker?: string;
  body?: string;
  figure?: string;
  /** Optional image (drawn only when the licence lane allows it: see imageAllowed()). */
  image_url?: string;
  image_license?: LicenseLane;
  credit?: string;
}

export interface LowerThirdPiece extends PieceBase { type: 'lower_third'; name: string; title?: string; hide?: boolean }
export interface TickerPiece extends PieceBase { type: 'ticker'; items: string[] }
export interface JinglePiece extends PieceBase { type: 'jingle'; kind: 'open' | 'sting' | 'close'; asset?: string; duration_ms?: number }
/** Over-the-shoulder box (OTS): a small graphic beside the anchor. Rendered as a wall card. */
export interface OtsPiece extends PieceBase { type: 'ots'; text: string; kicker?: string }

export type Piece = AnchorReadPiece | ReporterReadPiece | WallPiece | LowerThirdPiece | TickerPiece | JinglePiece | OtsPiece;
export type ReadPiece = AnchorReadPiece | ReporterReadPiece;
export const isRead = (p: Piece): p is ReadPiece => p.type === 'anchor_read' || p.type === 'reporter_read';

export interface StoryV1 {
  id: string;
  title?: string;
  country?: string;
  source?: SourceRef;
  pieces: Piece[];
}

export type SegmentKind = 'open' | 'section' | 'close';

export interface SegmentV1 {
  id: string;
  title: string;
  kind: SegmentKind;
  stories: StoryV1[];
}

export interface RundownV1 {
  schema: typeof RUNDOWN_SCHEMA;
  id: string;
  title: string;
  /** Show style id ("goodnight", "default-news"). */
  show_style: string;
  /** Set id; defaults to the style's set (news-studio). */
  set?: string;
  date?: string;
  cast: CastV1;
  segments: SegmentV1[];
  /** Free metadata from the adapter (episode no., source files, flags). */
  meta?: Record<string, unknown>;
}

// ── validation ────────────────────────────────────────────────────────

export interface ValidationResult { ok: boolean; errors: string[] }

const PIECE_TYPES = ['anchor_read', 'reporter_read', 'wall', 'lower_third', 'ticker', 'jingle', 'ots'];
const LAYOUTS = ['headline', 'country', 'numbers', 'title', 'close'];

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const isStr = (x: unknown): x is string => typeof x === 'string' && x.trim().length > 0;

function checkWords(words: unknown, at: string, err: (m: string) => void): void {
  if (words === undefined) return;
  if (!Array.isArray(words)) return err(`${at}.words must be an array`);
  let prev = -1;
  words.forEach((w, i) => {
    if (!isObj(w) || !isStr(w.word) || typeof w.start_ms !== 'number' || typeof w.end_ms !== 'number') return err(`${at}.words[${i}] needs {word,start_ms,end_ms}`);
    if (w.end_ms < w.start_ms) err(`${at}.words[${i}] ends before it starts`);
    if (w.start_ms < prev) err(`${at}.words[${i}] is out of order`);
    prev = w.start_ms;
  });
}

/** Structural validation of a rundown. Never throws; returns every problem found. */
export function validateRundown(x: unknown): ValidationResult {
  const errors: string[] = [];
  const err = (m: string) => { errors.push(m); };
  if (!isObj(x)) return { ok: false, errors: ['rundown must be an object'] };
  if (x.schema !== RUNDOWN_SCHEMA) err(`schema must be "${RUNDOWN_SCHEMA}"`);
  if (!isStr(x.id)) err('id is required');
  if (!isStr(x.title)) err('title is required');
  if (!isStr(x.show_style)) err('show_style is required');
  const anchors = new Set<string>();
  const reporters = new Set<string>();
  if (!isObj(x.cast)) err('cast is required');
  else {
    const c = x.cast;
    if (!Array.isArray(c.anchors) || c.anchors.length === 0) err('cast.anchors needs at least one anchor');
    else c.anchors.forEach((a, i) => {
      if (!isObj(a) || !isStr(a.chair) || !isStr(a.name) || !isStr(a.seat)) return err(`cast.anchors[${i}] needs chair, name, seat`);
      anchors.add(a.chair);
    });
    if (c.reporters !== undefined) {
      if (!Array.isArray(c.reporters)) err('cast.reporters must be an array');
      else c.reporters.forEach((r, i) => {
        if (!isObj(r) || !isStr(r.chair) || !isStr(r.name) || !isStr(r.locale)) return err(`cast.reporters[${i}] needs chair, name, locale`);
        if (r.presence === 'studio' && !isStr(r.seat)) err(`cast.reporters[${i}] in the studio needs a seat`);
        reporters.add(r.chair);
      });
    }
  }
  if (!Array.isArray(x.segments) || x.segments.length === 0) { err('segments needs at least one segment'); return { ok: false, errors }; }
  const ids = new Set<string>();
  let reads = 0;
  x.segments.forEach((s, si) => {
    const at = `segments[${si}]`;
    if (!isObj(s)) return err(`${at} must be an object`);
    if (!isStr(s.id)) err(`${at}.id is required`);
    else if (ids.has(s.id)) err(`${at}.id "${s.id}" is duplicated`); else ids.add(s.id);
    if (!isStr(s.title)) err(`${at}.title is required`);
    if (!['open', 'section', 'close'].includes(String(s.kind))) err(`${at}.kind must be open|section|close`);
    if (!Array.isArray(s.stories)) return err(`${at}.stories must be an array`);
    s.stories.forEach((st, ti) => {
      const sat = `${at}.stories[${ti}]`;
      if (!isObj(st)) return err(`${sat} must be an object`);
      if (!isStr(st.id)) err(`${sat}.id is required`);
      else if (ids.has(st.id)) err(`${sat}.id "${st.id}" is duplicated`); else ids.add(st.id);
      if (st.source !== undefined && (!isObj(st.source) || !isStr(st.source.name))) err(`${sat}.source needs a name`);
      if (!Array.isArray(st.pieces) || st.pieces.length === 0) return err(`${sat}.pieces needs at least one piece`);
      st.pieces.forEach((p, pi) => {
        const pat = `${sat}.pieces[${pi}]`;
        if (!isObj(p) || !PIECE_TYPES.includes(String(p.type))) return err(`${pat}.type must be one of ${PIECE_TYPES.join('|')}`);
        switch (p.type) {
          case 'anchor_read':
            reads++;
            if (!isStr(p.text)) err(`${pat}.text is required`);
            if (p.chair !== undefined && !anchors.has(String(p.chair))) err(`${pat}.chair "${String(p.chair)}" is not an anchor in cast`);
            checkWords(p.words, pat, err);
            break;
          case 'reporter_read':
            reads++;
            if (!isStr(p.text)) err(`${pat}.text is required`);
            if (!isStr(p.chair) || !reporters.has(p.chair)) err(`${pat}.chair "${String(p.chair)}" is not a reporter in cast`);
            checkWords(p.words, pat, err);
            break;
          case 'wall':
            if (!isStr(p.headline)) err(`${pat}.headline is required`);
            if (p.layout !== undefined && !LAYOUTS.includes(String(p.layout))) err(`${pat}.layout must be ${LAYOUTS.join('|')}`);
            if (p.layout === 'numbers' && !isStr(p.figure)) err(`${pat}: a numbers card needs a figure`);
            break;
          case 'lower_third':
            if (!isStr(p.name)) err(`${pat}.name is required`);
            break;
          case 'ticker':
            if (!Array.isArray(p.items) || !p.items.every(isStr)) err(`${pat}.items must be non-empty strings`);
            break;
          case 'jingle':
            if (!['open', 'sting', 'close'].includes(String(p.kind))) err(`${pat}.kind must be open|sting|close`);
            break;
          case 'ots':
            if (!isStr(p.text)) err(`${pat}.text is required`);
            break;
        }
      });
    });
  });
  if (reads === 0) err('rundown has no reads (anchor_read / reporter_read)');
  return { ok: errors.length === 0, errors };
}

/** Throws with every validation error when the rundown is malformed. */
export function assertRundown(x: unknown): asserts x is RundownV1 {
  const r = validateRundown(x);
  if (!r.ok) throw new Error(`invalid rundown:\n  - ${r.errors.join('\n  - ')}`);
}

/**
 * Licence-lane gate for wall images. Only `verbatim-ok` sources (public-domain
 * / open re-use: NASA, ESA, UN, OGL…) may show their image; © news
 * (`fact-rewrite`) and unknown lanes get the procedural card only.
 */
export function imageAllowed(lane: LicenseLane | undefined): boolean {
  return lane === 'verbatim-ok';
}
