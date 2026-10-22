import { describe, expect, it } from 'vitest';
import { wordsMouth, textMouth } from '../src/sets/textMouth';
import { NEWS_STUDIO } from '../src/sets/definitions';

const words = [
  { word: 'Good', start_ms: 100, end_ms: 380 },
  { word: 'evening,', start_ms: 420, end_ms: 900 },
  { word: 'world.', start_ms: 1500, end_ms: 1900 },
];

describe('wordsMouth (visemes on measured words.json timings)', () => {
  it('is closed before the first word, between words and after the last', () => {
    expect(wordsMouth(words, 50).open).toBe(0);
    expect(wordsMouth(words, 1200).open).toBe(0); // the pause after "evening,"
    expect(wordsMouth(words, 1950).open).toBe(0);
  });
  it('opens inside a measured word and names that word', () => {
    const s = wordsMouth(words, 240);
    expect(s.open).toBeGreaterThan(0.5);
    expect(s.word).toBe(0);
    expect(wordsMouth(words, 1700).word).toBe(2);
  });
  it('differs from the even text spread where the real pause is', () => {
    // the text-only estimate keeps talking through 1200 ms; measured words do not
    expect(textMouth('Good evening, world.', 1900, 1200).open).toBeGreaterThan(0);
    expect(wordsMouth(words, 1200).open).toBe(0);
  });
});

describe('news studio set', () => {
  it('hides empty seat props and frames the wide for portrait', () => {
    expect(NEWS_STUDIO.hideEmptySeats).toBe(true);
    expect(NEWS_STUDIO.cameras.wide.portrait).toBeDefined();
  });
});
