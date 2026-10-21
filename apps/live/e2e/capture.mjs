/**
 * Frame-stepped stage capture → JPEG frames (for an MP4 / frame strip).
 * Uses /stage?capture=1: the runtime renders exactly the frame for media
 * time t (deterministic: same plan + same t = same frame), no realtime.
 * The performance is loaded through the stage's own LocalTransport
 * (performance.preload event), like any show.
 *
 *   node e2e/capture.mjs <set-id> <startMs> <endMs> <fps> <outDir> [WxH] [extra-query]
 * Env: CHROMIUM_PATH, BASE_URL (default http://127.0.0.1:4173)
 */
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const [setId = 'captain-ata-ashcroft', s0 = '0', s1 = '10000', fpsArg = '25', out = '/tmp/frames', size = '1280x720', extra = 'cpuskin=1'] = process.argv.slice(2);
const [W, H] = size.split('x').map(Number);
const fps = Number(fpsArg);
const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', (e) => console.error('pageerror', e.message));
await page.goto(`${base}/stage/capture-${setId}?capture=1&captions=0&${extra}`);
await page.waitForFunction(() => !!window.__stage);
const catalog = await (await fetch(`${base}/sets/index.json`)).json();
const set = catalog.sets.find((s) => s.id === setId);
await page.evaluate(async (set) => {
  const tr = window.__stage.runtime.consumer.transport;
  tr.reset();
  await tr.command('performance.preload', {
    performance_id: `cap-${set.id}`, set_url: set.set_url, audio_url: set.audio_url,
    avatar_url: set.avatar_url, character_name: set.character_name,
  });
}, set);
await page.waitForFunction(() => window.__stage.telemetry().status === 'READY', null, { timeout: 120000 });
const start = Number(s0), end = Number(s1);
const step = 1000 / fps;
const log = [];
// warm-up frame (shader compile) + establish cue state up to start
await page.evaluate((ms) => window.__stage.runtime.captureAt(ms), Math.max(0, start - 1));
for (let i = 0, t = start; t < end; i++, t = start + i * step) {
  const idx = Math.round((t - Number(process.env.FRAME0_MS ?? start)) / step);
  const url = await page.evaluate((ms) => window.__stage.runtime.captureAt(ms), t);
  fs.writeFileSync(path.join(out, `f_${String(idx).padStart(5, '0')}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
  const tl = await page.evaluate(() => { const x = window.__stage.telemetry(); return { cam: x.camera, mouth: x.mouth, word: x.word }; });
  log.push({ t: Math.round(t), ...tl });
}
fs.appendFileSync(path.join(out, 'capture_log.jsonl'), log.map((l) => JSON.stringify(l)).join('\n') + '\n');
console.log(`captured ${log.length} frames ${start}-${end}ms; cams:`, [...new Set(log.map((l) => l.cam))].join(','));
await browser.close();
