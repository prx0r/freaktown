/**
 * PokerDealer — wraps poker-ts (MIT, github.com/claudijo/poker-ts) as the hand
 * state machine and turns every transition into a contract event the stage
 * animates: poker.hand_start / deal / turn / action / chips / board / showdown.
 *
 * Runs wherever the show is dealt from (/control); bots act via botDecision(),
 * a human seat acts by sending poker.intent through the same command transport.
 * NOTE: a demo/show dealer for the live stage, not game truth for money play —
 * hole cards are public in the event log (fine for a broadcast, not for real play).
 */
import { Table } from 'poker-ts';
import type {
  CardV1, PokerActionV1, PokerStreetV1, PokerTurnPayloadV1,
} from '@funnier/contracts';

export interface DealerEvent { type: string; payload: Record<string, unknown> }
export interface DealerSeat { seat: number; name: string; stack: number; kind: 'bot' | 'human'; style?: BotStyle }
export type BotStyle = 'tight' | 'loose' | 'maniac' | 'calling-station';

export const HAND_RANKINGS = ['high card', 'pair', 'two pair', 'three of a kind', 'straight', 'flush', 'full house', 'four of a kind', 'straight flush', 'royal flush'];

export class PokerDealer {
  readonly table: InstanceType<typeof Table>;
  readonly seats: DealerSeat[];
  private handNo = 0;
  handId = '';
  private lastBoard = 0;
  private emitted: DealerEvent[] = [];
  private names = new Map<number, string>();
  private potBefore = 0;
  private potTotal = 0;
  finished = false;

  constructor(seats: DealerSeat[], blinds = { smallBlind: 10, bigBlind: 20 }, numSeats = 8) {
    this.seats = seats;
    this.table = new Table(blinds, numSeats);
    for (const s of seats) { this.table.sitDown(s.seat, s.stack); this.names.set(s.seat, s.name); }
  }

  private emit(type: string, payload: Record<string, unknown>): void {
    if (type === 'poker.chips' && payload.to === 'pot') this.potTotal += Number(payload.amount) || 0;
    this.emitted.push({ type, payload: { hand_id: this.handId, ...payload } });
  }
  /** Drain events produced since the last call. */
  take(): DealerEvent[] { const e = this.emitted; this.emitted = []; return e; }

  pot(): number {
    const pots = this.table.isHandInProgress() ? this.table.pots().reduce((a, p) => a + p.size, 0) : 0;
    const bets = this.table.isHandInProgress() ? this.table.handPlayers().reduce((a, p) => a + (p?.betSize ?? 0), 0) : 0;
    return pots + bets;
  }

  startHand(button?: number): DealerEvent[] {
    this.handNo++;
    this.handId = `hand-${this.handNo}`;
    this.finished = false;
    this.lastBoard = 0;
    this.table.startHand(button);
    const players = this.table.seats();
    this.emit('poker.hand_start', {
      button: this.table.button(),
      small_blind: this.table.forcedBets().smallBlind,
      big_blind: this.table.forcedBets().bigBlind,
      seats: players.map((p, seat) => p && { seat, stack: p.stack, bet: p.betSize, name: this.names.get(seat) }).filter(Boolean),
    });
    // blinds as chip moves
    this.potTotal = 0;
    this.table.handPlayers().forEach((p, seat) => { if (p && p.betSize > 0) this.emit('poker.chips', { from: seat, to: 'pot', amount: p.betSize }); });
    const hole = this.table.holeCards();
    hole.forEach((cards, seat) => { if (cards) this.emit('poker.deal', { seat, cards: cards.map(card) }); });
    this.potBefore = this.pot();
    this.announceTurn();
    return this.take();
  }

  street(): PokerStreetV1 { return this.table.roundOfBetting() as PokerStreetV1; }

  toAct(): number | null {
    return this.table.isHandInProgress() && this.table.isBettingRoundInProgress() ? this.table.playerToAct() : null;
  }

  turnInfo(): PokerTurnPayloadV1 | null {
    const seat = this.toAct();
    if (seat === null) return null;
    const legal = this.table.legalActions();
    const hp = this.table.handPlayers();
    const maxBet = Math.max(...hp.map((p) => p?.betSize ?? 0));
    return {
      hand_id: this.handId, seat, actions: legal.actions as PokerActionV1[],
      min: legal.chipRange?.min, max: legal.chipRange?.max,
      to_call: Math.max(0, maxBet - (hp[seat]?.betSize ?? 0)), pot: this.pot(),
    };
  }

  private announceTurn(): void {
    const t = this.turnInfo();
    if (t) this.emit('poker.turn', { ...t });
  }

  /** Apply an action for `seat`. Returns false (no events) if it isn't that seat's turn / illegal. */
  act(seat: number, action: PokerActionV1, amount?: number): { ok: boolean; events: DealerEvent[]; error?: string } {
    const t = this.turnInfo();
    if (!t || t.seat !== seat) return { ok: false, events: [], error: `not seat ${seat}'s turn` };
    let a = action;
    if (!t.actions.includes(a)) {
      // map friendly intents: call→check when nothing to call, bet↔raise
      if (a === 'call' && t.actions.includes('check')) a = 'check';
      else if (a === 'check' && t.actions.includes('call')) return { ok: false, events: [], error: 'cannot check, must call/fold' };
      else if (a === 'raise' && t.actions.includes('bet')) a = 'bet';
      else if (a === 'bet' && t.actions.includes('raise')) a = 'raise';
      else return { ok: false, events: [], error: `illegal ${action}` };
    }
    let size: number | undefined;
    if (a === 'bet' || a === 'raise') {
      const min = t.min ?? 0, max = t.max ?? min;
      size = Math.max(min, Math.min(max, Math.round(amount ?? min)));
    }
    const before = this.table.handPlayers()[seat]?.betSize ?? 0;
    const street = this.street();
    this.table.actionTaken(a, size);
    const hp = this.table.isHandInProgress() ? this.table.handPlayers() : [];
    const after = hp[seat]?.betSize ?? before;
    const stack = this.table.seats()[seat]?.stack ?? 0;
    const put = Math.max(0, after - before);
    if (put > 0) this.emit('poker.chips', { from: seat, to: 'pot', amount: put });
    this.emit('poker.action', { seat, action: a, amount: put, stack, pot: this.pot(), street });
    this.advance();
    return { ok: true, events: this.take() };
  }

  private advance(): void {
    if (!this.table.isHandInProgress()) { if (!this.finished) this.finishFolded(); return; }
    if (this.table.isBettingRoundInProgress()) { this.announceTurn(); return; }
    // round over: one player left?
    const potsPre = this.table.pots();
    this.table.endBettingRound();
    if (!this.table.isHandInProgress()) { this.finishFolded(potsPre[0]?.eligiblePlayers?.[0]); return; }
    const board = this.table.communityCards();
    if (board.length > this.lastBoard) {
      this.lastBoard = board.length;
      this.emit('poker.board', { street: this.street(), cards: board.map(card) });
    }
    if (this.table.areBettingRoundsCompleted()) { this.showdown(); return; }
    if (this.table.isBettingRoundInProgress()) this.announceTurn();
    else this.advance();
  }

  private lastStanding(): number {
    const s = this.table.seats().findIndex((p) => p !== null);
    return Math.max(0, s);
  }

  private finishFolded(hint?: number): void {
    const now = this.table.seats();
    let seat = hint ?? -1;
    let gain = 0;
    for (const st of this.seats) {
      const d = (now[st.seat]?.stack ?? 0) - st.stack;
      if (d > gain) { gain = d; seat = st.seat; }
    }
    if (seat < 0) seat = this.lastStanding();
    const won = this.potTotal;
    this.emit('poker.chips', { from: 'pot', to: seat, amount: won });
    this.emit('poker.showdown', { winners: [{ seat, amount: won, ranking: 'everyone folded', cards: [] }], hole: [] });
    this.finished = true;
    this.syncStacks();
  }

  private showdown(): void {
    const hole = this.table.holeCards();
    const beforeStacks = this.table.seats().map((p) => p?.stack ?? 0);
    const potTotal = this.table.pots().reduce((a, p) => a + p.size, 0);
    this.table.showdown();
    const winners = this.table.winners();
    if (!winners.flat().length) { this.finishFolded(); return; }
    const after = this.table.seats().map((p) => p?.stack ?? 0);
    const flat = winners.flat().map(([seat, hand]) => ({
      seat, amount: Math.max(0, after[seat] - beforeStacks[seat]),
      ranking: HAND_RANKINGS[hand.ranking] ?? String(hand.ranking), cards: hand.cards.map(card),
    }));
    for (const w of flat) if (w.amount > 0) this.emit('poker.chips', { from: 'pot', to: w.seat, amount: w.amount });
    this.emit('poker.showdown', {
      winners: flat, pot: potTotal,
      hole: hole.map((c, seat) => c && { seat, cards: c.map(card) }).filter(Boolean),
    });
    this.finished = true;
    this.syncStacks();
  }

  private syncStacks(): void {
    const s = this.table.seats();
    for (const seat of this.seats) seat.stack = s[seat.seat]?.stack ?? seat.stack;
  }
}

export function card(c: { rank: string; suit: string }): CardV1 {
  return { rank: c.rank as CardV1['rank'], suit: c.suit as CardV1['suit'] };
}

// ── bots ──────────────────────────────────────────────────────────────

const RANK_VAL: Record<string, number> = { '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, T: 10, J: 11, Q: 12, K: 13, A: 14 };

/** Crude preflop strength 0..1 from two hole cards (pairs, high cards, suited, connected). */
export function holeStrength(cards: CardV1[]): number {
  if (cards.length < 2) return 0.3;
  const [a, b] = cards.map((c) => RANK_VAL[c.rank]).sort((x, y) => y - x);
  let s = (a + b) / 28;
  if (a === b) s += 0.35;
  if (cards[0].suit === cards[1].suit) s += 0.06;
  if (Math.abs(a - b) === 1) s += 0.04;
  return Math.min(1, s);
}

/** Rule-based bot: deterministic given (strength, style, rnd). */
export function botDecision(
  turn: PokerTurnPayloadV1, strength: number, style: BotStyle = 'loose', rnd = Math.random(),
): { action: PokerActionV1; amount?: number } {
  const can = (a: PokerActionV1) => turn.actions.includes(a);
  const aggressive = style === 'maniac' ? 0.35 : style === 'loose' ? 0.18 : style === 'tight' ? 0.12 : 0.04;
  const foldBar = style === 'tight' ? 0.42 : style === 'calling-station' ? 0.1 : style === 'maniac' ? 0.15 : 0.28;
  const raiseOk = (can('raise') || can('bet')) && (strength > 0.78 || rnd < aggressive);
  if (raiseOk) {
    const a: PokerActionV1 = can('raise') ? 'raise' : 'bet';
    const min = turn.min ?? 0;
    return { action: a, amount: Math.min(turn.max ?? min, min + Math.round(turn.pot * 0.3)) };
  }
  if (turn.to_call === 0 && can('check')) return { action: 'check' };
  if (strength < foldBar && turn.to_call > turn.pot * 0.25 && can('fold')) return { action: 'fold' };
  if (can('call')) return { action: 'call' };
  if (can('check')) return { action: 'check' };
  return { action: 'fold' };
}

const QUIPS: Record<string, string[]> = {
  fold: ['Not this one.', 'I fold. Under protest.', 'Too rich for my circuits.', 'Fine. Take it.'],
  check: ['Check.', 'I knock.', 'Check, quietly.', 'Your move.'],
  call: ['Call.', 'I will see that.', 'Sure, why not.', 'Calling. Against advice.'],
  bet: ['Bet.', 'Let us make it interesting.', 'A little something.', 'Chips in.'],
  raise: ['Raise.', 'Up it goes.', 'I raise. Feel that?', 'Bigger.'],
  win: ['Read it and weep.', 'Thank you, thank you.', 'Pot please.', 'Never in doubt.'],
};
export function quip(kind: string, n: number): string {
  const q = QUIPS[kind] ?? [kind];
  return q[Math.abs(n) % q.length];
}
