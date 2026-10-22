/**
 * Try-Not-To-Smile rules engine. Pure: (state, action) → { state, events }.
 * No clocks, no randomness, no I/O. Time arrives on every action (`t`, ms),
 * so a recorded action list replays to the identical result.
 *
 * Game: players take turns performing (agents deliver bits on the stage; the
 * human may tell their own). Everyone who is NOT performing must keep a
 * straight face. A smile above `smileThreshold` (relative to the player's
 * calibrated neutral face) held for `holdMs` is a BREAK: one strike, and every
 * `strikesPerLife` strikes cost a life. 0 lives = out (they become a
 * spectator). The performer scores a point per break they cause. Last face
 * standing wins; after `rounds` full rotations the most lives (then points) wins.
 *
 * Fairness:
 *   - scores are relative to each player's own calibrated neutral (resting smilers)
 *   - a hold must be continuous: a sample gap > maxGapMs resets it (dropped
 *     frames can't stitch two short twitches into a break)
 *   - after a break the player gets `graceMs` before another can count
 *   - when a player's camera reports bad light, their samples are ignored and
 *     they get a lighting warning (no strike for a face we can't see)
 *   - the performer is never judged during their own turn
 */
import { adjustSmile } from './calibration';

export interface TntsConfig {
  smileThreshold: number;
  holdMs: number;
  lives: number;
  strikesPerLife: number;
  turnMs: number;
  graceMs: number;
  rounds: number;
  maxGapMs: number;
  minLuminance: number;
  minPlayers: number;
}

export const DEFAULT_CONFIG: TntsConfig = {
  smileThreshold: 0.5,
  holdMs: 400,
  lives: 3,
  strikesPerLife: 1,
  turnMs: 15000,
  graceMs: 1500,
  rounds: 3,
  maxGapMs: 250,
  minLuminance: 0.18,
  minPlayers: 2,
};

export type PlayerKind = 'human' | 'agent';
export type Phase = 'lobby' | 'turn' | 'over';

export interface PlayerState {
  id: string;
  name: string;
  kind: PlayerKind;
  seat: string;
  lives: number;
  strikes: number;
  score: number;
  out: boolean;
  calibrated: boolean;
  baseline: number;
  restingSmiler: boolean;
  dark: boolean;
  /** Smile is simulated (agent affect), not measured. Always true for agents. */
  simulated: boolean;
  aboveSince: number | null;
  lastSampleAt: number | null;
  lastBreakAt: number | null;
  /** Latest adjusted smile (0..1), for the UI meter. */
  smile: number;
}

export interface TntsState {
  config: TntsConfig;
  phase: Phase;
  t: number;
  players: Record<string, PlayerState>;
  order: string[];
  spectators: Record<string, string>;
  round: number;
  turnIndex: number;
  performer: string | null;
  turnStartedAt: number;
  turnEndsAt: number;
  winner: string | null;
  breaks: Array<{ t: number; id: string; by: string | null; round: number }>;
}

export type TntsAction =
  | { type: 'join'; t: number; id: string; name: string; kind: PlayerKind; seat?: string }
  | { type: 'spectate'; t: number; id: string; name: string }
  | { type: 'leave'; t: number; id: string }
  | { type: 'calibrated'; t: number; id: string; baseline: number; restingSmiler?: boolean }
  | { type: 'start'; t: number }
  | { type: 'smile'; t: number; id: string; raw: number }
  | { type: 'lighting'; t: number; id: string; luminance: number }
  | { type: 'tick'; t: number }
  | { type: 'end_turn'; t: number };

export type TntsEvent =
  | { type: 'player.joined'; t: number; id: string; kind: PlayerKind; seat: string }
  | { type: 'player.left'; t: number; id: string }
  | { type: 'spectator.joined'; t: number; id: string }
  | { type: 'player.calibrated'; t: number; id: string; baseline: number; restingSmiler: boolean }
  | { type: 'fairness.resting_smiler'; t: number; id: string; baseline: number }
  | { type: 'game.started'; t: number; order: string[] }
  | { type: 'turn.started'; t: number; performer: string; round: number; endsAt: number }
  | { type: 'turn.ended'; t: number; performer: string; reason: 'time' | 'done' | 'performer-left' }
  | { type: 'smile.break'; t: number; id: string; by: string | null; strikes: number; lives: number; simulated: boolean }
  | { type: 'player.out'; t: number; id: string }
  | { type: 'lighting.warning'; t: number; id: string; luminance: number }
  | { type: 'lighting.ok'; t: number; id: string }
  | { type: 'game.over'; t: number; winner: string | null; standings: Array<{ id: string; lives: number; score: number }> }
  | { type: 'rejected'; t: number; action: string; reason: string };

export interface StepResult { state: TntsState; events: TntsEvent[] }

export function initialState(config: Partial<TntsConfig> = {}): TntsState {
  return {
    config: { ...DEFAULT_CONFIG, ...config },
    phase: 'lobby', t: 0, players: {}, order: [], spectators: {},
    round: 0, turnIndex: -1, performer: null, turnStartedAt: 0, turnEndsAt: 0,
    winner: null, breaks: [],
  };
}

const active = (s: TntsState): PlayerState[] => s.order.map((id) => s.players[id]).filter((p) => p && !p.out);

export function standings(s: TntsState): Array<{ id: string; lives: number; score: number }> {
  return Object.values(s.players)
    .map((p) => ({ id: p.id, lives: p.out ? 0 : p.lives, score: p.score }))
    .sort((a, b) => b.lives - a.lives || b.score - a.score || a.id.localeCompare(b.id));
}

function clone(s: TntsState): TntsState {
  const players: Record<string, PlayerState> = {};
  for (const [k, v] of Object.entries(s.players)) players[k] = { ...v };
  return { ...s, players, order: [...s.order], spectators: { ...s.spectators }, breaks: [...s.breaks] };
}

function finish(s: TntsState, t: number, ev: TntsEvent[]) {
  const st = standings(s);
  const alive = active(s);
  s.winner = alive.length === 1 ? alive[0].id : st.length && (st.length < 2 || st[0].lives !== st[1].lives || st[0].score !== st[1].score) ? st[0].id : null;
  s.phase = 'over';
  s.performer = null;
  ev.push({ type: 'game.over', t, winner: s.winner, standings: st });
}

/** Advance to the next performer who is still in; wraps into the next round. */
function nextTurn(s: TntsState, t: number, ev: TntsEvent[]) {
  if (active(s).length <= 1) return finish(s, t, ev);
  const n = s.order.length;
  let i = s.turnIndex;
  for (let k = 0; k < n; k++) {
    i = i + 1;
    if (i >= n) { i = 0; s.round += 1; }
    const p = s.players[s.order[i]];
    if (p && !p.out) break;
  }
  if (s.round > s.config.rounds) return finish(s, t, ev);
  s.turnIndex = i;
  s.performer = s.order[i];
  s.turnStartedAt = t;
  s.turnEndsAt = t + s.config.turnMs;
  for (const p of Object.values(s.players)) { p.aboveSince = null; p.smile = 0; }
  ev.push({ type: 'turn.started', t, performer: s.performer, round: s.round, endsAt: s.turnEndsAt });
}

function endTurn(s: TntsState, t: number, reason: 'time' | 'done' | 'performer-left', ev: TntsEvent[]) {
  if (s.performer) ev.push({ type: 'turn.ended', t, performer: s.performer, reason });
  nextTurn(s, t, ev);
}

export function step(prev: TntsState, a: TntsAction): StepResult {
  const s = clone(prev);
  const ev: TntsEvent[] = [];
  const reject = (reason: string): StepResult => ({ state: prev, events: [{ type: 'rejected', t: a.t, action: a.type, reason }] });
  if (a.t < s.t && a.type !== 'join' && a.type !== 'spectate') return reject('time went backwards');
  s.t = Math.max(s.t, a.t);
  const c = s.config;

  switch (a.type) {
    case 'join': {
      if (s.players[a.id]) return reject('already joined');
      if (s.phase !== 'lobby') {
        // late arrivals watch; they join the next game
        s.spectators[a.id] = a.name;
        ev.push({ type: 'spectator.joined', t: a.t, id: a.id });
        break;
      }
      const seat = a.seat ?? `seat${s.order.length + 1}`;
      s.players[a.id] = {
        id: a.id, name: a.name, kind: a.kind, seat, lives: c.lives, strikes: 0, score: 0, out: false,
        calibrated: a.kind === 'agent', baseline: 0, restingSmiler: false, dark: false,
        simulated: a.kind === 'agent', aboveSince: null, lastSampleAt: null, lastBreakAt: null, smile: 0,
      };
      s.order.push(a.id);
      ev.push({ type: 'player.joined', t: a.t, id: a.id, kind: a.kind, seat });
      break;
    }
    case 'spectate':
      s.spectators[a.id] = a.name;
      ev.push({ type: 'spectator.joined', t: a.t, id: a.id });
      break;
    case 'leave': {
      if (s.spectators[a.id]) { delete s.spectators[a.id]; ev.push({ type: 'player.left', t: a.t, id: a.id }); break; }
      const p = s.players[a.id];
      if (!p) return reject('not in game');
      if (s.phase === 'lobby') { delete s.players[a.id]; s.order = s.order.filter((x) => x !== a.id); }
      else p.out = true;
      ev.push({ type: 'player.left', t: a.t, id: a.id });
      if (s.phase === 'turn') {
        if (s.performer === a.id) endTurn(s, a.t, 'performer-left', ev);
        else if (active(s).length <= 1) finish(s, a.t, ev);
      }
      break;
    }
    case 'calibrated': {
      const p = s.players[a.id];
      if (!p) return reject('not in game');
      p.calibrated = true;
      p.baseline = a.baseline;
      p.restingSmiler = !!a.restingSmiler;
      ev.push({ type: 'player.calibrated', t: a.t, id: a.id, baseline: a.baseline, restingSmiler: p.restingSmiler });
      if (p.restingSmiler) ev.push({ type: 'fairness.resting_smiler', t: a.t, id: a.id, baseline: a.baseline });
      break;
    }
    case 'start': {
      if (s.phase !== 'lobby') return reject('already started');
      if (s.order.length < c.minPlayers) return reject(`need ${c.minPlayers} players`);
      const uncal = s.order.filter((id) => !s.players[id].calibrated);
      if (uncal.length) return reject(`not calibrated: ${uncal.join(',')}`);
      s.phase = 'turn';
      s.round = 1;
      s.turnIndex = -1;
      ev.push({ type: 'game.started', t: a.t, order: [...s.order] });
      // turnIndex -1 → first player; nextTurn's wrap bumps round only when passing the end
      nextTurn(s, a.t, ev);
      break;
    }
    case 'lighting': {
      const p = s.players[a.id];
      if (!p) return reject('not in game');
      const dark = a.luminance < c.minLuminance;
      if (dark && !p.dark) ev.push({ type: 'lighting.warning', t: a.t, id: a.id, luminance: a.luminance });
      if (!dark && p.dark) ev.push({ type: 'lighting.ok', t: a.t, id: a.id });
      p.dark = dark;
      if (dark) p.aboveSince = null;
      break;
    }
    case 'smile': {
      const p = s.players[a.id];
      if (!p) return reject('not in game');
      const adj = adjustSmile(a.raw, p.baseline);
      p.smile = adj;
      const gap = p.lastSampleAt === null ? Infinity : a.t - p.lastSampleAt;
      p.lastSampleAt = a.t;
      if (s.phase !== 'turn' || p.out || s.performer === p.id || p.dark) { p.aboveSince = null; break; }
      if (gap > c.maxGapMs) p.aboveSince = null;
      if (adj <= c.smileThreshold) { p.aboveSince = null; break; }
      if (p.aboveSince === null) p.aboveSince = a.t;
      const inGrace = p.lastBreakAt !== null && a.t - p.lastBreakAt < c.graceMs;
      if (a.t - p.aboveSince >= c.holdMs && !inGrace) {
        p.strikes += 1;
        if (p.strikes % c.strikesPerLife === 0) p.lives -= 1;
        p.lastBreakAt = a.t;
        p.aboveSince = null;
        const by = s.performer;
        if (by && s.players[by]) s.players[by].score += 1;
        s.breaks.push({ t: a.t, id: p.id, by, round: s.round });
        ev.push({ type: 'smile.break', t: a.t, id: p.id, by, strikes: p.strikes, lives: Math.max(0, p.lives), simulated: p.simulated });
        if (p.lives <= 0) {
          p.out = true;
          p.lives = 0;
          ev.push({ type: 'player.out', t: a.t, id: p.id });
          if (active(s).length <= 1) finish(s, a.t, ev);
        }
      }
      break;
    }
    case 'tick':
      if (s.phase === 'turn' && a.t >= s.turnEndsAt) endTurn(s, a.t, 'time', ev);
      break;
    case 'end_turn':
      if (s.phase !== 'turn') return reject('no turn running');
      endTurn(s, a.t, 'done', ev);
      break;
  }
  return { state: s, events: ev };
}

/** Fold a list of actions. */
export function replay(actions: TntsAction[], config: Partial<TntsConfig> = {}): { state: TntsState; events: TntsEvent[] } {
  let state = initialState(config);
  const events: TntsEvent[] = [];
  for (const a of actions) { const r = step(state, a); state = r.state; events.push(...r.events); }
  return { state, events };
}
