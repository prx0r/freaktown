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

/** One real phonetic viseme (take visemes.json: TalkingHead-en output). */
export interface PhoneticViseme {
  viseme: string;
  time: number;
  end: number;
}

const VISEME_KEYS: VisemeKey[] = ['aa', 'ee', 'ih', 'ou', 'oh'];
/** Oculus viseme ID -> the 5-key mouth shape (subset the drivers own). */
function oculusToKey(v: string): VisemeKey {
  switch (v) {
    case 'E': return 'ee';
    case 'I': return 'ih';
    case 'O': return 'oh';
    case 'U': return 'ou';
    default: return 'aa'; // PP/FF/TH/DD/kk/CH/SS/nn/RR/sil -> jaw shapes
  }
}

/** visemes.json (take build) -> timeline the track samples. */
export function toPhonetics(doc: { visemes: string[]; vtimes: number[]; vdurations: number[] } | null | undefined): PhoneticViseme[] {
  if (!doc) return [];
  const n = Math.min(doc.visemes?.length ?? 0, doc.vtimes?.length ?? 0, doc.vdurations?.length ?? 0);
  const out: PhoneticViseme[] = [];
  for (let i = 0; i < n; i++) {
    const time = Number(doc.vtimes[i]) || 0;
    const dur = Math.max(20, Number(doc.vdurations[i]) || 0);
    out.push({ viseme: String(doc.visemes[i]), time, end: time + dur });
  }
  return out.sort((a, b) => a.time - b.time);
}

export class MouthTrack {
  private words: WordTiming[];
  private spans: MouthSpan[];
  private groups: VisemeKey[][];
  private phonemes: PhoneticViseme[];

  constructor(words: WordTiming[] = [], spans: MouthSpan[] = [], phonemes: PhoneticViseme[] = []) {
    this.words = [...words].sort((a, b) => a.start_ms - b.start_ms);
    this.spans = [...spans].sort((a, b) => a.start_ms - b.start_ms);
    this.groups = this.words.map((w) => vowelGroups(w.word));
    this.phonemes = [...phonemes].sort((a, b) => a.time - b.time);
  }

  static fromPlan(plan: PerformancePlan | null | undefined, words?: WordTiming[], phonemes?: PhoneticViseme[]): MouthTrack | null {
    const w = words?.length ? words : plan?.word_timings ?? [];
    const s = plan?.mouth ?? [];
    const p = phonemes?.length ? phonemes : (plan as unknown as { phonemes?: PhoneticViseme[] })?.phonemes ?? [];
    if (!w.length && !s.length && !p.length) return null;
    return new MouthTrack(w, s, p);
  }

  get hasEnvelope(): boolean { return this.spans.length > 0; }
  get hasPhonetics(): boolean { return this.phonemes.length > 0; }

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
    // Real phonetics win over vowel-group guessing when the take ships
    // visemes.json (TalkingHead-en full-word phonetics vs first-vowel).
    if (this.phonemes.length) {
      let lo = 0, hi = this.phonemes.length - 1, hit = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const p = this.phonemes[mid];
        if (t < p.time) hi = mid - 1;
        else if (t >= p.end) lo = mid + 1;
        else { hit = mid; break; }
      }
      if (hit >= 0) {
        const key = oculusToKey(this.phonemes[hit].viseme);
        const open = g * 0.6;
        vis[key] = open;
        if (key !== 'aa') vis.aa = open * 0.35;
        return { open, visemes: vis, wordIndex: wi };
      }
    }
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
