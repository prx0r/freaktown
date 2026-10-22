/**
 * PokerShow — runs a hand for the live stage from /control:
 * PokerDealer (poker-ts) → contract events via `send`, bots act on a timer with
 * a quip (dialogue.line), a human seat acts by `poker.intent` from /play.
 * A human who doesn't act within `humanTimeoutMs` auto-checks (or folds).
 */
import type { PokerActionV1 } from '@funnier/contracts';
import { PokerDealer, botDecision, holeStrength, quip, type DealerEvent, type DealerSeat } from './PokerDealer';

export type Send = (type: string, payload: Record<string, unknown>) => Promise<unknown> | void;

export interface PokerShowOptions {
  seats: DealerSeat[];
  /** poker seat index → set seat id (for dialogue lines / camera cues). */
  seatId?: (i: number) => string;
  botDelayMs?: number;
  humanTimeoutMs?: number;
  quips?: boolean;
  /** Camera cues during the hand (reaction close-ups, board, overhead). */
  directCameras?: boolean;
  rnd?: () => number;
  schedule?: (fn: () => void, ms: number) => unknown;
  cancel?: (h: unknown) => void;
}

export class PokerShow {
  readonly dealer: PokerDealer;
  private o: Required<Omit<PokerShowOptions, 'seats'>>;
  private timer: unknown = null;
  private n = 0;
  private actions = 0;
  private stopped = false;
  log: string[] = [];
  lastWinner: number | null = null;
  onFinish?: () => void;

  constructor(private send: Send, opts: PokerShowOptions) {
    this.dealer = new PokerDealer(opts.seats.map((s) => ({ ...s })));
    this.o = {
      seatId: (i) => `seat${i}`, botDelayMs: 1400, humanTimeoutMs: 25000, quips: true, directCameras: true,
      rnd: Math.random, schedule: (fn, ms) => setTimeout(fn, ms), cancel: (h) => clearTimeout(h as number), ...opts,
    } as Required<Omit<PokerShowOptions, 'seats'>>;
  }

  private async emit(evts: DealerEvent[]): Promise<void> {
    for (const e of evts) {
      await this.send(e.type, e.payload);
      if (this.o.directCameras) {
        if (e.type === 'poker.board') await this.send('set.camera', { cue: 'board', source: 'auto_director' });
        if (e.type === 'poker.showdown') {
          const w = (e.payload.winners as Array<{ seat: number }>)[0];
          this.lastWinner = w?.seat ?? null;
          if (w) await this.send('set.camera', { cue: `reaction:${this.o.seatId(w.seat)}`, source: 'auto_director' });
        }
      }
    }
  }

  async start(button?: number): Promise<void> {
    await this.send('set.auto_director', { on: false });
    await this.send('set.camera', { cue: 'overhead', source: 'auto_director' });
    await this.emit(this.dealer.startHand(button));
    this.next();
  }

  stop(): void { this.stopped = true; if (this.timer) this.o.cancel(this.timer); }

  private seatOf(i: number): DealerSeat | undefined { return this.dealer.seats.find((s) => s.seat === i); }

  private next(): void {
    if (this.stopped) return;
    if (this.dealer.finished) {
      const w = this.dealer.seats.find((s) => s.kind === 'bot');
      void this.finish(w);
      return;
    }
    const turn = this.dealer.turnInfo();
    if (!turn) return;
    const seat = this.seatOf(turn.seat);
    if (seat?.kind === 'human') {
      this.timer = this.o.schedule(() => {
        const t = this.dealer.turnInfo();
        if (t && t.seat === turn.seat) void this.apply(turn.seat, t.actions.includes('check') ? 'check' : 'fold', undefined, 'timeout');
      }, this.o.humanTimeoutMs);
      return;
    }
    this.timer = this.o.schedule(() => {
      const t = this.dealer.turnInfo();
      if (!t || t.seat !== turn.seat) return;
      const hole = this.dealer.table.holeCards()[t.seat] ?? [];
      const strength = holeStrength(hole.map((c) => ({ rank: c.rank, suit: c.suit })) as never);
      const d = botDecision(t, strength, seat?.style ?? 'loose', this.o.rnd());
      void this.apply(t.seat, d.action, d.amount, 'bot');
    }, this.o.botDelayMs);
  }

  /** A human intent from /play (or a bot decision). Returns the error when rejected. */
  async apply(seat: number, action: PokerActionV1, amount?: number, who: 'human' | 'bot' | 'timeout' = 'human'): Promise<string | null> {
    if (this.stopped) return 'stopped';
    const res = this.dealer.act(seat, action, amount);
    if (!res.ok) return res.error ?? 'rejected';
    if (this.timer) { this.o.cancel(this.timer); this.timer = null; }
    this.log.push(`${who}:${seat}:${action}`);
    const act = res.events.find((e) => e.type === 'poker.action');
    const done = res.events.filter((e) => e.type !== 'poker.action' || e === act);
    if (act) await this.send(act.type, act.payload);
    if (this.o.directCameras && act) {
      // raises get a close-up, folds a reaction shot; otherwise keep the table in view
      const a = String(act.payload.action);
      const k = this.actions++;
      const cue = a === 'raise' || a === 'bet' ? `close:${this.o.seatId(seat)}`
        : a === 'fold' ? `reaction:${this.o.seatId(seat)}`
        : k % 4 === 0 ? `single:${this.o.seatId(seat)}` : k % 4 === 2 ? (k % 8 === 2 ? 'wide' : 'orbit') : null;
      if (cue) await this.send('set.camera', { cue, source: 'auto_director' });
    }
    if (this.o.quips && act && (who !== 'human')) {
      await this.send('dialogue.line', { seat: this.o.seatId(seat), text: quip(String(act.payload.action), this.n++) });
    }
    await this.emit(done.filter((e) => e !== act));
    this.next();
    return null;
  }

  private async finish(_w?: DealerSeat): Promise<void> {
    if (this.stopped) return;
    this.stopped = true;
    const winnerSeat = this.lastWinner === null ? undefined : this.seatOf(this.lastWinner);
    if (this.o.quips && winnerSeat?.kind === 'bot') await this.send('dialogue.line', { seat: this.o.seatId(winnerSeat.seat), text: quip('win', this.n++) });
    this.onFinish?.();
  }
}
