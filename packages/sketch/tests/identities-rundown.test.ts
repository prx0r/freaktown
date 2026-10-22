import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
// @ts-expect-error — plain .mjs build script (node), no types
import { buildIdentities } from '../scripts/build-identities.mjs';
import { DEFAULT_SKETCH_TIMING, getIdentity, listIdentities, resolveCastEntry, showRundownTemplate, defaultCastSize, RECURRING_SKETCH_SHARE } from '../src';
import { REPO } from './helpers';

describe('identities (bridge to assets/character-meshes/cast)', () => {
  it('snapshot is in sync with the canonical cast files', () => {
    const cur = JSON.parse(fs.readFileSync(path.join(REPO, 'packages/sketch/src/identities.generated.json'), 'utf8'));
    expect(cur).toEqual(buildIdentities());
    expect(listIdentities().length).toBe(JSON.parse(fs.readFileSync(path.join(REPO, 'assets/character-meshes/cast/cast-index.json'), 'utf8')).count);
  });
  it('resolves registered identities with their motion-style traits', () => {
    const r = resolveCastEntry({ role: 'x', identity: 'pog.sergeant-sled', seat: 'seat1' }, DEFAULT_SKETCH_TIMING);
    expect(r.registered).toBe(true);
    expect(r.name).toBe(getIdentity('pog.sergeant-sled')!.name);
    expect(r.react_delay_ms).toBe(120);
    expect(resolveCastEntry({ role: 'r', identity: 'pog.the-algorithm', seat: 's' }, DEFAULT_SKETCH_TIMING).avatar_url).toBe('basic:robot');
  });
  it('unknown identities need an inline name', () => {
    expect(() => resolveCastEntry({ role: 'x', identity: 'guest.nobody', seat: 'seat1' }, DEFAULT_SKETCH_TIMING)).toThrow(/give it a name/);
    expect(resolveCastEntry({ role: 'x', identity: 'guest.nobody', seat: 'seat1', name: 'Nobody' }, DEFAULT_SKETCH_TIMING).registered).toBe(false);
  });
});

describe('show rundown template (structure stats)', () => {
  const stats = JSON.parse(fs.readFileSync(path.join(REPO, 'packages/sketch/data/structure-stats.json'), 'utf8'));
  it('stats carry aggregate numbers only, with credit', () => {
    expect(stats.source.dataset_url).toBe('https://github.com/hhllcks/snldb');
    expect(stats.source.upstream).toMatch(/snlarchives\.net/);
    expect(stats.order.first_segment_is_cold_open).toBeGreaterThan(0.9);
  });
  it('cold open → monologue → sketches → news desk → … → closer', () => {
    const r = showRundownTemplate();
    const types = r.slots.map((s) => s.type);
    expect(types[0]).toBe('cold_open');
    expect(types[1]).toBe('monologue');
    expect(types[types.length - 1]).toBe('closer');
    expect(types.filter((t) => t === 'sketch').length).toBe(Math.round(stats.per_episode.live_sketches.median));
    const desk = types.indexOf('news_desk');
    expect(desk).toBeGreaterThan(2);
    expect(desk).toBeLessThan(types.length - 2);
    expect(types.indexOf('sketch')).toBeLessThan(desk);
  });
  it('cast-size defaults come from the stats', () => {
    expect(defaultCastSize('sketch')).toBe(Math.round(stats.cast_size_per_segment.sketch.median));
    expect(defaultCastSize('sketch', 4)).toBe(4);
    expect(RECURRING_SKETCH_SHARE).toBeCloseTo(stats.recurring.sketch.share, 5);
  });
});
