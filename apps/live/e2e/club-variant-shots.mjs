/**
 * Stand-up stage with the Blender-built comedy-club variants (?clubset=<id>), performer in place:
 * desktop + mobile stills per variant, plus the procedural default for comparison.
 *
 *   node e2e/club-variant-shots.mjs <outDir> [variants=procedural,dive,late-night-tv,basement-open-mic,theatre]
 * Env: CHROMIUM_PATH, BASE_URL (default http://127.0.0.1:4173), SET_ID (stand-up set, default captain-ata-ashcroft)
 * Writes <outDir>/<variant>_<desktop|mobile>_<wide|medium>.jpg and report.json (variant status, mic gap).
 */
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const [out = '/tmp/club-variants', list = 'procedural,dive,late-night-tv,basement-open-mic,theatre'] = process.argv.slice(2);
const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
const setId = process.env.SET_ID || 'captain-ata-ashcroft';
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const catalog = await (await fetch(`${base}/sets/index.json`)).json();
const set = catalog.sets.find((s) => s.id === setId);
const report = {};
for (const variant of list.split(',')) {
  for (const [dev, vp] of [['desktop', { width: 1280, height: 720 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport: vp });
    page.on('pageerror', (e) => console.error('pageerror', e.message));
    const q = variant === 'procedural' ? '' : `&clubset=${variant}`;
    await page.goto(`${base}/stage/club-${variant}?capture=1&captions=0&cpuskin=1${q}`);
    await page.waitForFunction(() => !!window.__stage);
    await page.evaluate(() => window.__stage.runtime.variantReady);
    await page.evaluate(async (set) => {
      const tr = window.__stage.runtime.consumer.transport;
      tr.reset();
      await tr.command('performance.preload', {
        performance_id: `club-${set.id}`, set_url: set.set_url, audio_url: set.audio_url,
        avatar_url: set.avatar_url, character_name: set.character_name,
      });
    }, set);
    await page.waitForFunction(() => window.__stage.telemetry().status === 'READY', null, { timeout: 180000 });
    for (let ms = 0; ms < 6000; ms += 500) await page.evaluate((m) => window.__stage.runtime.captureAt(m), ms);
    await page.evaluate(() => { const r = window.__stage.runtime; if (r.currentPlan) r.currentPlan.camera_cues = []; });
    let k = 0;
    for (const cam of ['WIDE_STAGE', 'COMIC_MEDIUM']) {
      const url = await page.evaluate(([c, m]) => {
        const r = window.__stage.runtime;
        r.cutCamera(c, 'human_director');
        return r.captureAt(m);
      }, [cam, 6000 + 40 * ++k]);
      const name = cam === 'WIDE_STAGE' ? 'wide' : 'medium';
      fs.writeFileSync(path.join(out, `${variant}_${dev}_${name}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
    }
    report[`${variant}/${dev}`] = await page.evaluate(() => {
      const r = window.__stage.runtime;
      return { variant: r.setVariantStatus(), mic: typeof r.micReport === 'function' ? r.micReport() : null };
    });
    console.log(variant, dev, JSON.stringify(report[`${variant}/${dev}`]));
    await page.close();
  }
}
fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 1));
await browser.close();
