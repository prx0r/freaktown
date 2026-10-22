import { describe, expect, it } from 'vitest';
import { DEFAULT_SKETCH_TIMING, gazeTargetAt, layoutSketch, planGaze, resolveCast, compileSketch } from '../src';
import { demo, mini } from './helpers';

const T = DEFAULT_SKETCH_TIMING;
const setup = (s = mini(), seed = s.id) => {
  const cast = resolveCast(s, T);
  const layout = layoutSketch(s, cast, T);
  return { cast, layout, plan: planGaze(layout, cast, T, seed) };
};

describe('gaze system', () => {
  it('listeners watch the speaker by default (outside scripted / idle looks)', () => {
    const { layout, plan } = setup();
    let checked = 0;
    for (const l of layout.lines) {
      for (const role of ['host', 'guest', 'walker'].filter((r) => r !== l.role)) {
        for (let t = l.start_ms + 50; t < l.end_ms; t += 250) {
          if (plan.looks.some((g) => g.role === role && t >= g.start_ms && t < g.end_ms)) continue;
          expect(gazeTargetAt(plan, layout, role, t)).toBe(l.role);
          checked++;
        }
      }
    }
    expect(checked).toBeGreaterThan(40);
  });

  it('scripted looks override the default', () => {
    const { layout, plan } = setup();
    const dt = layout.directions.find((d) => d.item.type === 'look')!;
    const hold = plan.looks.filter((g) => g.role === 'host' && g.source === 'double-take');
    expect(hold.length).toBe(3);
    // during the final snap-back the host looks at the guest even while the guest is not speaking
    const last = hold[2];
    expect(gazeTargetAt(plan, layout, 'host', last.start_ms + 10)).toBe('guest');
    expect(dt.t_ms).toBe(hold[0].start_ms);
  });

  it('double-take = glance → away → snap back (faster turn)', () => {
    const { plan } = setup();
    const [a, b, c] = plan.looks.filter((g) => g.source === 'double-take');
    expect(a.target).toBe('guest');
    expect(b.target).not.toBe('guest');
    expect(c.target).toBe('guest');
    expect(a.end_ms).toBe(b.start_ms);
    expect(b.end_ms).toBe(c.start_ms);
    expect(c.snap).toBeGreaterThan(a.snap);
    expect(a.end_ms - a.start_ms).toBe(T.double_take.glance_ms);
    expect(b.end_ms - b.start_ms).toBe(T.double_take.away_ms);
  });

  it('eye-roll looks up, laugh-break looks down', () => {
    const { plan } = setup();
    const r = plan.looks.filter((g) => g.source === 'reaction');
    expect(r.map((x) => x.target)).toEqual(['up', 'down']);
  });

  it('idle variation is seeded: same seed same plan, never on top of a scripted look', () => {
    const s = demo('wall-of-news');
    const a = setup(s, 'x').plan, b = setup(s, 'x').plan, c = setup(s, 'other-seed').plan;
    expect(a).toEqual(b);
    expect(JSON.stringify(a.looks.filter((g) => g.source === 'idle'))).not.toEqual(JSON.stringify(c.looks.filter((g) => g.source === 'idle')));
    for (const idle of a.looks.filter((g) => g.source === 'idle')) {
      const clash = a.looks.filter((g) => g !== idle && g.role === idle.role && g.source !== 'address' && g.start_ms < idle.end_ms && g.end_ms > idle.start_ms);
      expect(clash).toEqual([]);
    }
  });

  it('speakers address their scene partner (or the line\'s `to`); camera glance on the turn', () => {
    const { layout, plan } = setup(demo('wall-of-news'));
    const coLine = layout.lines.find((l) => l.role === 'coanchor')!; // replies to the anchor
    expect(gazeTargetAt(plan, layout, 'coanchor', coLine.start_ms + 100)).toBe('anchor');
    const toCam = layout.lines.find((l) => l.to === 'camera')!;
    expect(gazeTargetAt(plan, layout, toCam.role, toCam.start_ms + 100)).toBe('camera');
    expect(plan.looks.some((g) => g.source === 'camera-turn' && g.target === 'camera')).toBe(true);
  });

  it('micro nods come from listeners only and compile to face.expression gesture.nod', () => {
    const s = demo('the-tell');
    const { layout, plan } = setup(s);
    for (const n of plan.nods) {
      const sp = layout.lines.find((l) => n.t_ms >= l.start_ms && n.t_ms < l.end_ms);
      if (sp) expect(sp.role).not.toBe(n.role);
    }
    const c = compileSketch(s);
    expect(c.events.filter((e) => e.type === 'face.expression' && e.payload.action === 'gesture.nod').length).toBe(plan.nods.length);
    expect(c.events.filter((e) => e.type === 'gaze.look').length).toBe(plan.looks.length);
  });
});
