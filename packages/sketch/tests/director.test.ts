import { describe, expect, it } from 'vitest';
import { isLegalCut, type TimedLine } from '@funnier/newsroom';
import { compileSketch, SKETCH_CADENCE, type CompiledSketch, type SketchScriptV1 } from '../src';
import { demo, DEMO_IDS, mini } from './helpers';

const cases: Array<[string, SketchScriptV1]> = [...DEMO_IDS.map((id) => [id, demo(id)] as [string, SketchScriptV1]), ['mini', mini()]];

function seatOfRoleAt(c: CompiledSketch, role: string, t: number): string {
  // a line's seat is authoritative for its own time span; else last known
  const ls = c.lines.filter((l) => l.role === role && l.start_ms <= t);
  return ls.length ? ls[ls.length - 1].seat : c.cast.find((x) => x.role === role)!.seat;
}

describe('sketch director invariants', () => {
  it('cadence profile `sketch`: lmin ≈ 1.8 s, lmax ≈ 5 s', () => {
    expect(SKETCH_CADENCE.lmin_ms).toBe(1800);
    expect(SKETCH_CADENCE.lmax_ms).toBe(5000);
  });

  for (const [name, script] of cases) {
    describe(name, () => {
      const c = compileSketch(script);
      const shotAt = (t: number) => c.shots.find((s) => t >= s.start_ms && t < s.end_ms)!;

      it('shots tile the timeline without gaps or overlaps', () => {
        expect(c.shots[0].start_ms).toBe(0);
        for (let i = 1; i < c.shots.length; i++) expect(c.shots[i].start_ms).toBe(c.shots[i - 1].end_ms);
        expect(c.shots[c.shots.length - 1].end_ms).toBe(c.duration_ms);
      });

      it('speaker or a reaction is always in shot', () => {
        let n = 0;
        for (const l of c.lines) {
          for (let t = l.start_ms + 20; t < l.end_ms; t += 120) {
            const s = shotAt(t);
            const speakerSeat = seatOfRoleAt(c, l.role, t);
            const ok = s.seats.includes(speakerSeat) || (s.cls === 'reaction' && !!s.reactRole) || s.cls === 'wide' || s.reason === 'manual';
            if (!ok) throw new Error(`${name}: @${t}ms ${l.role} (${speakerSeat}) speaks but shot ${s.cue} shows ${s.seats.join(',')}`);
            n++;
          }
        }
        expect(n).toBeGreaterThan(50);
      });

      it('reaction shots belong to a look/react direction of that character', () => {
        const tl = c.events;
        for (const s of c.shots.filter((x) => x.cls === 'reaction')) {
          const dir = tl.some((e) => (e.type === 'gaze.look' || e.type === 'face.expression') && Math.abs(e.t_ms - s.start_ms) < 1600 && e.payload.seat === s.seats[0]);
          expect(dir, `${s.cue}@${s.start_ms}`).toBe(true);
        }
      });

      it('laugh holds are respected: no cut strictly inside a hold', () => {
        expect(c.laughs.length).toBeGreaterThan(0);
        for (const w of c.laughs) for (const s of c.shots) {
          if (s.start_ms > w.start_ms + 1 && s.start_ms < w.end_ms - 1) throw new Error(`${name}: cut ${s.cue}@${s.start_ms} inside laugh hold ${w.start_ms}-${w.end_ms}`);
        }
      });

      it('no mid-word cuts (and none in a line tail)', () => {
        const lines = c.lines.map((l) => ({ ...l, words: [] as Array<{ word: string; start_ms: number; end_ms: number }> }));
        // rebuild absolute words from the dialogue events
        for (const e of c.events.filter((x) => x.type === 'dialogue.line')) {
          const l = lines.find((x) => x.id === e.payload.line_id)!;
          l.words = (e.payload.words as Array<{ word: string; start_ms: number; end_ms: number }>).map((w) => ({ word: w.word, start_ms: e.t_ms + w.start_ms, end_ms: e.t_ms + w.end_ms }));
        }
        for (const s of c.shots.slice(1)) expect(isLegalCut(s.start_ms, lines as unknown as TimedLine[], SKETCH_CADENCE.tail_hold_ms), `${s.cue}@${s.start_ms}`).toBe(true);
      });

      it('shot bounds: inside [lmin, lmax] unless open / silent / button hold (none forced)', () => {
        for (const s of c.shots) {
          const d = s.end_ms - s.start_ms;
          const speech = c.lines.some((l) => l.start_ms < s.end_ms && l.end_ms > s.start_ms);
          if (s.reason === 'open' || !speech) continue;
          expect(d, `${s.cue}@${s.start_ms}`).toBeGreaterThanOrEqual(SKETCH_CADENCE.lmin_ms);
          if (s.reason !== 'button') expect(d, `${s.cue}@${s.start_ms}`).toBeLessThanOrEqual(SKETCH_CADENCE.lmax_ms);
        }
        expect(c.shots.filter((s) => s.forced)).toEqual([]);
      });

      it('grammar: open wide, wide on the game reveal, reaction close-ups, button holds to the end', () => {
        expect(c.shots[0].cls).toBe('wide');
        const game = script.scenes.flatMap((s) => s.beats).find((b) => b.kind === 'game');
        if (game) {
          const first = c.lines.find((l) => l.beat === game.id)!;
          const s = c.shots.find((x) => x.start_ms <= first.start_ms + 1 && x.end_ms > first.start_ms)!;
          expect(s.reason === 'game-reveal' || s.reason === 'double-take' || s.reason === 'reaction' || s.reason === 'look').toBe(true);
          expect(c.shots.some((x) => x.reason === 'game-reveal' && x.cls === 'wide')).toBe(true);
        }
        expect(c.shots.filter((s) => s.cls === 'reaction').length).toBeGreaterThanOrEqual(2);
        const last = c.shots[c.shots.length - 1];
        expect(last.reason).toBe('button');
      });

      it('deterministic', () => {
        expect(compileSketch(script)).toEqual(c);
      });
    });
  }
});

describe('compileSketch events', () => {
  const c = compileSketch(demo('wall-of-news'));
  it('casts registered identities and turns the auto director off', () => {
    const load = c.events[0];
    expect(load.type).toBe('set.load');
    expect((load.payload.cast as Array<{ character_id: string }>).map((m) => m.character_id)).toEqual(['pog.doug-deadline', 'pog.tictoria-gossip', 'pog.the-algorithm']);
    expect(c.events.some((e) => e.type === 'set.auto_director' && e.payload.on === false)).toBe(true);
    expect(c.cast.every((m) => m.registered)).toBe(true);
  });
  it('emits headlines, a walk to the mark, looks, reactions and the blackout', () => {
    const types = new Set(c.events.map((e) => e.type));
    for (const t of ['overlay.headline', 'stage.move', 'gaze.look', 'face.expression', 'dialogue.line', 'set.camera', 'overlay.blackout']) expect(types.has(t), t).toBe(true);
    const move = c.events.find((e) => e.type === 'stage.move')!;
    expect(move.payload).toMatchObject({ seat: 'floor-mark', to: 'wall-mark' });
    // after the walk, the algorithm's lines play from the mark
    expect(c.lines.filter((l) => l.role === 'algo').every((l) => l.seat === 'wall-mark')).toBe(true);
  });
  it('reactions fire after the identity\'s own latency', () => {
    const s = demo('the-tell');
    const k = compileSketch(s, { timing: { react_delay_ms: 999 } });
    // registered identities with a motion-style keep their own delay (not the 999 default)
    expect(k.cast.find((m) => m.role === 'sarge')!.react_delay_ms).toBe(120);
  });
  it('flags estimated timings honestly', () => {
    expect(c.estimated).toBe(true);
    expect(c.warnings.join()).toMatch(/ESTIMATED/);
  });
});
