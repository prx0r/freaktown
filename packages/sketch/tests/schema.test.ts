import { describe, expect, it } from 'vitest';
import { assertSketch, SketchError, validateSketch, type SketchScriptV1 } from '../src';
import { demo, DEMO_IDS, mini } from './helpers';

const clone = (s: SketchScriptV1) => JSON.parse(JSON.stringify(s)) as SketchScriptV1;

describe('sketch schema (funnier.sketch/v1)', () => {
  it('accepts both demos and the mini fixture', () => {
    for (const id of DEMO_IDS) expect(validateSketch(demo(id))).toEqual([]);
    expect(validateSketch(mini())).toEqual([]);
  });

  it('rejects wrong schema id, missing cast and empty scenes', () => {
    expect(validateSketch({})).toContain('schema must be "funnier.sketch/v1"');
    const s = clone(mini()); s.cast = [];
    expect(validateSketch(s).join()).toMatch(/cast: at least one/);
    const t = clone(mini()); t.scenes = [];
    expect(validateSketch(t).join()).toMatch(/scenes: at least one/);
  });

  it('flags unknown roles, bad reaction/gesture kinds and self-looks', () => {
    const s = clone(mini());
    s.scenes[0].beats[0].items.push(
      { type: 'line', who: 'nobody', text: 'hi' },
      { type: 'react', who: 'host', kind: 'swoon' as never },
      { type: 'gesture', who: 'host', kind: 'moonwalk' as never },
      { type: 'look', who: 'host', at: 'host' },
      { type: 'look', who: 'host', at: 'the moon' },
    );
    const e = validateSketch(s).join('\n');
    expect(e).toMatch(/unknown role "nobody"/);
    expect(e).toMatch(/reaction kind must be one of/);
    expect(e).toMatch(/gesture kind must be one of/);
    expect(e).toMatch(/cannot look at itself/);
    expect(e).toMatch(/look target "the moon"/);
  });

  it('accepts camera / audience / prop / point look targets', () => {
    const s = clone(mini());
    s.scenes[0].beats[0].items.push(
      { type: 'look', who: 'host', at: 'camera' }, { type: 'look', who: 'host', at: 'audience' },
      { type: 'look', who: 'host', at: 'prop:table' }, { type: 'look', who: 'host', at: { point: [0, 1, 0] } },
    );
    expect(validateSketch(s)).toEqual([]);
  });

  it('during:"prev" needs a line right before it; nothing may follow the blackout', () => {
    const s = clone(mini());
    s.scenes[0].beats[0].items.unshift({ type: 'react', who: 'host', kind: 'smirk', during: 'prev' });
    s.scenes[0].beats[3].items.push({ type: 'line', who: 'host', text: 'one more thing' });
    const e = validateSketch(s).join('\n');
    expect(e).toMatch(/during:"prev" needs a line/);
    expect(e).toMatch(/nothing may follow the blackout/);
  });

  it('duplicate roles / seats / beat ids are errors; assertSketch throws SketchError', () => {
    const s = clone(mini());
    s.cast.push({ role: 'host', identity: 'x', seat: 'seat1', name: 'X' });
    s.scenes[0].beats.push({ ...s.scenes[0].beats[0] });
    const e = validateSketch(s).join('\n');
    expect(e).toMatch(/duplicate role "host"/);
    expect(e).toMatch(/two members on seat "seat1"/);
    expect(e).toMatch(/duplicate beat id "b1"/);
    expect(() => assertSketch(s)).toThrow(SketchError);
  });
});
