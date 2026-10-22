/**
 * TntsGame — one Try-Not-To-Smile table: a human (or several) vs agent players.
 *
 * Drives the pure rules engine (rules.ts) on an injected clock:
 *   - agent turns: plan a bit → stage cues (dialogue lines, camera, faces)
 *   - every listener reacts at the punchline: humans by their measured face
 *     (samples pushed in with humanSmile), agents by their simulated curve
 *     (taste.ts), sampled every 50 ms into the same rules
 *   - human turns: the human tells a bit and taps "punchline"; agents react
 *
 * Output: TntsEvents (rules) + StageCues (for SetEventExecutor). Deterministic
 * for a given seed + input sequence: the tests and the render rely on that.
 */
import { AgentPlayer, EMOTION_FOR, humanJoke, type TurnPlan } from './agents';
import { getPartyIdentity, type PartyIdentity } from './identity';
import { mulberry32, type Rng } from './rng';
import { initialState, step, type TntsAction, type TntsConfig, type TntsEvent, type TntsState } from './rules';
import { curveAt, type SmileCurve } from './taste';
import type { JokeSource } from './jokes';

export interface StageCue { t: number; type: string; payload: Record<string, unknown> }

export interface TntsGameOptions {
  seed?: string;
  config?: Partial<TntsConfig>;
  /** Agent identity ids (resident pog.* or agent-made), seated in order. */
  agents: string[];
  sources?: JokeSource[];
  /** Set the agents sit at (podcast: 4 seats around a table). */
  setId?: string;
}

const SAMPLE_MS = 50;

export class TntsGame {
  state: TntsState;
  readonly log: TntsEvent[] = [];
  readonly cues: StageCue[] = [];
  readonly agents = new Map<string, AgentPlayer>();
  private rng: Rng;
  private used = new Set<string>();
  private plan: TurnPlan | null = null;
  private planCursor = 0;
  private curves = new Map<string, { curve: SmileCurve; punchAt: number; shownPeak: boolean }>();
  private lastAgentSample = -Infinity;
  private humanBits = 0;
  private humanPunchAt: number | null = null;
  private listeners: Array<(e: TntsEvent) => void> = [];
  private cueListeners: Array<(c: StageCue) => void> = [];
  readonly setId: string;

  constructor(private opts: TntsGameOptions) {
    this.rng = mulberry32(opts.seed ?? 'tnts');
    this.state = initialState(opts.config);
    this.setId = opts.setId ?? 'podcast';
    opts.agents.forEach((id) => {
      const idn = getPartyIdentity(id);
      if (!idn) throw new Error(`unknown identity ${id}`);
      this.agents.set(id, new AgentPlayer(idn, opts.sources));
    });
  }

  on(fn: (e: TntsEvent) => void): () => void { this.listeners.push(fn); return () => { this.listeners = this.listeners.filter((x) => x !== fn); }; }
  onCue(fn: (c: StageCue) => void): () => void { this.cueListeners.push(fn); return () => { this.cueListeners = this.cueListeners.filter((x) => x !== fn); }; }

  identity(id: string): PartyIdentity | undefined { return this.agents.get(id)?.identity; }

  private cue(c: StageCue) { this.cues.push(c); for (const f of this.cueListeners) f(c); }

  dispatch(a: TntsAction): TntsEvent[] {
    const r = step(this.state, a);
    this.state = r.state;
    for (const e of r.events) { this.log.push(e); for (const f of this.listeners) f(e); this.onEvent(e); }
    return r.events;
  }

  /** Seat the agents + one or more humans, then cast the set. */
  seat(humans: Array<{ id: string; name: string }>, t = 0): void {
    let i = 1;
    for (const a of this.agents.values()) this.dispatch({ type: 'join', t, id: a.id, name: a.identity.name, kind: 'agent', seat: `seat${i++}` });
    for (const h of humans) this.dispatch({ type: 'join', t, id: h.id, name: h.name, kind: 'human', seat: `seat${i++}` });
    const cast = Object.values(this.state.players).map((p) => ({
      seat: p.seat, character_id: p.id, name: p.name,
      avatar_url: p.kind === 'agent' ? this.agents.get(p.id)!.identity.look.avatar_url : 'basic',
      kind: p.kind === 'agent' ? 'character' : 'human',
    }));
    this.cue({ t, type: 'set.load', payload: { setId: this.setId, title: 'Try Not To Smile', cast } });
    this.cue({ t, type: 'set.camera', payload: { cue: 'wide' } });
  }

  calibrated(id: string, baseline: number, restingSmiler: boolean, t: number) { this.dispatch({ type: 'calibrated', t, id, baseline, restingSmiler }); }
  start(t: number) { return this.dispatch({ type: 'start', t }); }
  humanSmile(id: string, raw: number, t: number) { return this.dispatch({ type: 'smile', t, id, raw }); }
  lighting(id: string, luminance: number, t: number) { return this.dispatch({ type: 'lighting', t, id, luminance }); }

  /** The human performer finished a bit (taps "punchline"): agents react now. */
  humanPunchline(t: number, text?: string) {
    const perf = this.state.performer;
    if (!perf || this.state.players[perf]?.kind !== 'human') return;
    if (this.humanPunchAt !== null) return;
    this.humanPunchAt = t;
    const joke = humanJoke(++this.humanBits, text);
    this.scheduleReactions(joke, t);
    this.cue({ t, type: 'set.camera', payload: { cue: 'wide' } });
  }

  private scheduleReactions(joke: TurnPlan['joke'], punchAt: number) {
    this.curves.clear();
    for (const a of this.agents.values()) {
      const p = this.state.players[a.id];
      if (!p || p.out || this.state.performer === a.id) continue;
      this.curves.set(a.id, { curve: a.react(joke, this.rng), punchAt, shownPeak: false });
    }
  }

  private onEvent(e: TntsEvent) {
    if (e.type === 'turn.started') {
      this.plan = null; this.planCursor = 0; this.curves.clear(); this.humanPunchAt = null;
      const perf = this.state.players[e.performer];
      this.cue({ t: e.t, type: 'set.camera', payload: { cue: `${perf.seat}-single` } });
      const agent = this.agents.get(e.performer);
      if (agent) {
        this.plan = agent.planTurn(e.t, this.rng, this.used);
        this.scheduleReactions(this.plan.joke, this.plan.punchEndsAt);
      }
    } else if (e.type === 'smile.break') {
      const p = this.state.players[e.id];
      if (p) this.cue({ t: e.t, type: 'face.expression', payload: { seat: p.seat, emotion: 'happy', intensity: 1, duration_ms: 1600 } });
      this.cue({ t: e.t, type: 'set.camera', payload: { cue: `${p?.seat ?? 'wide'}-single` } });
    } else if (e.type === 'game.over') {
      this.cue({ t: e.t, type: 'set.camera', payload: { cue: 'wide' } });
    }
  }

  /** Advance the table to time t (call every frame, or in a loop in tests). */
  update(t: number): void {
    if (this.state.phase !== 'turn') return;
    // 1. performer's planned lines → stage
    if (this.plan) {
      while (this.planCursor < this.plan.lines.length && this.plan.lines[this.planCursor].t <= t) {
        const l = this.plan.lines[this.planCursor++];
        const seat = this.state.players[this.state.performer!].seat;
        this.cue({ t: l.t, type: 'dialogue.line', payload: { seat, text: l.text, duration_ms: l.duration_ms, emotion: EMOTION_FOR[l.delivery], delivery: l.delivery, role: l.role } });
      }
    }
    // 2. simulated agent smiles → rules (same path as a measured human)
    if (t - this.lastAgentSample >= SAMPLE_MS) {
      this.lastAgentSample = t;
      for (const [id, c] of this.curves) {
        if (this.state.phase !== 'turn') break;
        const level = curveAt(c.curve, t - c.punchAt);
        const p = this.state.players[id];
        if (!p || p.out) continue;
        if (level > 0 && !c.shownPeak && level >= c.curve.peak) {
          c.shownPeak = true;
          this.cue({ t, type: 'face.expression', payload: { seat: p.seat, emotion: 'happy', intensity: c.curve.peak, duration_ms: c.curve.hold_ms, simulated: true } });
        }
        this.dispatch({ type: 'smile', t, id, raw: level });
      }
    }
    if (this.state.phase !== 'turn') return;
    // 3. turn end: the agent's bit is over, or the clock ran out
    if (this.plan && t >= this.plan.endsAt) { this.dispatch({ type: 'end_turn', t }); return; }
    if (!this.plan && this.humanPunchAt !== null && t >= this.humanPunchAt + 3500) { this.dispatch({ type: 'end_turn', t }); return; }
    this.dispatch({ type: 'tick', t });
  }

  /** Run without a browser: humans supply their smile via `humanAt(id, t)`. */
  simulate(humanAt: (id: string, t: number) => number, opts: { from?: number; until?: number; stepMs?: number; humanPunchAfterMs?: number } = {}): void {
    const stepMs = opts.stepMs ?? SAMPLE_MS;
    const until = opts.until ?? 10 * 60_000;
    const punched = new Set<number>();
    for (let t = opts.from ?? 0; t <= until && this.state.phase === 'turn'; t += stepMs) {
      for (const p of Object.values(this.state.players)) if (p.kind === 'human' && !p.out) this.humanSmile(p.id, humanAt(p.id, t), t);
      const perf = this.state.performer;
      if (perf && this.state.players[perf]?.kind === 'human' && !punched.has(this.state.turnStartedAt) && t - this.state.turnStartedAt >= (opts.humanPunchAfterMs ?? 4000)) {
        punched.add(this.state.turnStartedAt);
        this.humanPunchline(t);
      }
      this.update(t);
    }
  }
}
