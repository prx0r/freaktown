/**
 * MouthTrack — deterministic mouth from the plan, sampled on the media clock.
 *
 *   envelope spans (measured from set.wav)  → when the mouth moves
 *   word timings + vowel groups              → syllable flaps + viseme shape
 *
 * Same input + same clock = same mouth on every replay (no analyser jitter).
 * The analyser path in LipSync.ts stays as the live-audio fallback
 * (mic, realtime TTS) when a plan carries no timings.
 */

import type { MouthSpan, PerformancePlan, WordTiming } from '@funnier/contracts';
import type { VisemeKey, Visemes } from '../avatars/types';

export interface MouthSample {
  open: number;
  visemes: Visemes;
  wordIndex: number;
}

const VOWEL_VISEME: Record<string, VisemeKey> = { a: 'aa', e: 'ee', i: 'ih', y: 'ih', o: 'oh', u: 'ou' };

function vowelGroups(word: string): VisemeKey[] {
  const groups = word.toLowerCase().replace(/[^a-z]/g, '').match(/[aeiouy]+/g) ?? [];
  const keys = groups.map((g) => VOWEL_VISEME[g[0]] ?? 'aa');
  return keys.length ? keys : ['aa'];
}

function findIndex<T extends { start_ms: number; end_ms: number }>(xs: T[], t: number): number {
  let lo = 0, hi = xs.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid].end_ms < t) lo = mid + 1;
    else if (xs[mid].start_ms > t) hi = mid - 1;
    else return mid;
  }
  return -1;
}

const RAMP_MS = 45;

export class MouthTrack {
  private words: WordTiming[];
  private spans: MouthSpan[];
  private groups: VisemeKey[][];

  constructor(words: WordTiming[] = [], spans: MouthSpan[] = []) {
    this.words = [...words].sort((a, b) => a.start_ms - b.start_ms);
    this.spans = [...spans].sort((a, b) => a.start_ms - b.start_ms);
    this.groups = this.words.map((w) => vowelGroups(w.word));
  }

  static fromPlan(plan: PerformancePlan | null | undefined, words?: WordTiming[]): MouthTrack | null {
    const w = words?.length ? words : plan?.word_timings ?? [];
    const s = plan?.mouth ?? [];
    if (!w.length && !s.length) return null;
    return new MouthTrack(w, s);
  }

  get hasEnvelope(): boolean { return this.spans.length > 0; }

  private gate(t: number): number {
    if (this.spans.length) {
      const i = findIndex(this.spans, t);
      if (i < 0) return 0;
      const sp = this.spans[i];
      return Math.min(1, (t - sp.start_ms) / RAMP_MS, (sp.end_ms - t) / RAMP_MS);
    }
    const i = findIndex(this.words, t);
    if (i < 0) return 0;
    const w = this.words[i];
    return Math.min(1, (t - w.start_ms) / RAMP_MS, (w.end_ms - t) / RAMP_MS);
  }

  sample(t: number): MouthSample {
    const vis: Visemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
    const g = Math.max(0, this.gate(t));
    const wi = findIndex(this.words, t);
    if (g <= 0) return { open: 0, visemes: vis, wordIndex: wi };
    let open = g * 0.55;
    let key: VisemeKey = 'aa';
    if (wi >= 0) {
      const w = this.words[wi];
      const groups = this.groups[wi];
      const u = Math.max(0, Math.min(0.999, (t - w.start_ms) / Math.max(1, w.end_ms - w.start_ms)));
      const phase = u * groups.length;
      key = groups[Math.floor(phase)];
      open = g * (0.25 + 0.75 * Math.abs(Math.sin(Math.PI * phase)));
    }
    vis[key] = open;
    if (key !== 'aa') vis.aa = open * 0.35;
    return { open, visemes: vis, wordIndex: wi };
  }
}
