/**
 * The consistency checker: does a line (or a whole set) sound like this
 * character, and does it stay inside their rails? Deterministic rules only.
 *
 * Levels: "error" = taboo / safety rail / forbidden word (must fix before
 * submit), "warn" = off-voice (register, contractions, length, exclamations,
 * delivery that fights the physicality), "info" = craft notes (no tic or
 * signature word anywhere, mechanism outside their range, catchphrase overuse).
 */
import type { CharacterSet, CharacterTheory, SetLine } from './types';

export interface VoiceFlag { line: string | null; level: 'error' | 'warn' | 'info'; rule: string; message: string; suggestion?: string }
export interface VoiceReport { character: string; score: number; ok: boolean; flags: VoiceFlag[]; checked: number }

const CONTRACTION = /\b[a-z]+'(s|re|ve|ll|d|t|m)\b/i;
const SLANG = ['gonna', 'wanna', 'gotta', 'dude', 'bro', 'lol', 'omg', 'yeah', 'nah', 'kinda', 'sorta', 'ya', 'vibes', 'lit', 'sus'];
const FORMAL_REGISTER = /formal|precise|official|economical|measured|butler|courteous/i;
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const has = (text: string, phrase: string) => new RegExp(`(^|[^a-z])${esc(phrase.toLowerCase())}([^a-z]|$)`).test(text.toLowerCase());

/** Check one line of text (optionally with its role/delivery) against the theory. */
export function checkLine(t: CharacterTheory, text: string, meta: Partial<SetLine> = {}): VoiceFlag[] {
  const id = meta.id ?? null;
  const f: VoiceFlag[] = [];
  const v = t.voice;
  const isActOut = meta.role === 'act-out';
  for (const w of v.forbidden_words) if (has(text, w)) f.push({ line: id, level: 'error', rule: 'forbidden-word', message: `"${w}" is never in ${t.name}'s voice`, suggestion: v.substitutions[w] ? `use "${v.substitutions[w]}"` : 'cut or rephrase' });
  for (const s of t.taboo.never_says) if (has(text, s)) f.push({ line: id, level: 'error', rule: 'taboo-never-says', message: `${t.name} never says "${s}"` });
  for (const s of t.taboo.never_topics) for (const w of s.toLowerCase().split(/[,/]| or /).map((x) => x.trim()).filter((x) => x.length > 3)) if (has(text, w)) f.push({ line: id, level: 'error', rule: 'safety-topic', message: `touches a never-topic: ${s}` });
  for (const s of t.taboo.never_targets) for (const w of s.toLowerCase().split(/[,/]| or /).map((x) => x.trim()).filter((x) => x.length > 3 && !/people|groups|audience/.test(x))) if (has(text, w)) f.push({ line: id, level: 'error', rule: 'safety-target', message: `aims at a never-target: ${s}` });
  for (const [a, b] of Object.entries(v.substitutions)) if (has(text, a) && !v.forbidden_words.includes(a)) f.push({ line: id, level: 'warn', rule: 'substitution', message: `${t.name} would say "${b}", not "${a}"`, suggestion: text.replace(new RegExp(esc(a), 'gi'), b) });
  if (!isActOut) {
    if (v.contractions === 'never' && CONTRACTION.test(text)) f.push({ line: id, level: 'warn', rule: 'contractions', message: `${t.name} does not use contractions`, suggestion: text.replace(/\b(\w+)n't\b/gi, '$1 not').replace(/\bI'm\b/g, 'I am').replace(/\b(\w+)'re\b/gi, '$1 are').replace(/\b(\w+)'ll\b/gi, '$1 will').replace(/\bit's\b/gi, 'it is') });
    if (!v.exclamations && text.includes('!')) f.push({ line: id, level: 'warn', rule: 'exclamation', message: `${t.name} never raises their voice on the page`, suggestion: text.replace(/!/g, '.') });
    if (FORMAL_REGISTER.test(v.register)) for (const s of SLANG) if (has(text, s)) f.push({ line: id, level: 'warn', rule: 'register', message: `"${s}" breaks the ${v.register} register` });
    const longest = Math.max(0, ...text.split(/[.?!:;]+/).map((s) => s.split(/\s+/).filter(Boolean).length));
    if (longest > v.max_sentence_words) f.push({ line: id, level: 'warn', rule: 'sentence-length', message: `${longest}-word sentence; ${t.name} tops out around ${v.max_sentence_words}` });
  }
  if (meta.role === 'punch' && meta.delivery === 'manic' && t.physicality.energy < 0.4) f.push({ line: id, level: 'warn', rule: 'delivery-fit', message: `manic punch from a low-energy (${t.physicality.energy}) ${t.physicality.delivery_default} character`, suggestion: `set_delivery ${id} style=${t.physicality.delivery_default}` });
  if (meta.role === 'punch' && meta.text && meta.text.split(/\s+/).length > 28) f.push({ line: id, level: 'info', rule: 'punch-length', message: 'long punch: the laugh word should be near the end; consider splitting into punch + tag' });
  if (meta.mechanism && !t.writes.includes(meta.mechanism) && (t.taste.weights[meta.mechanism] ?? 0) < -0.3) f.push({ line: id, level: 'info', rule: 'mechanism', message: `${meta.mechanism} is outside ${t.name}'s range (taste ${t.taste.weights[meta.mechanism]})` });
  return f;
}

/** Check a whole set: every line, plus set-level voice markers. */
export function checkSet(t: CharacterTheory, s: Pick<CharacterSet, 'lines'>): VoiceReport {
  const flags: VoiceFlag[] = s.lines.flatMap((l) => checkLine(t, l.text, l));
  const all = s.lines.map((l) => l.text).join(' ');
  const markers = [...t.voice.verbal_tics, ...t.voice.signature_words, ...t.catchphrases];
  if (markers.length && !markers.some((m) => has(all, m.split(/[.,]/)[0].trim()))) flags.push({ line: null, level: 'info', rule: 'voice-markers', message: `no verbal tic, signature word or catchphrase anywhere; the set could belong to anyone` });
  for (const c of t.catchphrases) { const n = s.lines.filter((l) => has(l.text, c)).length; if (n > 2) flags.push({ line: null, level: 'info', rule: 'catchphrase-overuse', message: `"${c}" used ${n} times; twice is a runner, three times is a crutch` }); }
  const punches = s.lines.filter((l) => l.role === 'punch').length;
  if (s.lines.length > 6 && punches === 0) flags.push({ line: null, level: 'warn', rule: 'structure', message: 'no punch lines in the set' });
  return report(t, flags, s.lines.length);
}

export function report(t: CharacterTheory, flags: VoiceFlag[], checked: number): VoiceReport {
  const w = { error: 1, warn: 0.35, info: 0.08 } as const;
  const penalty = flags.reduce((n, f) => n + w[f.level], 0);
  return { character: t.id, score: Math.max(0, Math.round((1 - penalty / Math.max(1, checked)) * 1000) / 1000), ok: !flags.some((f) => f.level === 'error'), flags, checked };
}
