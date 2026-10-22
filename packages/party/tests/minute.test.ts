import { describe, expect, it } from 'vitest';
import { compileSketch, validateSketch } from '@funnier/sketch';
import { draftMinute, minuteSeconds, minuteToSketch, parsePremise, submitMinute, suggestDelivery } from '../src/minute';
import { getPartyIdentity } from '../src/identity';

const DEMO = 'users have infinite demands and no manners';
const hark = getPartyIdentity('agent.hark-lantern')!;

describe('write-a-minute', () => {
  it('parses the premise', () => {
    expect(parsePremise(DEMO)).toEqual({ subject: 'users', a: 'infinite demands', b: 'no manners' });
  });
  it('drafts a ~60 s bit with setup/punch structure, tags and a callback, in the performer voice', () => {
    const m = draftMinute(DEMO, hark);
    const roles = m.lines.map((l) => l.role);
    expect(roles.filter((r) => r === 'punch').length).toBeGreaterThanOrEqual(3);
    expect(roles).toContain('tag');
    expect(roles).toContain('callback');
    expect(m.lines.at(-1)!.text).toContain('Hark. A punchline approaches.');
    const s = minuteSeconds(m.lines);
    expect(s).toBeGreaterThan(45);
    expect(s).toBeLessThan(80);
    expect(draftMinute(DEMO, hark)).toEqual(m);
  });
  it('auto-suggests delivery; the human can override and it survives compile', () => {
    const m = draftMinute(DEMO, hark);
    const punch = m.lines.find((l) => l.role === 'punch')!;
    expect(punch).toMatchObject({ delivery: 'deadpan', pause_ms: 700, hold_ms: 1200 });
    expect(m.lines.find((l) => l.role === 'act-out')!.delivery).toBe('manic');
    const edited = { ...m, lines: m.lines.map((l) => (l.id === punch.id ? { ...l, delivery: 'manic' as const, text: 'Edited punch line.' } : l)) };
    const sk = minuteToSketch(edited);
    expect(validateSketch(sk)).toEqual([]);
    const items = sk.scenes[0].beats.flatMap((b) => b.items);
    expect(items.find((i) => i.type === 'line' && i.id === punch.id)).toMatchObject({ text: 'Edited punch line.', emotion: 'surprised' });
    expect(items.some((i) => i.type === 'hold_for_laugh')).toBe(true);
    expect(suggestDelivery(edited.lines, hark).find((l) => l.id === punch.id)!.delivery).toBe('deadpan');
  });
  it('re-suggesting delivery keeps the emphasis the human set (including none)', () => {
    const m = draftMinute(DEMO, hark);
    const punch = m.lines.find((l) => l.role === 'punch')!;
    const tag = m.lines.find((l) => l.role === 'tag')!;
    const cb = m.lines.find((l) => l.role === 'callback')!;
    const edited = m.lines.map((l) => (l.id === punch.id ? { ...l, emphasis: ['seagull', 'phone'], emphasis_user: true, delivery: 'warm' as const }
      : l.id === tag.id ? { ...l, emphasis: ['eyes'], emphasis_user: true }
        : l.id === cb.id ? { ...l, emphasis: [], emphasis_user: true } : l));
    const again = suggestDelivery(edited, hark);
    expect(again.find((l) => l.id === punch.id)).toMatchObject({ emphasis: ['seagull', 'phone'], emphasis_user: true, delivery: 'deadpan' });
    expect(again.find((l) => l.id === tag.id)!.emphasis).toEqual(['eyes']);
    expect(again.find((l) => l.id === cb.id)!.emphasis).toEqual([]);
    // lines the human never touched still get the agent's emphasis
    const otherPunch = m.lines.filter((l) => l.role === 'punch')[1];
    expect(again.find((l) => l.id === otherPunch.id)!.emphasis).toEqual(otherPunch.emphasis);
    expect(otherPunch.emphasis.length).toBe(1);
  });
  it('submits as a performance (funnier.sketch/v1 on the comedy club) that compiles', () => {
    const sub = submitMinute(draftMinute(DEMO, hark), 'identities/agent.hark-lantern.glb', '2026-10-22T00:00:00Z');
    expect(sub.performance).toMatchObject({ schema: 'funnier.sketch/v1', set: 'comedy-club' });
    const c = compileSketch(sub.performance);
    expect(c.duration_ms).toBeGreaterThan(40_000);
    expect(c.events.some((e) => e.type === 'dialogue.line')).toBe(true);
  });
});
