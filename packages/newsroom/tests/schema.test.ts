import { describe, expect, it } from 'vitest';
import { validateRundown, assertRundown, imageAllowed, type RundownV1 } from '../src';
import fixture from './fixtures/rundown.goodnight.json';

const clone = (): RundownV1 => JSON.parse(JSON.stringify(fixture));

describe('rundown schema', () => {
  it('accepts the fixture', () => {
    const r = validateRundown(fixture);
    expect(r.errors).toEqual([]);
    expect(r.ok).toBe(true);
    expect(() => assertRundown(fixture)).not.toThrow();
  });
  it('rejects a non-object and the wrong schema id', () => {
    expect(validateRundown(null).ok).toBe(false);
    const x = clone() as unknown as Record<string, unknown>; x.schema = 'nope';
    expect(validateRundown(x).errors.join()).toMatch(/schema must be/);
  });
  it('needs an anchor and at least one read', () => {
    const x = clone(); x.cast.anchors = [];
    expect(validateRundown(x).errors.join()).toMatch(/at least one anchor/);
    const y = clone(); y.segments = [{ id: 'a', title: 'A', kind: 'section', stories: [{ id: 'b', pieces: [{ type: 'wall', headline: 'h' }] }] }];
    expect(validateRundown(y).errors.join()).toMatch(/no reads/);
  });
  it('checks reporter chairs against the cast', () => {
    const x = clone();
    x.segments[1].stories[0].pieces[2] = { type: 'reporter_read', chair: 'reporter:xx', text: 'hello' };
    expect(validateRundown(x).errors.join()).toMatch(/not a reporter in cast/);
  });
  it('flags duplicate ids, bad layouts, numbers cards without a figure', () => {
    const x = clone();
    x.segments[2].stories[0].id = 's1';
    x.segments[1].stories[0].pieces[0] = { type: 'wall', headline: 'h', layout: 'numbers' };
    (x.segments[1].stories[1].pieces[0] as { layout?: string }).layout = 'spinny';
    const e = validateRundown(x).errors.join('\n');
    expect(e).toMatch(/duplicated/);
    expect(e).toMatch(/needs a figure/);
    expect(e).toMatch(/layout must be/);
  });
  it('checks measured words are ordered and well-formed', () => {
    const x = clone();
    x.segments[0].stories[0].pieces[3] = { type: 'anchor_read', text: 'a b', words: [{ word: 'a', start_ms: 300, end_ms: 400 }, { word: 'b', start_ms: 100, end_ms: 50 }] };
    const e = validateRundown(x).errors.join('\n');
    expect(e).toMatch(/out of order/);
    expect(e).toMatch(/ends before it starts/);
  });
  it('studio reporters need a seat', () => {
    const x = clone(); x.cast.reporters = [{ chair: 'r', name: 'R', locale: 'EN', presence: 'studio' }];
    expect(validateRundown(x).errors.join()).toMatch(/needs a seat/);
  });
  it('only verbatim-ok lanes may show images', () => {
    expect(imageAllowed('verbatim-ok')).toBe(true);
    expect(imageAllowed('fact-rewrite')).toBe(false);
    expect(imageAllowed(undefined)).toBe(false);
  });
});
