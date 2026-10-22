/**
 * Sketch script — the authoring format for a performed sketch in any set.
 *
 *   SketchScriptV1  →  scenes[]  →  beats[]  →  items[] (lines + stage directions)
 *
 * A sketch is a cast of persistent identities (the `pog.*` ids of
 * assets/character-meshes/cast, or any id with an inline name/avatar) put on
 * seats/marks of a set, and a sequence of beats. A beat is the comedy unit
 * (setup → game → escalation → turn → punch → button); items inside a beat
 * run in order on one clock. Lines own time; most directions overlap the
 * next line; pause / hold_for_laugh (and move with wait) own time too.
 *
 * Pure data + a dependency-free validator (same doctrine as the newsroom
 * rundown). JSON Schema id: funnier.sketch/v1.
 */

export const SKETCH_SCHEMA = 'funnier.sketch/v1' as const;

export type BeatKind = 'setup' | 'game' | 'escalation' | 'turn' | 'punch' | 'button' | 'scene';

export type ReactionKind = 'smirk' | 'eye-roll' | 'shock' | 'deadpan' | 'laugh-break';
export const REACTION_KINDS: readonly ReactionKind[] = ['smirk', 'eye-roll', 'shock', 'deadpan', 'laugh-break'];

export type GestureKind = 'point' | 'shrug' | 'open' | 'wave' | 'nod' | 'lean-in' | 'lean-back' | 'slump' | 'freeze';
export const GESTURE_KINDS: readonly GestureKind[] = ['point', 'shrug', 'open', 'wave', 'nod', 'lean-in', 'lean-back', 'slump', 'freeze'];

/**
 * Look target: a cast role, "camera", "audience", "up", "down",
 * "prop:<name>" (wall, table, board, cards, pot, desk) or a world point.
 */
export type LookTarget = string | { point: [number, number, number] };

export interface CastEntry {
  /** Role id used by lines/directions ("anchor", "dealer"). */
  role: string;
  /** Persistent identity ("pog.doug-deadline") or any stable id ("guest.wren"). */
  identity: string;
  /** Seat / mark id on the set where the character starts ("anchor1", "seat3"). */
  seat: string;
  /** Display name (defaults to the identity's registered name). */
  name?: string;
  /** "basic" | "basic:robot" | avatars/<x>.vrm | GLB url (defaults to a BASIC body). */
  avatar_url?: string;
}

/**
 * Timing anchor for a direction (lines are always sequential):
 *   (default)       at the cursor: after the previous item, overlapping what follows
 *   during: "prev"  inside the previous line — at `at_word` (0-based) or `offset_ms` from its start,
 *                   or `from_end_ms` before its end
 */
export interface Anchor {
  during?: 'prev';
  at_word?: number;
  offset_ms?: number;
  from_end_ms?: number;
}

export interface LineItem { type: 'line'; who: string; text: string; emotion?: string; id?: string; /** Addressee: a role, "camera" or "audience" (default: the previous speaker if they spoke within ~6 s, else the room). */ to?: string; /** Measured words relative to line start (overrides the estimate). */ words?: Array<{ word: string; start_ms: number; end_ms: number }> }
export interface LookItem extends Anchor { type: 'look'; who: string; at: LookTarget; ms?: number; double_take?: boolean }
export interface ReactItem extends Anchor { type: 'react'; who: string; kind: ReactionKind; ms?: number }
export interface PauseItem { type: 'pause'; ms: number }
export interface HoldItem { type: 'hold_for_laugh'; ms?: number }
export interface MoveItem extends Anchor { type: 'move'; who: string; to: string; ms?: number; wait?: boolean }
export interface GestureItem extends Anchor { type: 'gesture'; who: string; kind: GestureKind; ms?: number; intensity?: number }
export interface HeadlineItem extends Anchor { type: 'headline'; text: string; kicker?: string; layout?: string; body?: string; figure?: string }
/** Raw set event passthrough for set-specific props (poker.deal, poker.board, overlay.lower_third …). */
export interface PropItem extends Anchor { type: 'prop'; event: string; payload: Record<string, unknown> }
/** Manual camera override for this moment (any set cue; "ots:a>b" / "two-shot:a+b" may use roles). */
export interface CameraItem extends Anchor { type: 'camera'; cue: string; hold_ms?: number }
export interface ButtonItem { type: 'button' }
export interface BlackoutItem { type: 'blackout'; fade_ms?: number; delay_ms?: number }

export type SketchItem = LineItem | LookItem | ReactItem | PauseItem | HoldItem | MoveItem | GestureItem | HeadlineItem | PropItem | CameraItem | ButtonItem | BlackoutItem;
export type DirectionItem = Exclude<SketchItem, LineItem>;

export interface Beat {
  id: string;
  kind: BeatKind;
  /** One-line note for writers (not performed). */
  note?: string;
  items: SketchItem[];
}

export interface Scene { id: string; title?: string; beats: Beat[] }

export interface SketchScriptV1 {
  schema: typeof SKETCH_SCHEMA;
  id: string;
  title: string;
  /** Set id from the stage registry ("news-studio", "poker-table", "podcast", "comedy-club"). */
  set: string;
  premise?: string;
  /** The game of the scene in one sentence (what escalates). */
  game?: string;
  /** Fiction disclaimer / credits shown nowhere on stage, kept with the script. */
  credits?: string;
  cast: CastEntry[];
  scenes: Scene[];
  /** Per-script timing overrides (see SketchTiming). */
  timing?: Partial<SketchTiming>;
  /** Show-style id for news sets (newsroom styles), optional. */
  style?: string;
}

/** The knobs a writer/director tunes. Defaults: DEFAULT_SKETCH_TIMING. */
export interface SketchTiming {
  /** Estimated speech rate when lines carry no measured words. */
  wpm: number;
  /** Gap between consecutive lines (ms). Cross-talk = negative not supported. */
  line_gap_ms: number;
  /** Extra gap at a beat boundary (ms). */
  beat_gap_ms: number;
  /** Default hold_for_laugh (ms) when the item gives none. */
  laugh_hold_ms: number;
  /** Default look duration (ms). */
  look_ms: number;
  /** Double-take: first glance, look-away, then the snap back (ms). */
  double_take: { glance_ms: number; away_ms: number; hold_ms: number };
  /** Reaction delay when the identity has none (ms); identity motion-style wins. */
  react_delay_ms: number;
  /** Default reaction duration (ms). */
  react_ms: number;
  /** Default move-to duration (ms). */
  move_ms: number;
  /** Gaze life: chance per listener per line of an idle glance away, and its length. */
  idle_glance_chance: number;
  idle_glance_ms: number;
  /** Chance a listener gives a micro nod during a line. */
  nod_chance: number;
  /** Speaker glances at the camera on a turn/punch beat. */
  camera_glance_on_turn: boolean;
}

export const DEFAULT_SKETCH_TIMING: SketchTiming = {
  wpm: 165,
  line_gap_ms: 260,
  beat_gap_ms: 380,
  laugh_hold_ms: 1400,
  look_ms: 1400,
  double_take: { glance_ms: 320, away_ms: 520, hold_ms: 1300 },
  react_delay_ms: 220,
  react_ms: 1500,
  move_ms: 1400,
  idle_glance_chance: 0.22,
  idle_glance_ms: 700,
  nod_chance: 0.35,
  camera_glance_on_turn: true,
};

// ── validation ─────────────────────────────────────────────────────────

export class SketchError extends Error {}

const ITEM_TYPES = new Set(['line', 'look', 'react', 'pause', 'hold_for_laugh', 'move', 'gesture', 'headline', 'prop', 'camera', 'button', 'blackout']);
const NON_ROLE_TARGETS = new Set(['camera', 'audience', 'up', 'down']);

/** Throws SketchError listing every problem found (not just the first). */
export function assertSketch(s: unknown): asserts s is SketchScriptV1 {
  const errs = validateSketch(s);
  if (errs.length) throw new SketchError(`invalid sketch:\n  - ${errs.join('\n  - ')}`);
}

export function validateSketch(x: unknown): string[] {
  const e: string[] = [];
  const s = x as Partial<SketchScriptV1>;
  if (!s || typeof s !== 'object') return ['not an object'];
  if (s.schema !== SKETCH_SCHEMA) e.push(`schema must be "${SKETCH_SCHEMA}"`);
  if (!s.id || !/^[a-z0-9][a-z0-9-]*$/.test(s.id)) e.push('id: lowercase slug required');
  if (!s.title) e.push('title required');
  if (!s.set) e.push('set required');
  if (!Array.isArray(s.cast) || !s.cast.length) { e.push('cast: at least one member'); return e; }
  const roles = new Set<string>();
  const seats = new Set<string>();
  for (const c of s.cast) {
    if (!c.role) e.push('cast: role required');
    if (!c.identity) e.push(`cast ${c.role}: identity required`);
    if (!c.seat) e.push(`cast ${c.role}: seat required`);
    if (roles.has(c.role)) e.push(`cast: duplicate role "${c.role}"`);
    if (seats.has(c.seat)) e.push(`cast: two members on seat "${c.seat}"`);
    roles.add(c.role); seats.add(c.seat);
  }
  if (!Array.isArray(s.scenes) || !s.scenes.length) { e.push('scenes: at least one'); return e; }
  const beatIds = new Set<string>();
  let lines = 0;
  let ended = false;
  const role = (where: string, r: unknown) => { if (typeof r !== 'string' || !roles.has(r)) e.push(`${where}: unknown role "${String(r)}"`); };
  for (const sc of s.scenes) {
    if (!sc.id) e.push('scene: id required');
    if (!Array.isArray(sc.beats) || !sc.beats.length) { e.push(`scene ${sc.id}: at least one beat`); continue; }
    for (const b of sc.beats) {
      if (!b.id) e.push(`scene ${sc.id}: beat id required`);
      if (beatIds.has(b.id)) e.push(`duplicate beat id "${b.id}"`);
      beatIds.add(b.id);
      if (!Array.isArray(b.items)) { e.push(`beat ${b.id}: items[] required`); continue; }
      let prevIsLine = false;
      b.items.forEach((it, i) => {
        const w = `beat ${b.id} item ${i} (${(it as { type?: string })?.type})`;
        if (!it || !ITEM_TYPES.has((it as SketchItem).type)) { e.push(`${w}: unknown type`); return; }
        if (ended) e.push(`${w}: nothing may follow the blackout`);
        const a = it as Anchor;
        if (a.during === 'prev' && !prevIsLine) e.push(`${w}: during:"prev" needs a line right before it`);
        switch (it.type) {
          case 'line':
            role(w, it.who);
            if (!it.text || !it.text.trim()) e.push(`${w}: text required`);
            if (it.to !== undefined && it.to !== 'camera' && it.to !== 'audience' && !roles.has(it.to)) e.push(`${w}: to must be a role, camera or audience`);
            lines++;
            break;
          case 'look':
            role(w, it.who);
            if (typeof it.at === 'string') {
              if (!NON_ROLE_TARGETS.has(it.at) && !it.at.startsWith('prop:') && !roles.has(it.at)) e.push(`${w}: look target "${it.at}" is not a role, camera, audience, up, down or prop:<name>`);
              if (it.at === it.who) e.push(`${w}: a character cannot look at itself`);
            } else if (!it.at || !Array.isArray(it.at.point) || it.at.point.length !== 3) e.push(`${w}: look target point must be [x,y,z]`);
            break;
          case 'react':
            role(w, it.who);
            if (!REACTION_KINDS.includes(it.kind)) e.push(`${w}: reaction kind must be one of ${REACTION_KINDS.join(', ')}`);
            break;
          case 'pause':
            if (!(it.ms > 0)) e.push(`${w}: ms > 0 required`);
            break;
          case 'hold_for_laugh':
            if (it.ms !== undefined && !(it.ms > 0)) e.push(`${w}: ms must be > 0`);
            break;
          case 'move':
            role(w, it.who);
            if (!it.to) e.push(`${w}: to (mark/seat id) required`);
            break;
          case 'gesture':
            role(w, it.who);
            if (!GESTURE_KINDS.includes(it.kind)) e.push(`${w}: gesture kind must be one of ${GESTURE_KINDS.join(', ')}`);
            break;
          case 'headline':
            if (!it.text) e.push(`${w}: text required`);
            break;
          case 'prop':
            if (!it.event || typeof it.payload !== 'object') e.push(`${w}: event + payload required`);
            break;
          case 'camera':
            if (!it.cue) e.push(`${w}: cue required`);
            break;
          case 'blackout':
            ended = true;
            break;
        }
        prevIsLine = it.type === 'line' ? true : a.during === 'prev' ? prevIsLine : false;
      });
    }
  }
  if (!lines) e.push('a sketch needs at least one line');
  return e;
}

export const isLine = (i: SketchItem): i is LineItem => i.type === 'line';
