/**
 * Set adapter — real build_set.py outputs (apps/live/public/sets) → PerformancePlan.
 */
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptSealedSet, deriveWordTimings, splitWords, wordWeight, type TimelineBeat } from '../src/plan/setAdapter';
import { MouthTrack } from '../src/performance/MouthTrack';

const SETS = path.resolve(__dirname, '../../../apps/live/public/sets');
const load = (id: string) => ({
  timeline: JSON.parse(fs.readFileSync(path.join(SETS, id, 'timeline.json'), 'utf8')) as TimelineBeat[],
  mouthCues: JSON.parse(fs.readFileSync(path.join(SETS, id, 'mouth_cues.json'), 'utf8')),
  setPlan: JSON.parse(fs.readFileSync(path.join(SETS, id, 'set_plan.json'), 'utf8')),
});

describe('setAdapter', () => {
  for (const id of ['captain-ata-ashcroft', 'the-algorithm']) {
    describe(id, () => {
      const input = load(id);
      const plan = adaptSealedSet(input);

      it('keeps every word of every beat, in order, inside its beat span', () => {
        const words = plan.word_timings!;
        const expected = input.timeline.flatMap((b) => splitWords(b.text));
        expect(words.map((w) => w.word)).toEqual(expected);
        for (const w of words) {
          const beat = input.timeline.find((b) => b.beat_id === w.beat_id)!;
          expect(w.start_ms).toBeGreaterThanOrEqual(beat.start_ms);
          expect(w.end_ms).toBeLessThanOrEqual(beat.end_ms);
          expect(w.end_ms).toBeGreaterThan(w.start_ms);
        }
        for (let i = 1; i < words.length; i++) expect(words[i].start_ms).toBeGreaterThanOrEqual(words[i - 1].start_ms);
        words.forEach((w, i) => expect(w.index).toBe(i));
      });

      it('lands words on voiced audio (envelope), not silence', () => {
        const words = plan.word_timings!;
        const voiced = (t: number) => input.mouthCues.some((m: { start_ms: number; end_ms: number }) => t >= m.start_ms - 1 && t <= m.end_ms + 1);
        // every word onset sits on measured speech (words may straddle a breath gap)
        const onsets = words.filter((w) => voiced(w.start_ms)).length;
        expect(onsets / words.length).toBeGreaterThan(0.95);
      });

      it('schedules cameras: opens wide, close-ups only on punchlines, ≥3 presets, no strobing', () => {
        const cams = plan.camera_cues!;
        expect(cams[0]).toMatchObject({ at_ms: 0, camera: 'WIDE_STAGE' });
        expect(new Set(cams.map((c) => c.camera)).size).toBeGreaterThanOrEqual(3);
        const punchSpans = input.timeline.filter((b) => b.type === 'punchline');
        for (const c of cams.filter((x) => x.camera === 'COMIC_CLOSE')) {
          expect(punchSpans.some((b) => c.at_ms >= b.start_ms - 200 && c.at_ms <= b.end_ms)).toBe(true);
        }
        expect(cams.some((c) => c.camera === 'COMIC_CLOSE')).toBe(true);
        for (let i = 1; i < cams.length; i++) {
          expect(cams[i].at_ms - cams[i - 1].at_ms).toBeGreaterThanOrEqual(1200);
          expect(cams[i].camera).not.toBe(cams[i - 1].camera);
        }
      });

      it('emits motion + face cues sorted, with the punchline expression from the delivery', () => {
        expect(plan.cue_count).toBe(plan.cues.length);
        for (let i = 1; i < plan.cues.length; i++) expect(plan.cues[i].at_ms).toBeGreaterThanOrEqual(plan.cues[i - 1].at_ms);
        const actions = new Set(plan.cues.map((c) => c.action));
        for (const a of ['gaze.audience', 'gesture.open', 'face.deadpan', 'pose.lean_forward', 'gesture.wave']) expect(actions).toContain(a);
        expect(plan.duration_ms).toBeGreaterThan(40000);
        expect(plan.character_id).toBe(input.setPlan.character_id);
      });

      it('feeds a MouthTrack that opens on speech and closes in silence', () => {
        const track = MouthTrack.fromPlan(plan)!;
        const w = plan.word_timings![10];
        const opens = Array.from({ length: 20 }, (_, i) => track.sample(w.start_ms + ((w.end_ms - w.start_ms) * i) / 20).open);
        expect(Math.max(...opens)).toBeGreaterThan(0.4);
        const gapStart = input.timeline[0].end_ms + 50;
        expect(track.sample(gapStart).open).toBe(0);
      });
    });
  }

  it('falls back to even spread when no envelope exists', () => {
    const tl: TimelineBeat[] = [{ beat_id: 'b1', type: 'setup', start_ms: 0, end_ms: 1000, text: 'one two three' }];
    const words = deriveWordTimings(tl, []);
    expect(words).toHaveLength(3);
    expect(words[0].start_ms).toBe(0);
    expect(words[2].end_ms).toBe(1000);
  });

  it('weights words by syllables + punctuation', () => {
    expect(wordWeight('cat')).toBe(1);
    expect(wordWeight('relationship.')).toBeGreaterThan(wordWeight('relationship'));
    expect(wordWeight('2019')).toBeGreaterThan(1);
  });
});
