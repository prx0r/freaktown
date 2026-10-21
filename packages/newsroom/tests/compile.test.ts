import { describe, expect, it } from 'vitest';
import { compile, toShowEvents, eventsBetween, type RundownV1 } from '../src';
import goodnight from './fixtures/rundown.goodnight.json';

describe('compile', () => {
  const out = compile(goodnight as RundownV1);

  it('starts with set.load + set.theme + auto director off', () => {
    expect(out.events.slice(0, 3).map((e) => e.type)).toEqual(['set.load', 'set.theme', 'set.auto_director']);
    expect(out.events[0].payload).toMatchObject({ setId: 'news-studio', cast: [{ seat: 'anchor1', name: 'Test Anchor' }] });
    expect(out.events[1].payload).toMatchObject({ style: 'goodnight', palette: { accent: '#F5C86B' }, wall: { family: 'paper-sunrise' } });
  });

  it('events are time-ordered and only use contract event types', () => {
    const allowed = new Set(['set.load', 'set.theme', 'set.auto_director', 'set.camera', 'overlay.headline', 'overlay.lower_third', 'overlay.ticker', 'dialogue.line', 'face.expression', 'audio.sting']);
    for (let i = 1; i < out.events.length; i++) expect(out.events[i].t_ms).toBeGreaterThanOrEqual(out.events[i - 1].t_ms);
    for (const e of out.events) expect(allowed.has(e.type), e.type).toBe(true);
  });

  it('maps to ShowEvents and steps by window', () => {
    const se = toShowEvents(out, '2026-10-20T22:00:00.000Z');
    expect(se[0]).toMatchObject({ seq: 1, type: 'set.load', actor: 'newsroom', created_at: '2026-10-20T22:00:00.000Z' });
    expect(eventsBetween(out, -1, 0).length).toBeGreaterThanOrEqual(3);
  });

  it('matches the snapshot (timeline shape)', () => {
    const shape = {
      duration_ms: out.duration_ms,
      estimated: out.estimated,
      shots: out.shots.map((s) => `${s.start_ms}-${s.end_ms} ${s.cue} ${s.reason}${s.move_ms ? ` move${s.move_ms}` : ''}${s.creep ? ' creep' : ''}`),
      events: out.events.map((e) => `${e.t_ms} ${e.type}${e.type === 'set.camera' ? ` ${String(e.payload.cue)}` : e.type === 'overlay.headline' ? ` [${String(e.payload.layout)}] ${String(e.payload.text)}` : ''}`),
    };
    expect(shape).toMatchSnapshot();
  });
});
