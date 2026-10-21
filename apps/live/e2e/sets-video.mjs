// Record ~real-time video of each set's demo (Playwright recordVideo → webm), for ffmpeg → MP4.
// usage: node e2e/sets-video.mjs <setId> <seconds> <outdir> [baseURL]
import { chromium } from '@playwright/test';
import fs from 'node:fs';
const [setId = 'podcast', secs = '14', out = '/tmp/setvid', base = 'http://127.0.0.1:4173'] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctl = await browser.newContext({ viewport: { width: 1000, height: 800 } });
const ep = `vid-${setId}-${Date.now()}`;
// control + play in one context, the recorded stage needs the same storage → share via one context with video on
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: out, size: { width: 1280, height: 720 } } });
await ctl.close();
const control = await ctx.newPage();
await control.goto(`${base}/control/${ep}`);
await control.getByTestId('reset').click();
const stage = await ctx.newPage();
await stage.goto(`${base}/stage/${ep}?quality=low&cpuskin=1`);
await stage.waitForFunction(() => !!window.__stage);
await control.getByTestId('set-picker').selectOption(setId);
await control.getByTestId('set-demo').click();
await stage.bringToFront();
await stage.waitForFunction((id) => window.__setStage?.telemetry().setId === id, setId, { timeout: 90000 });
const t0 = Date.now();
let play = null;
if (setId === 'poker-table') {
  play = await ctx.newPage();
  await play.goto(`${base}/play/${ep}/seat/4`);
  await play.getByTestId('play-name').fill('You');
  await play.getByTestId('play-join').click();
  await stage.bringToFront();
}
while (Date.now() - t0 < Number(secs) * 1000) {
  if (play && (await play.getByTestId('play-turn').count())) {
    const c = play.getByTestId('act-check');
    if (await c.count()) await c.click(); else await play.getByTestId('act-call').click();
    await stage.bringToFront();
  }
  await stage.waitForTimeout(400);
}
const cuts = await stage.evaluate(() => window.__setStage.telemetry().cuts.map((c) => c.cue));
const v = stage.video();
await ctx.close();
const p = await v.path();
fs.writeFileSync(`${out}/${setId}.json`, JSON.stringify({ video: p, startOffsetMs: 0, cuts }));
console.log('VIDEO', p, 'cuts', cuts.length, cuts.join(' | '));
await browser.close();
