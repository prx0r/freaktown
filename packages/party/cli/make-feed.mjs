#!/usr/bin/env node
/**
 * Synthetic blendshape stream (the "fake webcam" for /tnts?feed=recorded).
 *   node packages/party/cli/make-feed.mjs --grin 6000 --dur 60000 --fps 20 -o apps/live/public/tnts/feeds/grin-after-6s.json
 * Frames carry ARKit/MediaPipe blendshape names (mouthSmileL/R, cheekSquintL/R, eyeSquintL/R, jawOpen, eyeBlinkL/R)
 * with small seeded jitter and blinks; a neutral face until --grin, then a held grin.
 * --dark a-b adds a low-light window (luma 0.05).
 */
import fs from 'node:fs';
import path from 'node:path';
const a = Object.fromEntries(process.argv.slice(2).reduce((acc, k, i, arr) => (k.startsWith('-') ? [...acc, [k.replace(/^-+/, ''), arr[i + 1]]] : acc), []));
const grin = Number(a.grin ?? 6000), dur = Number(a.dur ?? 60000), fps = Number(a.fps ?? 20);
const [darkA, darkB] = (a.dark ?? '').split('-').map(Number);
let s = 12345;
const rnd = () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296);
const r3 = (x) => Math.round(x * 1000) / 1000;
const frames = [];
for (let t = 0; t <= dur; t += Math.round(1000 / fps)) {
  const g = t >= grin ? Math.min(1, (t - grin) / 250) : 0;
  const smile = 0.04 + rnd() * 0.04 + g * 0.82;
  const squint = 0.06 + rnd() * 0.04 + g * 0.6;
  const blink = t % 3700 < 120 ? 0.9 : 0.05;
  frames.push({ t, luma: darkA <= t && t < darkB ? 0.05 : r3(0.45 + rnd() * 0.05), bs: {
    mouthSmileLeft: r3(smile), mouthSmileRight: r3(smile * 0.97), cheekSquintLeft: r3(squint), cheekSquintRight: r3(squint),
    eyeSquintLeft: r3(squint * 0.9), eyeSquintRight: r3(squint * 0.9), jawOpen: r3(0.03 + g * 0.2 + rnd() * 0.02),
    eyeBlinkLeft: blink, eyeBlinkRight: blink, browInnerUp: r3(0.05 + rnd() * 0.03) } });
}
const out = a.o ?? 'feed.json';
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify({ kind: 'synthetic-blendshapes', fps, grin_ms: grin, frames }));
console.log(out, frames.length, 'frames');
