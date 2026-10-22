import { describe, expect, it } from 'vitest';
import { initialState, replay, step, type TntsAction, type TntsState } from '../src/rules';
import { adjustSmile, calibrateNeutral, lumaOf } from '../src/calibration';
import { smileScore, syntheticFrame } from '../src/smile';

const seat3 = (): TntsAction[] => [
  { type: 'join', t: 0, id: 'h', name: 'You', kind: 'human' },
  { type: 'join', t: 0, id: 'a1', name: 'A1', kind: 'agent' },
  { type: 'join', t: 0, id: 'a2', name: 'A2', kind: 'agent' },
  { type: 'calibrated', t: 0, id: 'h', baseline: 0.05 },
];

/** Smile samples every 50 ms from t0 for durMs at level x. */
const hold = (id: string, t0: number, durMs: number, x: number): TntsAction[] => {
  const out: TntsAction[] = [];
  for (let t = t0; t <= t0 + durMs; t += 50) out.push({ type: 'smile', t, id, raw: x });
  return out;
};

describe('TNTS rules', () => {
  it('needs players and calibration before start', () => {
    let s = initialState();
    expect(step(s, { type: 'start', t: 0 }).events[0]).toMatchObject({ type: 'rejected' });
    const r = replay([
      { type: 'join', t: 0, id: 'h', name: 'You', kind: 'human' },
      { type: 'join', t: 0, id: 'a1', name: 'A1', kind: 'agent' },
      { type: 'start', t: 0 },
    ]);
    expect(r.events.at(-1)).toMatchObject({ type: 'rejected', reason: 'not calibrated: h' });
    s = r.state;
    s = step(s, { type: 'calibrated', t: 1, id: 'h', baseline: 0.1 }).state;
    const st = step(s, { type: 'start', t: 2 });
    expect(st.events.map((e) => e.type)).toEqual(['game.started', 'turn.started']);
    expect(st.state.performer).toBe('h');
  });

  it('a smile above threshold held for 400 ms is a break; 350 ms is not', () => {
    const base = replay([...seat3(), { type: 'start', t: 0 }]).state; // h performs first
    // h performs → judge a1 (agent)
    let s: TntsState = base;
    for (const a of hold('a1', 100, 350, 0.8)) s = step(s, a).state;
    expect(s.players.a1.strikes).toBe(0);
    for (const a of hold('a1', 1000, 400, 0.8)) s = step(s, a).state;
    expect(s.players.a1.strikes).toBe(1);
    expect(s.players.a1.lives).toBe(2);
    expect(s.players.h.score).toBe(1); // performer credited
  });

  it('threshold is strict and relative to the calibrated neutral face', () => {
    const r = replay([...seat3(), { type: 'end_turn', t: 0 }, { type: 'start', t: 0 }]);
    let s = r.state; // performer h; judge... make h a listener: end h's turn
    s = step(s, { type: 'end_turn', t: 10 }).state; // a1 performs, h judged
    expect(s.performer).toBe('a1');
    // resting smiler: baseline .4 — raw .65 → adjusted (.65-.4)/.6 = .417 < .5 → safe
    s = step(s, { type: 'calibrated', t: 10, id: 'h', baseline: 0.4, restingSmiler: true }).state;
    for (const a of hold('h', 100, 800, 0.65)) s = step(s, a).state;
    expect(s.players.h.strikes).toBe(0);
    // raw .8 → (.8-.4)/.6 = .667 > .5 → break
    for (const a of hold('h', 1000, 450, 0.8)) s = step(s, a).state;
    expect(s.players.h.strikes).toBe(1);
    expect(adjustSmile(0.65, 0.4)).toBeCloseTo(0.417, 3);
  });

  it('sample gaps reset the hold (dropped frames cannot stitch twitches)', () => {
    let s = replay([...seat3(), { type: 'start', t: 0 }]).state;
    for (const t of [100, 150, 200, 500, 550, 600]) s = step(s, { type: 'smile', t, id: 'a1', raw: 0.9 }).state;
    expect(s.players.a1.strikes).toBe(0);
  });

  it('grace period after a break; performer is never judged', () => {
    let s = replay([...seat3(), { type: 'start', t: 0 }]).state;
    for (const a of hold('a1', 100, 2000, 0.9)) s = step(s, a).state;
    // 100..2100 continuous: break at 500, grace until 2000, next hold restarts → second break at ≥2000+
    expect(s.players.a1.strikes).toBe(2);
    for (const a of hold('h', 100, 3000, 1)) s = step(s, a).state; // h is performing
    expect(s.players.h.strikes).toBe(0);
  });

  it('losing all lives = out; last face standing wins', () => {
    let s = replay([...seat3(), { type: 'start', t: 0 }], { lives: 1 }).state;
    const ev: string[] = [];
    for (const a of [...hold('a1', 100, 450, 0.9), ...hold('a2', 1000, 450, 0.9)]) { const r = step(s, a); s = r.state; ev.push(...r.events.map((e) => e.type)); }
    expect(ev).toEqual(['smile.break', 'player.out', 'smile.break', 'player.out', 'game.over']);
    expect(s.phase).toBe('over');
    expect(s.winner).toBe('h');
  });

  it('turns rotate, skip players who are out, rounds cap the game', () => {
    let s = replay([...seat3(), { type: 'start', t: 0 }], { rounds: 2, turnMs: 1000 }).state;
    const perf: string[] = [s.performer!];
    for (let t = 1000; t <= 10_000 && s.phase === 'turn'; t += 1000) { s = step(s, { type: 'tick', t }).state; if (s.performer) perf.push(s.performer); }
    expect(perf).toEqual(['h', 'a1', 'a2', 'h', 'a1', 'a2']);
    expect(s.phase).toBe('over');
  });

  it('bad lighting suspends judging with a warning (no strike for an unseen face)', () => {
    let s = replay([...seat3(), { type: 'end_turn', t: 0 }, { type: 'start', t: 0 }]).state;
    s = step(s, { type: 'end_turn', t: 5 }).state; // a1 performs, h listens
    const r = step(s, { type: 'lighting', t: 10, id: 'h', luminance: 0.05 });
    expect(r.events[0]).toMatchObject({ type: 'lighting.warning', id: 'h' });
    s = r.state;
    for (const a of hold('h', 100, 800, 1)) s = step(s, a).state;
    expect(s.players.h.strikes).toBe(0);
    expect(step(s, { type: 'lighting', t: 1000, id: 'h', luminance: 0.5 }).events[0]).toMatchObject({ type: 'lighting.ok' });
  });

  it('late joiners and explicit spectators watch, never judged', () => {
    let s = replay([...seat3(), { type: 'start', t: 0 }, { type: 'join', t: 5, id: 'late', name: 'Late', kind: 'human' }, { type: 'spectate', t: 6, id: 'sp', name: 'Sp' }]).state;
    expect(Object.keys(s.spectators)).toEqual(['late', 'sp']);
    expect(s.players.late).toBeUndefined();
    expect(step(s, { type: 'smile', t: 100, id: 'late', raw: 1 }).events[0]).toMatchObject({ type: 'rejected' });
  });

  it('performer leaving ends their turn', () => {
    const s = replay([...seat3(), { type: 'start', t: 0 }]).state;
    const r = step(s, { type: 'leave', t: 10, id: 'h' });
    expect(r.events.map((e) => e.type)).toEqual(['player.left', 'turn.ended', 'turn.started']);
    expect(r.state.performer).toBe('a1');
  });

  it('replay is deterministic', () => {
    const acts = [...seat3(), { type: 'start', t: 0 } as TntsAction, ...hold('a1', 100, 600, 0.9)];
    expect(JSON.stringify(replay(acts))).toBe(JSON.stringify(replay(acts)));
  });
});

describe('calibration + measured smile', () => {
  it('neutral baseline, resting smiler, noisy and smiling rejects', () => {
    const steady = Array.from({ length: 30 }, (_, i) => 0.05 + (i % 3) * 0.01);
    expect(calibrateNeutral(steady)).toMatchObject({ ok: true, baseline: 0.06, restingSmiler: false });
    const resting = steady.map((x) => x + 0.3);
    expect(calibrateNeutral(resting)).toMatchObject({ ok: true, restingSmiler: true });
    const noisy = Array.from({ length: 30 }, (_, i) => (i % 2 ? 0.05 : 0.6));
    expect(calibrateNeutral(noisy)).toMatchObject({ ok: false, reason: 'too-noisy' });
    expect(calibrateNeutral(steady.map(() => 0.8))).toMatchObject({ ok: false, reason: 'already-smiling' });
    expect(calibrateNeutral([0.1, 0.1])).toMatchObject({ ok: false, reason: 'too-few-samples' });
  });

  it('syntheticFrame inverts smileFusion (mouthSmile + cheekSquint)', () => {
    for (const x of [0, 0.2, 0.5, 0.8]) expect(smileScore(syntheticFrame(x))).toBeCloseTo(x, 1);
    expect(smileScore({})).toBe(0);
  });

  it('luma of an RGBA buffer', () => {
    expect(lumaOf(new Uint8ClampedArray(4 * 64).fill(255), 1)).toBe(1);
    expect(lumaOf(new Uint8ClampedArray(4 * 64), 1)).toBe(0);
  });
});
