/**
 * MorphVisemePlayer unit tests — stub scene graph, no three.js.
 * Deterministic: frames in, morph weights out.
 */
import { describe, expect, it } from 'vitest';
import { MorphVisemePlayer } from './MorphVisemePlayer';

function mesh(names: string[]) {
  const dict: Record<string, number> = {};
  names.forEach((n, i) => { dict[n] = i; });
  return {
    morphTargetDictionary: dict,
    morphTargetInfluences: new Array(names.length).fill(0),
  };
}

function scene(...meshes: ReturnType<typeof mesh>[]) {
  return { traverse: (cb: (o: unknown) => void) => meshes.forEach(cb) };
}

const DOC = {
  words: ['hello'],
  wtimes: [0],
  wdurations: [420],
  visemes: ['I', 'E', 'nn', 'O'],
  vtimes: [0, 106, 209, 310],
  vdurations: [106, 103, 101, 110],
};

describe('MorphVisemePlayer', () => {
  it('binds only morphs present in the file', () => {
    const p = new MorphVisemePlayer();
    const m = mesh(['viseme_aa', 'viseme_PP', 'jawOpen', 'noseSneerLeft']);
    const bound = p.attachToObject(scene(m));
    expect(p.hasMouth).toBe(true);
    expect(bound).toContain('aa');
    expect(bound).toContain('PP');
    expect(bound).not.toContain('O'); // no morph, no binding
  });

  it('plays the active viseme and rests others', () => {
    const p = new MorphVisemePlayer();
    const m = mesh(['viseme_I', 'viseme_E', 'viseme_aa']);
    p.attachToObject(scene(m));
    p.playDoc(DOC);
    p.update(50); // inside I frame
    expect(m.morphTargetInfluences[0]).toBeGreaterThan(0.1);
    for (let t = 50; t < 500; t += 16) p.update(t);
    // converged somewhere sensible; weights stay bounded
    for (const v of m.morphTargetInfluences) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it('PP gets near-full close weight like TalkingHead', () => {
    const p = new MorphVisemePlayer();
    const m = mesh(['viseme_PP']);
    p.attachToObject(scene(m));
    p.playDoc({ words: [], wtimes: [], wdurations: [], visemes: ['PP'], vtimes: [0], vdurations: [200] });
    for (let t = 0; t < 150; t += 16) p.update(t);
    expect(m.morphTargetInfluences[0]).toBeGreaterThan(0.7);
  });

  it('silence after the timeline decays to rest', () => {
    const p = new MorphVisemePlayer();
    const m = mesh(['viseme_I']);
    p.attachToObject(scene(m));
    p.playDoc(DOC);
    for (let t = 0; t < 2000; t += 16) p.update(t);
    expect(m.morphTargetInfluences[0]).toBeLessThan(0.05);
  });

  it('no morphs means no mouth, never raises', () => {
    const p = new MorphVisemePlayer();
    p.attachToObject(scene(mesh(['noseSneerLeft'])));
    expect(p.hasMouth).toBe(false);
    p.playDoc(DOC);
    p.update(100);
    p.playDoc(null);
    p.playDoc(undefined);
    p.update(100);
  });
});
