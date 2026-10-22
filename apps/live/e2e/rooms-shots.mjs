#!/usr/bin/env node
/**
 * rooms-shots — screenshots of /rooms (lobby + each room view) at desktop and mobile.
 * Rooms run in the tab (?local=1), so no server is needed. Serves apps/live/dist.
 *   node apps/live/e2e/rooms-shots.mjs --out <dir> [--wait 9000] [--viewports desktop,mobile]
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, '../dist');
const a = {};
for (let i = 2; i < process.argv.length; i += 2) a[process.argv[i].slice(2)] = process.argv[i + 1];
const out = a.out ?? '.';
const wait = Number(a.wait ?? 9000);
fs.mkdirSync(out, { recursive: true });
const VIEW = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true } };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.glb': 'model/gltf-binary', '.vrm': 'model/gltf-binary', '.png': 'image/png', '.svg': 'image/svg+xml' };
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
try {
  for (const vp of String(a.viewports ?? 'desktop,mobile').split(',')) {
    const v = VIEW[vp];
    const ctx = await browser.newContext({ viewport: { width: v.width, height: v.height }, deviceScaleFactor: v.deviceScaleFactor ?? 1, isMobile: !!v.isMobile });
    const page = await ctx.newPage();
    await page.goto(`${base}/rooms?local=1`);
    await page.getByTestId('room-card-newsroom').waitFor();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(out, `rooms-lobby-${vp}.png`), fullPage: true });
    console.log(path.join(out, `rooms-lobby-${vp}.png`));
    for (const id of (a.rooms ?? 'podcast,poker,tnts,newsroom').split(',')) {
      await page.goto(`${base}/rooms/${id}?local=1`);
      await page.waitForTimeout(wait);
      const f = path.join(out, `rooms-${id}-${vp}.png`);
      await page.screenshot({ path: f });
      console.log(f);
    }
    await ctx.close();
  }
} finally { await browser.close(); server.close(); }
