import { describe, expect, it } from 'vitest';
import { PokerDealer, PokerShow, botDecision, holeStrength, pokerSeats, POKER_HUMAN_SEAT, type DealerEvent } from '../src/sets';

const seats = () => pokerSeats('Human');

describe('PokerDealer (poker-ts) → contract events', () => {
  it('hand_start → blinds chips → 2 cards per seat → first turn', () => {
    const d = new PokerDealer(seats());
    const ev = d.startHand(0);
    expect(ev[0].type).toBe('poker.hand_start');
    expect((ev[0].payload.seats as unknown[]).length).toBe(5);
    expect(ev.filter((e) => e.type === 'poker.chips').map((e) => e.payload.amount).sort()).toEqual([10, 20]);
    const deals = ev.filter((e) => e.type === 'poker.deal');
    expect(deals).toHaveLength(5);
    for (const e of deals) expect((e.payload.cards as unknown[]).length).toBe(2);
    const turn = ev[ev.length - 1];
    expect(turn.type).toBe('poker.turn');
    expect(turn.payload.to_call).toBe(20);
    expect(ev.every((e) => e.payload.hand_id === 'hand-1')).toBe(true);
  });

  it('rejects out-of-turn actions and maps call→check when nothing to call', () => {
    const d = new PokerDealer(seats());
    d.startHand(0);
    const t = d.turnInfo()!;
    const other = [0, 2, 3, 4, 6].find((s) => s !== t.seat)!;
    expect(d.act(other, 'call').ok).toBe(false);
    const r = d.act(t.seat, 'call');
    expect(r.ok).toBe(true);
    const a = r.events.find((e) => e.type === 'poker.action')!;
    expect(a.payload).toMatchObject({ seat: t.seat, action: 'call', amount: 20, street: 'preflop' });
    expect(r.events.find((e) => e.type === 'poker.chips')?.payload).toMatchObject({ from: t.seat, to: 'pot', amount: 20 });
  });

  it('everyone calls/checks → flop, turn, river boards then showdown with chips to winners', () => {
    const d = new PokerDealer(seats());
    const all: DealerEvent[] = [...d.startHand(0)];
    let guard = 0;
    while (!d.finished && guard++ < 100) {
      const t = d.turnInfo()!;
      all.push(...d.act(t.seat, t.actions.includes('check') ? 'check' : 'call').events);
    }
    const boards = all.filter((e) => e.type === 'poker.board').map((e) => (e.payload.cards as unknown[]).length);
    expect(boards).toEqual([3, 4, 5]);
    const sd = all.find((e) => e.type === 'poker.showdown')!;
    const winners = sd.payload.winners as Array<{ seat: number; amount: number; ranking: string }>;
    expect(winners.length).toBeGreaterThan(0);
    expect(winners.reduce((a, w) => a + w.amount, 0)).toBe(100); // 5 × 20
    expect((sd.payload.hole as unknown[]).length).toBe(5);
    expect(all.filter((e) => e.type === 'poker.chips' && e.payload.from === 'pot').length).toBe(winners.filter((w) => w.amount > 0).length);
    const total = d.seats.reduce((a, s) => a + s.stack, 0);
    expect(total).toBe(5000);
  });

  it('all fold to one player → showdown "everyone folded"', () => {
    const d = new PokerDealer(seats());
    d.startHand(0);
    const evs: DealerEvent[] = [];
    let guard = 0;
    while (!d.finished && guard++ < 20) { const t = d.turnInfo()!; evs.push(...d.act(t.seat, 'fold').events); }
    const sd = evs.find((e) => e.type === 'poker.showdown')!;
    expect((sd.payload.winners as Array<{ ranking: string }>)[0].ranking).toBe('everyone folded');
  });
});

describe('bots', () => {
  it('strength + policy', () => {
    expect(holeStrength([{ rank: 'A', suit: 'spades' }, { rank: 'A', suit: 'hearts' }])).toBeGreaterThan(0.9);
    expect(holeStrength([{ rank: '2', suit: 'spades' }, { rank: '7', suit: 'hearts' }])).toBeLessThan(0.4);
    const turn = { hand_id: 'h', seat: 0, actions: ['fold', 'call', 'raise'] as const, min: 40, max: 1000, to_call: 20, pot: 30 };
    expect(botDecision({ ...turn, actions: [...turn.actions] }, 0.95, 'tight', 0.9).action).toBe('raise');
    expect(botDecision({ ...turn, actions: [...turn.actions] }, 0.2, 'tight', 0.9).action).toBe('fold');
    expect(botDecision({ ...turn, actions: [...turn.actions] }, 0.2, 'calling-station', 0.9).action).toBe('call');
  });
});

describe('PokerShow: 4 bots + a human seat play to showdown through send()', () => {
  it('waits for the human, applies poker.intent, quips, reaches showdown', async () => {
    const sent: Array<{ type: string; payload: Record<string, unknown> }> = [];
    const q: Array<() => void> = [];
    const show = new PokerShow((type, payload) => { sent.push({ type, payload }); }, {
      seats: seats(), rnd: () => 0.99, botDelayMs: 1, humanTimeoutMs: 999999,
      schedule: (fn) => { q.push(fn); return q.length; }, cancel: () => {},
    });
    await show.start(0);
    let humanActs = 0;
    for (let i = 0; i < 200 && !show.dealer.finished; i++) {
      const t = show.dealer.turnInfo();
      if (t && t.seat === POKER_HUMAN_SEAT) {
        expect(await show.apply(0, 'call')).toMatch(/not seat 0/);
        expect(await show.apply(POKER_HUMAN_SEAT, t.actions.includes('check') ? 'check' : 'call')).toBeNull();
        humanActs++;
        continue;
      }
      const fn = q.shift(); if (fn) { fn(); await new Promise((r) => setTimeout(r, 0)); }
    }
    expect(show.dealer.finished).toBe(true);
    expect(humanActs).toBeGreaterThan(0);
    const types = sent.map((s) => s.type);
    expect(types).toContain('poker.showdown');
    expect(types).toContain('dialogue.line');
    expect(sent.filter((s) => s.type === 'set.camera').length).toBeGreaterThanOrEqual(2);
    expect(show.log.some((l) => l.startsWith(`human:${POKER_HUMAN_SEAT}`))).toBe(true);
  });
});
