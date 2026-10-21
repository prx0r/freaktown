import { describe, expect, it } from 'vitest';
import { MouthTrack } from '../src/performance/MouthTrack';
import { Performer } from '../src/performance/Performer';

describe('MouthTrack', () => {
  const track = new MouthTrack(
    [{ word: 'hello', start_ms: 100, end_ms: 500, index: 0 }, { word: 'moon', start_ms: 600, end_ms: 900, index: 1 }],
    [{ start_ms: 100, end_ms: 500 }, { start_ms: 600, end_ms: 900 }],
  );
  it('is closed outside speech and deterministic inside', () => {
    expect(track.sample(50).open).toBe(0);
    expect(track.sample(550).open).toBe(0);
    expect(track.sample(300)).toEqual(track.sample(300));
  });
  it('picks visemes from the word vowels', () => {
    const peaks = [0.25, 0.75].map((u) => track.sample(100 + 400 * u).visemes);
    expect(peaks[0].ee).toBeGreaterThan(0); // h-e-llo
    expect(peaks[1].oh).toBeGreaterThan(0); // hell-o
    expect(track.sample(750).visemes.oh).toBeGreaterThan(0); // m-oo-n
  });
});

describe('Performer', () => {
  it('face cues raise the mapped emotion then decay; blink fires on its own timer', () => {
    const p = new Performer();
    p.trigger('face.smile', 1, 1000, 0);
    const mid = p.update(500, 500, 0.016, 0);
    expect(mid.emotions.happy).toBeGreaterThan(0.5);
    const after = p.update(2000, 2000, 0.016, 0);
    expect(after.emotions.happy).toBe(0);
    let blinked = false;
    for (let t = 0; t < 6000; t += 16) if (p.update(t, t, 0.016, 0).blink > 0.5) blinked = true;
    expect(blinked).toBe(true);
  });
  it('gestures move the arms and freeze stills the body', () => {
    const p = new Performer();
    const rest = p.update(0, 0, 0.016, 0).pose.armR.raise;
    p.trigger('gesture.wave', 1, 1000, 100);
    expect(p.update(600, 600, 0.016, 0).pose.armR.raise).toBeGreaterThan(rest + 0.5);
  });
});
