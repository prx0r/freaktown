#!/usr/bin/env node
/**
 * th_visemes.mjs — text + word timings -> Oculus viseme timeline.
 *
 * Uses the vendored TalkingHead English rules (../vendor/talkinghead/
 * lipsync-en.mjs, MIT) so offline takes and the live stage share one
 * letter-to-sound implementation. No dependencies, runs anywhere node
 * exists (GPU bank boxes included).
 *
 * stdin:  {"words": [{"text": "hello", "start_ms": 0, "end_ms": 420}]}
 * stdout: {"words": [...], "wtimes": [...], "wdurations": [...],
 *          "visemes": [...], "vtimes": [...], "vdurations": [...]}
 * (TalkingHead speakAudio shape — the stage consumes it directly.)
 *
 * Each word's relative viseme units are scaled to fit its measured span.
 * Unknown/empty words emit nothing (never pad with fake visemes).
 */
import { readFileSync } from 'node:fs';
import { LipsyncEn } from '../vendor/talkinghead/lipsync-en.mjs';

const input = JSON.parse(readFileSync(0, 'utf8'));
const words = (input.words || []).filter(
  (w) => w && typeof w.text === 'string' && w.text.trim().length > 0
);

const eng = new LipsyncEn();
const out = { words: [], wtimes: [], wdurations: [], visemes: [], vtimes: [], vdurations: [] };

for (const w of words) {
  const text = w.text.trim();
  const start = Math.max(0, Number(w.start_ms) || 0);
  const end = Math.max(start, Number(w.end_ms) || start);
  const cleaned = eng.preProcessText(text);
  if (!cleaned) continue;
  // One viseme pass per whitespace-separated token.
  let cursor = start;
  const tokens = cleaned.split(/\s+/).filter(Boolean);
  const span = Math.max(1, end - start);
  // Weight each token by its relative viseme mass so long words get time.
  const masses = tokens.map((tok) => {
    const r = eng.wordsToVisemes(tok);
    return { tok, r, mass: r.durations.reduce((a, b) => a + b, 0) || 1 };
  });
  const totalMass = masses.reduce((a, m) => a + m.mass, 0) || 1;
  for (const { tok, r, mass } of masses) {
    const wLen = (span * mass) / totalMass;
    const wStart = cursor;
    cursor += wLen;
    out.words.push(tok);
    out.wtimes.push(Math.round(wStart));
    out.wdurations.push(Math.round(Math.min(wLen, end - wStart)));
    const rel = r.durations.reduce((a, b) => a + b, 0) || 1;
    let t = wStart;
    for (let i = 0; i < r.visemes.length; i++) {
      const d = (r.durations[i] / rel) * wLen;
      out.visemes.push(r.visemes[i]);
      out.vtimes.push(Math.round(t));
      out.vdurations.push(Math.max(20, Math.round(d)));
      t += d;
    }
  }
}

process.stdout.write(JSON.stringify(out));
