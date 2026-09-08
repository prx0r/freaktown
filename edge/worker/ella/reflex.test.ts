/**
 * EllaReflex tests — deterministic triggers over synthetic sense pairs.
 */
import { describe, expect, it } from 'vitest';
import { evaluateReflex, microLine, type ReflexInput } from './reflex';
import type { EllaSenseV1 } from '../../src/contracts/show';

function sense(overrides: Partial<EllaSenseV1> = {}): EllaSenseV1 {
  return {
    episode_id: 'ep1',
    phase: 'set_active',
    active_appearance_id: 'perf1',
    seq: 100,
    is_paused: false,
    set_time_ms: null,
    crowd: {
      laugh_events: 0, claps: 0, boos: 0,
      crickets: 0, groans: 0, unique_laughers: 0,
    },
    pot_cents: 0,
    updated_at: '2026-09-08T20:00:00.000Z',
    ...overrides,
  };
}

function at(base: EllaSenseV1, secondsLater: number): string {
  return new Date(Date.parse(base.updated_at) + secondsLater * 1000).toISOString();
}

describe('evaluateReflex', () => {
  it('fires iris_widen on a laugh spike', () => {
    const prev = sense();
    const curr = sense({
      seq: 120,
      crowd: { ...sense().crowd, laugh_events: 60, unique_laughers: 20 },
      updated_at: at(prev, 10),
    });
    const out = evaluateReflex({ prev, curr });
    expect(out.map((a) => a.action)).toContain('iris_widen');
    expect(out[0]).toMatchObject({ trigger: 'audience_laugh_spike', source: 'reflex-v1', latency_ms: 0 });
  });

  it('stays quiet on ordinary chuckles', () => {
    const prev = sense();
    const curr = sense({
      seq: 101,
      crowd: { ...sense().crowd, laugh_events: 2 },
      updated_at: at(prev, 10),
    });
    expect(evaluateReflex({ prev, curr })).toEqual([]);
  });

  it('fires stillness on dead silence during a set', () => {
    const prev = sense();
    const curr = sense({ seq: 110, updated_at: at(prev, 10) });
    const out = evaluateReflex({ prev, curr });
    const still = out.find((a) => a.action === 'stillness');
    expect(still?.trigger).toBe('dead_silence');
    expect(still?.text).toBe(microLine(110));
  });

  it('fires desk_flash on a $100+ tip', () => {
    const prev = sense();
    const curr = sense({ seq: 111, pot_cents: 15000, updated_at: at(prev, 5) });
    const out = evaluateReflex({ prev, curr });
    expect(out.map((a) => a.action)).toContain('desk_flash');
  });

  it('fires look_at_chatgpt on wtf spikes and chatgpt reveals', () => {
    const prev = sense();
    const wtf = sense({
      seq: 112,
      crowd: { ...sense().crowd, groans: 20, boos: 10 },
      updated_at: at(prev, 5),
    });
    expect(evaluateReflex({ prev, curr: wtf }).map((a) => a.action)).toContain('look_at_chatgpt');

    const calm = sense({ seq: 113, updated_at: at(prev, 5) });
    const out = evaluateReflex({ prev, curr: calm, recentEventTypes: ['judge.chatgpt.locked'] });
    expect(out.map((a) => a.action)).toContain('look_at_chatgpt');
  });

  it('does nothing when paused or between sets', () => {
    const prev = sense();
    const paused = sense({
      seq: 114,
      is_paused: true,
      crowd: { ...sense().crowd, laugh_events: 999 },
      updated_at: at(prev, 1),
    });
    expect(evaluateReflex({ prev, curr: paused })).toEqual([]);
    const between = sense({ seq: 115, active_appearance_id: null, updated_at: at(prev, 1) });
    expect(evaluateReflex({ prev, curr: between })).toEqual([]);
  });

  it('micro-lines rotate deterministically', () => {
    expect(microLine(0)).toBe('oh.');
    expect(microLine(12)).toBe('oh.');
    expect(microLine(1)).not.toBe(microLine(2));
  });
});
