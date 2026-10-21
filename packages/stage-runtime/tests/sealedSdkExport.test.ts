/**
 * Cross-repo contract: characters repo sealed-set export -> adaptSealedSet.
 *
 * Fixture produced by audition/seal_set.py (delivery_engine --seal) on
 * buddha-ultimate-deadpan (Norm-harvested deadpan style + Fish cast voice).
 * set.wav intentionally absent — the adapter never needs audio; mouth_cues
 * carry the envelope. See characters docs/SPEC-FREAK-SDK.md.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { adaptSealedSet } from '../src/plan/setAdapter';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SET = path.join(HERE, 'fixtures', 'sealed-buddha');

const load = () => ({
  timeline: JSON.parse(fs.readFileSync(path.join(SET, 'timeline.json'), 'utf8')),
  mouthCues: JSON.parse(fs.readFileSync(path.join(SET, 'mouth_cues.json'), 'utf8')),
  setPlan: JSON.parse(fs.readFileSync(path.join(SET, 'set_plan.json'), 'utf8')),
});

describe('sealed SDK export (characters -> sealed-set.v1)', () => {
  const input = load();
  const plan = adaptSealedSet(input);

  it('adapts: beats, words, duration', () => {
    expect(plan.beats!.length).toBe(input.timeline.length);
    expect(plan.word_timings!.length).toBeGreaterThan(30);
    expect(plan.duration_ms).toBeGreaterThan(20000);
    expect(plan.character_id).toBe('buddha-ultimate-deadpan');
  });

  it('lands word onsets on voiced audio (envelope), >95%', () => {
    const voiced = (t: number) =>
      input.mouthCues.some((m: { start_ms: number; end_ms: number }) =>
        t >= m.start_ms - 1 && t <= m.end_ms + 1);
    const onsets = plan.word_timings!.filter((w) => voiced(w.start_ms)).length;
    expect(onsets / plan.word_timings!.length).toBeGreaterThan(0.95);
  });

  it('character actions reach the stage: koan_hold -> freeze + deadpan face', () => {
    expect(plan.cues.some((c) => c.action === 'locomotion.freeze')).toBe(true);
    expect(plan.cues.some((c) => c.action === 'face.deadpan')).toBe(true);
  });

  it('camera: opens wide, close-up on punchline, no strobing', () => {
    const cams = plan.camera_cues!;
    expect(cams[0]).toMatchObject({ at_ms: 0, camera: 'WIDE_STAGE' });
    expect(cams.some((c) => c.camera === 'COMIC_CLOSE')).toBe(true);
    for (let i = 1; i < cams.length; i++) {
      expect(cams[i].at_ms - cams[i - 1].at_ms).toBeGreaterThanOrEqual(1200);
    }
  });

  it('flat deadpan profile: energy 0.4 -> stillness 0.6', () => {
    expect(plan.energy).toBeCloseTo(0.4, 5);
    expect(plan.stillness).toBeCloseTo(0.6, 5);
  });
});
