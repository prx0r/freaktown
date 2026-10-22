/**
 * Stand-up framing check: frame-stepped stills of the comedy-club stage
 * (desktop + mobile × wide + close) for before/after comparisons.
 *
 *   node e2e/standup-shots.mjs <outDir> [set-id] [tMs]
 * Env: CHROMIUM_PATH, BASE_URL (default http://127.0.0.1:4173)
 * Writes <outDir>/{desktop,mobile}_{wide,medium,close}.jpg and mic.json
 * (mic-to-mouth distance from the runtime, when the runtime exposes it).
 */
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const [out = '/tmp/standup', setId = 'captain-ata-ashcroft', tArg = '9000'] = process.argv.slice(2);
const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const catalog = await (await fetch(`${base}/sets/index.json`)).json();
const set = catalog.sets.find((s) => s.id === setId);
const report = {};
for (const [dev, vp] of [['desktop', { width: 1280, height: 720 }], ['mobile', { width: 390, height: 844 }]]) {
  const page = await browser.newPage({ viewport: vp });
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  await page.goto(`${base}/stage/shots-${setId}?capture=1&captions=0&cpuskin=1`);
  await page.waitForFunction(() => !!window.__stage);
  await page.evaluate(async (set) => {
    const tr = window.__stage.runtime.consumer.transport;
    tr.reset();
    await tr.command('performance.preload', {
      performance_id: `shots-${set.id}`, set_url: set.set_url, audio_url: set.audio_url,
      avatar_url: set.avatar_url, character_name: set.character_name,
    });
  }, set);
  await page.waitForFunction(() => window.__stage.telemetry().status === 'READY', null, { timeout: 120000 });
  const t = Number(tArg);
  for (let ms = 0; ms < t; ms += 500) await page.evaluate((m) => window.__stage.runtime.captureAt(m), ms);
  // freeze the plan's own camera cues so each still shows the requested preset
  await page.evaluate(() => { const r = window.__stage.runtime; if (r.currentPlan) r.currentPlan.camera_cues = []; });
  let k = 0;
  for (const cam of ['WIDE_STAGE', 'COMIC_MEDIUM', 'COMIC_CLOSE']) {
    const url = await page.evaluate(([c, m]) => {
      const r = window.__stage.runtime;
      r.cutCamera(c, 'human_director');
      return r.captureAt(m);
    }, [cam, t + 40 * ++k]);
    const name = { WIDE_STAGE: 'wide', COMIC_MEDIUM: 'medium', COMIC_CLOSE: 'close' }[cam];
    fs.writeFileSync(path.join(out, `${dev}_${name}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
  }
  report[dev] = await page.evaluate(() => {
    const r = window.__stage.runtime;
    return typeof r.micReport === 'function' ? r.micReport() : null;
  });
  await page.close();
}
fs.writeFileSync(path.join(out, 'mic.json'), JSON.stringify(report, null, 1));
console.log('shots ->', out, JSON.stringify(report));
await browser.close();
