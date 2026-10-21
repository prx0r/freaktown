/**
 * Mouth from text when a line has no audio: words spread over the line's
 * duration, one open/close per syllable-ish vowel group, viseme from the vowel.
 * Same doctrine as the sealed-set adapter (word vowels → visemes); used only
 * for bodies that really have a mouth (BASIC jaw, VRM visemes).
 */
import type { Visemes } from '../avatars/types';

const VOWEL_VIS: Record<string, keyof Visemes> = { a: 'aa', e: 'ee', i: 'ih', o: 'oh', u: 'ou', y: 'ih' };

export interface TextMouthSample { open: number; visemes: Visemes; word: number }

export function estimateLineMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(900, Math.round(words * 330 + 300));
}

export function textMouth(text: string, durationMs: number, tMs: number): TextMouthSample {
  const zero: Visemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (!words.length || tMs < 0 || tMs >= durationMs) return { open: 0, visemes: zero, word: -1 };
  const groups = words.map((w) => Math.max(1, (w.toLowerCase().match(/[aeiouy]+/g) ?? []).length));
  const total = groups.reduce((a, b) => a + b, 0);
  const speech = durationMs * 0.92;
  const pos = (tMs / speech) * total;
  let acc = 0;
  for (let i = 0; i < words.length; i++) {
    if (pos < acc + groups[i]) {
      const local = pos - acc;
      const syl = Math.floor(local);
      const phase = local - syl;
      const vowels = words[i].toLowerCase().match(/[aeiouy]+/g) ?? ['a'];
      const v = vowels[Math.min(syl, vowels.length - 1)][0];
      const open = Math.sin(Math.PI * phase) * (i === words.length - 1 ? 0.8 : 1) * 0.85;
      const vis = { ...zero, [VOWEL_VIS[v] ?? 'aa']: open };
      return { open, visemes: vis, word: i };
    }
    acc += groups[i];
  }
  return { open: 0, visemes: zero, word: words.length - 1 };
}
