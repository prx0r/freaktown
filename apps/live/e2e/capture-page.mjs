#!/usr/bin/env node
/**
 * capture-page — deterministic screenshots / MP4 of any capture-mode page that
 * exposes window.<api>.renderAt(ms) + .ready + .duration_ms (/tnts, /minute, /alien-news).
 * Serves apps/live/dist (SPA fallback) on a local port; Playwright drives the page; ffmpeg encodes.
 *
 *   node apps/live/e2e/capture-page.mjs --path "/tnts?capture=1" --api __tnts \
 *        [--shots 12000,30000 --viewports desktop,mobile --shots-dir out/]   screenshots
 *        [--mp4 out.mp4 --fps 12 --from 0 --to 60000 --size 1280x720]        video (silent)
 * Env: CHROMIUM_PATH (system Chromium on linux-arm64).
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, '../dist');
const a = {};
for (let i = 2; i < process.argv.length; i++) { const k = process.argv[i]; if (k.startsWith('--')) { const v = process.argv[i + 1]; if (!v || v.startsWith('--')) a[k.slice(2)] = true; else { a[k.slice(2)] = v; i++; } } }
const api = a.api ?? '__tnts';
const VIEW = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true } };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.glb': 'model/gltf-binary', '.vrm': 'model/gltf-binary', '.png': 'image/png', '.svg': 'image/svg+xml', '.mp3': 'audio/mpeg', '.wav': 'audio/wav' };

const server = http.createServer((req, res) => {
  const u = decodeURIComponent((req.url ?? '/').split('?')[0]);
  let f = path.join(dist, u);
  if (!f.startsWith(dist) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(dist, 'index.html');
  res.setHeader('Content-Type', MIME[path.extname(f)] ?? 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });

async function open(viewport) {
  const ctx = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: viewport.deviceScaleFactor ?? 1, isMobile: !!viewport.isMobile });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('[page]', e.message));
  await page.goto(base + a.path);
  await page.waitForFunction((n) => window[n]?.ready === true, api, { timeout: 120000 });
  return { ctx, page };
}

try {
  if (a.shots) {
    const dir = a['shots-dir'] ?? '.';
    fs.mkdirSync(dir, { recursive: true });
    for (const vp of String(a.viewports ?? 'desktop').split(',')) {
      const { ctx, page } = await open(VIEW[vp]);
      for (const ms of String(a.shots).split(',').map(Number)) {
        // walk up to the shot so stateful cues (cast, faces) are applied in order
        for (let t = 0; t < ms; t += 2000) await page.evaluate(([n, x]) => window[n].renderAt(x), [api, t]);
        await page.evaluate(([n, x]) => window[n].renderAt(x), [api, ms]);
        await page.waitForTimeout(300);
        const out = path.join(dir, `${a.prefix ?? 'shot'}-${vp}-${ms}.png`);
        await page.screenshot({ path: out });
        console.log(out);
      }
      await ctx.close();
    }
  }
  if (a.mp4) {
    const [w, h] = String(a.size ?? '1280x720').split('x').map(Number);
    const { ctx, page } = await open({ width: w, height: h });
    const dur = await page.evaluate((n) => window[n].duration_ms, api);
    const fps = Number(a.fps ?? 12), from = Number(a.from ?? 0), to = Math.min(Number(a.to ?? dur), dur);
    // --frames <dir>: frames persist (indexed by show time) so long renders resume across runs;
    // --budget <s>: stop after that many seconds (re-run to continue), then encode when complete.
    const tmp = a.frames ? (fs.mkdirSync(a.frames, { recursive: true }), a.frames) : fs.mkdtempSync(path.join(os.tmpdir(), 'cap-'));
    const t0 = Date.now(), budget = Number(a.budget ?? 1e9) * 1000;
    let i = 0, done = true;
    for (let t = from; t <= to; t += 1000 / fps, i++) {
      const f = path.join(tmp, `f${String(i).padStart(5, '0')}.jpg`);
      if (fs.existsSync(f)) continue;
      if (Date.now() - t0 > budget) { done = false; break; }
      await page.evaluate(([n, x]) => window[n].renderAt(x), [api, Math.round(t)]);
      await page.screenshot({ path: f, type: 'jpeg', quality: 85 });
      if (i % 60 === 0) console.log('frame', i, Math.round(t));
    }
    await ctx.close();
    if (!done) { console.log('PARTIAL', i, 'frames so far; re-run to continue'); process.exitCode = 3; }
    else {
    const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(tmp, 'f%05d.jpg'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', a.mp4], { stdio: 'inherit' });
    if (r.status !== 0) throw new Error('ffmpeg failed');
    if (!a.frames) fs.rmSync(tmp, { recursive: true, force: true });
    console.log(a.mp4, i, 'frames', `${((to - from) / 1000).toFixed(1)}s`);
    }
  }
} finally {
  await browser.close();
  server.close();
}
