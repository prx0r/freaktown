#!/usr/bin/env node
/**
 * newsroom-timeline — compile a rundown on the program clock, no browser.
 *
 *   node packages/newsroom/cli/timeline.mjs <rundown.json> [--words words.json] [-o timeline.json]
 *
 * --words takes the same forms as render.mjs: an episode-wide [{word,start_ms,end_ms}] array,
 * {"words": [...]}, or {"lines": {"<lineId>": [relative words]}} (per read, measured from TTS).
 * Output: {duration_ms, timing_source, estimated, lines[{id,kind,seat,text,start_ms,end_ms,words}],
 *          jingles[], stories[], segments[], shots[], events[], warnings[]}.
 * This is how an engine puts its audio on the same clock the picture will use: lay each line's
 * wav at lines[i].start_ms, the jingles at jingles[i].start_ms, then render with the same --words.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const rundownPath = args.find((a, i) => !a.startsWith('-') && !['-o', '--words'].includes(args[i - 1]));
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
if (!rundownPath) { console.error('usage: timeline.mjs <rundown.json> [--words words.json] [-o out.json]'); process.exit(2); }

const { build } = await import('esbuild');
const bundle = path.join(os.tmpdir(), `newsroom-sdk-${process.pid}.mjs`);
await build({ entryPoints: [path.join(here, '../src/index.ts')], bundle: true, format: 'esm', platform: 'node', outfile: bundle, logLevel: 'error' });
const sdk = await import(pathToFileURL(bundle).href);
fs.rmSync(bundle, { force: true });

const rundown = JSON.parse(fs.readFileSync(rundownPath, 'utf8'));
let timings = {};
const wp = opt('--words');
if (wp) {
  const w = JSON.parse(fs.readFileSync(wp, 'utf8'));
  if (Array.isArray(w)) timings = { episodeWords: w };
  else if (Array.isArray(w.words)) timings = { episodeWords: w.words };
  else if (w.lines) timings = { lines: w.lines };
}
const v = sdk.validateRundown(rundown);
if (!v.ok) { console.error('invalid rundown:', v.errors.join('; ')); process.exit(1); }
const style = sdk.getShowStyle(rundown.show_style);
const prog = sdk.layoutProgram(rundown, style, timings);
const show = sdk.compile(rundown, timings);
const out = {
  rundown: rundown.id, style: style.id, duration_ms: show.duration_ms ?? prog.duration_ms,
  timing_source: prog.timingSource, estimated: prog.estimated, cadence: style.cadence,
  lines: prog.lines.map((l) => ({ id: l.id, kind: l.kind, chair: l.chair, seat: l.seat, storyId: l.storyId, segmentId: l.segmentId, text: l.text, start_ms: l.start_ms, end_ms: l.end_ms, estimated: l.estimated, words: l.words })),
  jingles: prog.jingles, stories: prog.stories, segments: prog.segments,
  shots: show.shots, events: show.events, warnings: show.warnings ?? [],
};
const o = opt('-o');
if (o) fs.writeFileSync(o, JSON.stringify(out, null, 1)); else process.stdout.write(JSON.stringify(out));
console.error(`[timeline] ${out.duration_ms}ms · ${out.lines.length} lines · ${out.shots.length} shots · ${out.timing_source}`);
