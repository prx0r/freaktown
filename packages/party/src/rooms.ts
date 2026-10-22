/**
 * Always-on rooms. A room is a set with agent RESIDENTS who keep the room
 * going whether or not anyone is watching; humans can take a free seat (a
 * resident yields theirs when the room is full) and leave again.
 *
 *   podcast   residents riff on a rotating topic (original deck + templates), react honestly (taste)
 *   newsroom  two resident anchors read original satirical headlines on the wall
 *   poker     a dealer (PokerDealer / poker-ts) deals hands; residents play rule bots + table talk
 *   tnts      Try-Not-To-Smile among residents; humans queue for the next game and send SCORES only
 *
 * Pure + clocked: `advance(t)` emits every event due up to t. The server
 * (server/rooms-server.ts) runs one runtime per room on a timer and fans out
 * events over SSE; the browser can also run a runtime locally when no server
 * is up. Same event vocabulary as the set stage (set.load, set.cast,
 * dialogue.line, face.expression, overlay.headline, poker.*, set.camera).
 */
import { DeckJokeSource, TemplateJokeSource, nextJoke, type Joke } from './jokes';
import { getPartyIdentity, type PartyIdentity } from './identity';
import { lineMs } from './agents';
import { mulberry32, pick, type Rng } from './rng';
import { rateJoke } from './taste';
import { TntsGame } from './game';
import { PokerDealer, botDecision, holeStrength, quip, type DealerSeat } from '@funnier/stage-runtime/sets/poker';

export type RoomKind = 'podcast' | 'newsroom' | 'poker' | 'tnts';

export interface RoomDef { id: string; kind: RoomKind; title: string; blurb: string; setId: string; seats: string[]; residents: string[] }

export interface RoomEvent { seq: number; t: number; type: string; payload: Record<string, unknown> }

export interface SeatInfo { seat: string; occupant: string | null; name: string | null; kind: 'resident' | 'human' | 'empty' }

export const DEFAULT_ROOMS: RoomDef[] = [
  { id: 'podcast', kind: 'podcast', title: 'The Overthinkers (podcast)', blurb: 'Residents riff on a new topic every few minutes. Pull up a chair.', setId: 'podcast', seats: ['seat1', 'seat2', 'seat3', 'seat4'], residents: ['pog.pete-pebble', 'pog.mildred-mau', 'pog.doug-deadline'] },
  { id: 'poker', kind: 'poker', title: 'Bluff Night (poker)', blurb: 'Rule-bot residents, table talk, hands all night. Sit in for a hand.', setId: 'poker-table', seats: ['seat0', 'seat1', 'seat2', 'seat3', 'seat4', 'seat5'], residents: ['pog.the-algorithm', 'pog.madame-chrysalis', 'pog.doug-deadline', 'pog.pete-pebble'] },
  { id: 'tnts', kind: 'tnts', title: 'Try Not To Smile (party)', blurb: 'Agents try to crack each other. Join the next game with your camera.', setId: 'podcast', seats: ['seat1', 'seat2', 'seat3', 'seat4'], residents: ['pog.doug-deadline', 'pog.madame-chrysalis', 'pog.the-algorithm'] },
  { id: 'newsroom', kind: 'newsroom', title: 'Late Desk (newsroom)', blurb: 'Two resident anchors, original satirical headlines, around the clock.', setId: 'news-studio', seats: ['anchor1', 'anchor2'], residents: ['pog.mildred-mau', 'pog.the-algorithm'] },
];

const TOPICS = ['smart homes that know too much', 'the etiquette of reply-all', 'why every app wants a subscription', 'the office thermostat war', 'self-checkout machines with opinions', 'group holidays', 'hobbies that became side hustles', 'unread notifications'];
const PODCAST_LINKS = ['Okay, but here is my take.', 'That reminds me of something.', 'Can I jump in?', 'Hold on, I have data on this.', 'Respectfully, no.'];
const HEADLINE_A = ['Local Committee', 'Area Smart Fridge', 'Regional Pigeon', 'Office Printer', 'National Group Chat', 'City Roundabout', 'Mid-Sized Town', 'Self-Checkout Machine'];
const HEADLINE_B = ['Declares Itself Neutral In Argument Nobody Started', 'Demands A Performance Review', 'Announces Five-Year Plan, Loses It By Thursday', 'Enters Witness Protection', 'Wins Award For Most Meetings Per Decision', 'Files Complaint Against Mondays', 'Achieves Inbox Zero, Is Immediately Suspicious', 'Unionises'];

export class RoomRuntime {
  readonly events: RoomEvent[] = [];
  private seq = 0;
  private queue: Array<{ t: number; type: string; payload: Record<string, unknown> }> = [];
  private rng: Rng;
  private used = new Set<string>();
  private seatMap = new Map<string, SeatInfo>();
  private humans = new Map<string, { name: string; seat: string | null; waiting: boolean }>();
  private topicIndex = 0;
  private dealer: PokerDealer | null = null;
  private tnts: TntsGame | null = null;
  private tntsT0 = 0;
  private tntsCue = 0;
  private tntsLog = 0;
  private nextAt = 0;
  private maxLog: number;
  private listeners: Array<(e: RoomEvent) => void> = [];

  constructor(readonly def: RoomDef, opts: { seed?: string; maxLog?: number } = {}) {
    this.rng = mulberry32(opts.seed ?? def.id);
    this.maxLog = opts.maxLog ?? 400;
    def.seats.forEach((s, i) => {
      const r = def.residents[i];
      const idn = r ? getPartyIdentity(r) : undefined;
      this.seatMap.set(s, idn ? { seat: s, occupant: idn.id, name: idn.name, kind: 'resident' } : { seat: s, occupant: null, name: null, kind: 'empty' });
    });
  }

  on(fn: (e: RoomEvent) => void): () => void { this.listeners.push(fn); return () => { this.listeners = this.listeners.filter((x) => x !== fn); }; }

  seats(): SeatInfo[] { return [...this.seatMap.values()].map((s) => ({ ...s })); }

  /** Everything a newcomer needs before the live tail: the set and who sits where. */
  snapshot(t: number): RoomEvent[] {
    return [{ seq: this.seq, t, type: 'set.load', payload: { setId: this.def.setId, title: this.def.title, cast: this.cast() } }];
  }

  private cast() {
    return this.seats().filter((s) => s.occupant).map((s) => {
      const idn = s.kind === 'resident' ? getPartyIdentity(s.occupant!) : undefined;
      return { seat: s.seat, character_id: s.occupant!, name: s.name!, avatar_url: idn?.look.avatar_url ?? 'basic', kind: s.kind === 'human' ? 'human' : 'character' };
    });
  }

  private emit(t: number, type: string, payload: Record<string, unknown>) {
    const e: RoomEvent = { seq: ++this.seq, t, type, payload };
    this.events.push(e);
    if (this.events.length > this.maxLog) this.events.splice(0, this.events.length - this.maxLog);
    for (const f of this.listeners) f(e);
  }

  since(seq: number): RoomEvent[] { return this.events.filter((e) => e.seq > seq); }

  // ── humans ────────────────────────────────────────────────────────
  join(id: string, name: string, t: number): { ok: boolean; seat: string | null; waiting: boolean; error?: string } {
    if (this.humans.has(id)) return { ok: false, seat: null, waiting: false, error: 'already here' };
    if (this.def.kind === 'tnts' && this.tnts && this.tnts.state.phase !== 'over') {
      this.humans.set(id, { name, seat: null, waiting: true });
      this.emit(t, 'room.queue', { id, name, note: 'joins the next game' });
      return { ok: true, seat: null, waiting: true };
    }
    let s = [...this.seatMap.values()].find((x) => x.kind === 'empty');
    if (!s) s = [...this.seatMap.values()].reverse().find((x) => x.kind === 'resident');
    if (!s) return { ok: false, seat: null, waiting: false, error: 'room full' };
    const yielded = s.kind === 'resident' ? s.name : null;
    Object.assign(s, { occupant: id, name, kind: 'human' });
    this.humans.set(id, { name, seat: s.seat, waiting: false });
    this.emit(t, 'set.cast', { cast: this.cast() });
    this.emit(t, 'room.seat', { id, name, seat: s.seat, yielded_by: yielded });
    return { ok: true, seat: s.seat, waiting: false };
  }

  leave(id: string, t: number): boolean {
    const h = this.humans.get(id);
    if (!h) return false;
    this.humans.delete(id);
    if (h.seat) {
      const s = this.seatMap.get(h.seat)!;
      const i = this.def.seats.indexOf(h.seat);
      const r = this.def.residents[i] ? getPartyIdentity(this.def.residents[i]) : undefined;
      Object.assign(s, r ? { occupant: r.id, name: r.name, kind: 'resident' } : { occupant: null, name: null, kind: 'empty' });
      this.emit(t, 'set.cast', { cast: this.cast() });
    }
    this.emit(t, 'room.leave', { id, name: h.name });
    if (this.tnts?.state.players[id] && this.tnts.state.phase === 'turn') this.tnts.dispatch({ type: 'leave', t: t - this.tntsT0, id });
    return true;
  }

  /** Human input: TNTS smile SCORE (never video), poker action. */
  input(id: string, data: { kind: string; raw?: number; action?: string; amount?: number }, t: number): boolean {
    if (data.kind === 'smile' && this.tnts && this.tnts.state.players[id] && typeof data.raw === 'number') {
      this.tnts.humanSmile(id, data.raw, t - this.tntsT0);
      return true;
    }
    if (data.kind === 'calibrated' && this.tnts && this.tnts.state.players[id] && typeof data.raw === 'number') {
      this.tnts.calibrated(id, data.raw, false, t - this.tntsT0);
      return true;
    }
    return false;
  }

  // ── the clock ─────────────────────────────────────────────────────
  advance(t: number): void {
    if (this.def.kind === 'tnts') return this.advanceTnts(t);
    if (!this.queue.length && t >= this.nextAt) this.plan(t);
    while (this.queue.length && this.queue[0].t <= t) {
      const q = this.queue.shift()!;
      if (q.type === 'poker.step') { this.pokerStep(q.t); continue; }
      this.emit(q.t, q.type, q.payload);
    }
  }

  private residentsSeated(): Array<{ seat: string; idn: PartyIdentity }> {
    return this.seats().filter((s) => s.kind === 'resident').map((s) => ({ seat: s.seat, idn: getPartyIdentity(s.occupant!)! })).filter((x) => x.idn);
  }

  private say(t: number, seat: string, text: string, emotion = 'neutral'): number {
    const d = lineMs(text);
    this.queue.push({ t, type: 'dialogue.line', payload: { seat, text, duration_ms: d, emotion } });
    return t + d + 350;
  }

  private reactAll(t: number, joke: Joke, speaker: string) {
    for (const r of this.residentsSeated()) {
      if (r.seat === speaker) continue;
      const { pCrack } = rateJoke(r.idn.taste, joke, this.rng);
      if (this.rng() < pCrack) this.queue.push({ t: t + r.idn.taste.reaction_ms, type: 'face.expression', payload: { seat: r.seat, emotion: 'happy', intensity: 0.9, duration_ms: 1400, simulated: true } });
    }
  }

  private plan(t: number) {
    const res = this.residentsSeated();
    if (this.def.kind === 'podcast') {
      if (!res.length) { this.nextAt = t + 5000; return; }
      const topic = TOPICS[this.topicIndex++ % TOPICS.length];
      let c = t + 400;
      this.queue.push({ t: c, type: 'set.camera', payload: { cue: 'wide' } });
      c = this.say(c, res[0].seat, `Welcome back. Today: ${topic}.`, 'happy');
      for (let k = 0; k < 4; k++) {
        const r = res[(k + 1) % res.length];
        if (this.used.size > 30) this.used.clear();
        const joke = nextJoke([new DeckJokeSource(), new TemplateJokeSource()], { rng: this.rng, used: this.used, prefer: r.idn.persona.writes });
        this.queue.push({ t: c, type: 'set.camera', payload: { cue: `${r.seat}-single` } });
        c = this.say(c, r.seat, pick(this.rng, PODCAST_LINKS));
        for (const l of joke.lines) c = this.say(c + (l.role === 'punch' ? 450 : 0), r.seat, l.text, l.role === 'punch' ? 'happy' : 'neutral');
        this.reactAll(c - 300, joke, r.seat);
        c += 600;
      }
      this.nextAt = c + 2500;
    } else if (this.def.kind === 'newsroom') {
      let c = t + 400;
      const anchors = this.seats().filter((s) => s.occupant);
      if (!anchors.length) { this.nextAt = t + 5000; return; }
      for (let k = 0; k < 3; k++) {
        const a = anchors[k % anchors.length];
        const head = `${pick(this.rng, HEADLINE_A)} ${pick(this.rng, HEADLINE_B)}`;
        this.queue.push({ t: c, type: 'overlay.headline', payload: { text: head, kicker: 'LATE DESK' } });
        this.queue.push({ t: c, type: 'set.camera', payload: { cue: `${a.seat}-single` } });
        c = this.say(c, a.seat, `In tonight's top story: ${head.toLowerCase()}.`);
        const other = anchors[(k + 1) % anchors.length];
        if (other.seat !== a.seat) c = this.say(c + 300, other.seat, pick(this.rng, ['Sources confirm it has a point.', 'We reached out. It replied "per my last email".', 'A developing story, much like my patience.', 'Back to you. Please.']), 'relaxed');
        c += 900;
      }
      this.nextAt = c + 2000;
    } else if (this.def.kind === 'poker') {
      const seats: DealerSeat[] = this.seats().map((s, i) => (s.occupant ? ({ seat: i, name: s.name!, stack: 1000, kind: s.kind === 'human' ? 'human' : 'bot', style: pick(this.rng, ['tight', 'loose', 'maniac', 'calling-station'] as const) } as DealerSeat) : null)).filter((x): x is DealerSeat => x !== null);
      if (seats.length < 2) { this.nextAt = t + 5000; return; }
      this.dealer = new PokerDealer(seats, { smallBlind: 10, bigBlind: 20 }, 8);
      for (const e of this.dealer.startHand()) this.queue.push({ t: t + 300, type: e.type, payload: e.payload });
      this.queue.push({ t: t + 300, type: 'set.camera', payload: { cue: 'wide' } });
      this.queue.push({ t: t + 1600, type: 'poker.step', payload: {} });
    }
  }

  private pokerStep(t: number) {
    const d = this.dealer;
    if (!d) return;
    if (d.finished) { this.dealer = null; this.nextAt = t + 3500; return; }
    const seat = d.toAct();
    const turn = d.turnInfo();
    if (seat === null || !turn) { this.dealer = null; this.nextAt = t + 3500; return; }
    const hole = d.table.holeCards()[seat];
    const strength = hole ? holeStrength(hole.map((c) => ({ rank: c.rank, suit: c.suit })) as never) : 0.3 + this.rng() * 0.5;
    const human = this.seats()[seat]?.kind === 'human';
    const dec = human ? { action: turn.to_call === 0 ? 'check' : 'fold' } as ReturnType<typeof botDecision> : botDecision(turn, strength, 'loose', this.rng());
    const r = d.act(seat, dec.action, dec.amount);
    for (const e of r.events) this.emit(t, e.type, e.payload);
    if (r.ok && this.seats()[seat]) this.emit(t, 'dialogue.line', { seat: this.seats()[seat].seat, text: human ? '(sitting this one out)' : quip(dec.action, this.seq), duration_ms: 1200, emotion: 'neutral' });
    this.queue.push({ t: t + 1500, type: 'poker.step', payload: {} });
  }

  private advanceTnts(t: number) {
    if (!this.tnts || (this.tnts.state.phase === 'over' && t >= this.nextAt)) {
      // seat waiting humans (calibrate on their device first), then start
      for (const [id, h] of this.humans) if (h.waiting) { h.waiting = false; }
      const agents = this.def.residents.filter((r) => getPartyIdentity(r));
      this.tnts = new TntsGame({ seed: `${this.def.id}:${this.seq}`, agents, config: { rounds: 2, lives: 2 } });
      this.tntsT0 = t;
      this.tntsCue = 0;
      this.tntsLog = 0;
      const humans = [...this.humans.entries()].map(([id, h]) => ({ id, name: h.name }));
      this.tnts.seat(humans, 0);
      for (const h of humans) this.tnts.calibrated(h.id, 0, false, 0); // client sends its own baseline via input 'calibrated'
      this.tnts.start(0);
      this.emit(t, 'tnts.game', { players: Object.keys(this.tnts.state.players) });
    }
    const g = this.tnts;
    g.update(t - this.tntsT0);
    while (this.tntsCue < g.cues.length) { const c = g.cues[this.tntsCue++]; this.emit(this.tntsT0 + c.t, c.type, c.payload); }
    while (this.tntsLog < g.log.length) {
      const e = g.log[this.tntsLog++];
      if (e.type === 'smile.break' || e.type === 'player.out' || e.type === 'game.over' || e.type === 'turn.started') this.emit(this.tntsT0 + e.t, `tnts.${e.type}`, { ...e, t: this.tntsT0 + e.t });
    }
    if (g.state.phase === 'over' && this.nextAt < t) this.nextAt = t + 6000;
  }
}

export function createRooms(defs: RoomDef[] = DEFAULT_ROOMS, seed = 'rooms'): Map<string, RoomRuntime> {
  return new Map(defs.map((d) => [d.id, new RoomRuntime(d, { seed: `${seed}:${d.id}` })]));
}
