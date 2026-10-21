import { describe, expect, it } from 'vitest';
import { ProsodyTrack } from '../src/performance/ProsodyTrack';

const frames = [
  { t_ms: 0, accent: 0, arousal: 0.2, phrase_end: 0 },
  { t_ms: 100, accent: 0.9, arousal: 0.3, phrase_end: 0 },
  { t_ms: 200, accent: 0, arousal: 0.2, phrase_end: 0 },
  { t_ms: 300, accent: 0, arousal: 0, phrase_end: 1 },
];

describe('ProsodyTrack', () => {
  it('is silent with no frames', () => {
    const p = new ProsodyTrack();
    expect(p.present).toBe(false);
    expect(p.sample(500)).toEqual({ brow: 0, eye: 0, blink: 0 });
  });

  it('lifts brows on accents and eyes on arousal, under the caps', () => {
    const p = new ProsodyTrack(frames);
    expect(p.present).toBe(true);
    const s = p.sample(150);
    expect(s.brow).toBeGreaterThan(0.2);
    expect(s.brow).toBeLessThanOrEqual(0.4);
    expect(s.eye).toBeGreaterThan(0);
  });

  it('blinks on phrase end then rests', () => {
    const p = new ProsodyTrack(frames);
    expect(p.sample(320).blink).toBeGreaterThan(0.5);
    expect(p.sample(900).blink).toBe(0);
  });

  it('stale frames decay to rest instead of freezing', () => {
    const p = new ProsodyTrack(frames);
    expect(p.sample(5000)).toEqual({ brow: 0, eye: 0, blink: 0 });
  });
});
