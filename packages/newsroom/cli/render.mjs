#!/usr/bin/env node
/**
 * newsroom-render — rundown.json (+ optional audio + words.json) → MP4, headless.
 *
 * Same approach as apps/live/e2e/capture.mjs: the built live app (apps/live/dist)
 * is served locally, the /newsroom page runs in capture mode (no realtime: the
 * stage renders exactly the frame for show time t), Playwright screenshots each
 * frame (canvas + DOM overlays), ffmpeg encodes. Frames are kept in a work dir
 * so an interrupted render resumes where it stopped.
 *
 *   node packages/newsroom/cli/render.mjs <rundown.json> -o out.mp4
 *        [--words words.json]   measured words: [{word,start_ms,end_ms}] (episode clock)
 *                               or {"lines": {"<lineId>": [...]}} (per line, relative)
 *        [--audio master.wav]   mux this audio (else silent; --tone = quiet placeholder tone)
 *        [--size 1280x720] [--fps 25] [--from ms] [--to ms] [--quality low|high]
 *        [--shots 30000,52000 --viewports desktop,mobile --shots-dir dir]   screenshots only
 *        [--newsset <id>]       baked Blender studio instead of the procedural one (late-night|goodnight|breaking)
 *        [--build]              rebuild apps/live first (default: build only if dist is missing)
 *        [--keep-frames]
 * Env: CHROMIUM_PATH (system Chromium; linux-arm64 has no Playwright-managed one).
 * Writes <out>.json beside the MP4: timing source (measured / ESTIMATED), shots, warnings.
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { spawnSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');
const dist = path.join(repo, 'apps/live/dist');

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '-o') a.out = argv[++i];
    else if (k.startsWith('--')) {
      const key = k.slice(2);
      const v = argv[i + 1];
      if (v === undefined || v.startsWith('--')) a[key] = true; else { a[key] = v; i++; }
    } else a._.push(k);
  }
  return a;
}

const args = parseArgs(process.argv.slice(2));
const rundownPath = args._[0];
if (!rundownPath) { console.error('usage: render.mjs <rundown.json> -o out.mp4 [--words words.json] [--audio a.wav] ...'); process.exit(2); }
const rundown = JSON.parse(fs.readFileSync(rundownPath, 'utf8'));
let timings = {};
if (args.words) {
  const w = JSON.parse(fs.readFileSync(args.words, 'utf8'));
  if (Array.isArray(w)) timings = { episodeWords: w };
  else if (Array.isArray(w.words)) timings = { episodeWords: w.words };
  else if (w.lines) timings = { lines: w.lines };
  else throw new Error('words.json: expected an array, {words:[...]} or {lines:{...}}');
}
const [W, H] = String(args.size ?? '1280x720').split('x').map(Number);
const fps = Number(args.fps ?? 25);
const quality = args.quality === 'high' ? 'high' : 'low';
const out = path.resolve(args.out ?? `${path.basename(rundownPath, '.json')}.mp4`);

// 1) the live app build
if (args.build || !fs.existsSync(path.join(dist, 'index.html'))) {
  console.log('[render] building apps/live …');
  const b = spawnSync('npm', ['run', 'build', '-w', '@funnier/live'], { cwd: repo, stdio: 'inherit' });
  if (b.status !== 0) process.exit(b.status ?? 1);
}

// 2) a tiny static server (SPA fallback), no network
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.vrm': 'model/gltf-binary', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent((req.url ?? '/').split('?')[0]);
  let f = path.join(dist, u);
  if (!f.startsWith(dist) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(dist, 'index.html');
  res.setHeader('Content-Type', MIME[path.extname(f)] ?? 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

// 3) the stage
const { chromium } = await import('@playwright/test');
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});

async function openStage(vw, vh, mobile = false) {
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(`${base}/newsroom/render?capture=1&quality=${quality}&cpuskin=1${args.newsset ? `&newsset=${encodeURIComponent(args.newsset)}` : ''}`);
  await page.waitForFunction(() => !!window.__newsroom, null, { timeout: 60000 });
  const info = await page.evaluate((x) => window.__newsroom.load(x), { rundown, timings });
  return { ctx, page, info };
}

try {
  if (args.shots) {
    // screenshots only
    const times = String(args.shots).split(',').map(Number);
    const vps = String(args.viewports ?? 'desktop').split(',');
    const dir = path.resolve(args['shots-dir'] ?? path.dirname(out));
    fs.mkdirSync(dir, { recursive: true });
    for (const vp of vps) {
      const [vw, vh, mob] = vp === 'mobile' ? [390, 844, true] : [W, H, false];
      const { ctx, page } = await openStage(vw, vh, mob);
      for (const t of times) {
        // step up to t so eased moves/creeps land exactly as in the MP4
        for (let s = 0; s < t; s += 1000) await page.evaluate((ms) => window.__newsroom.renderAt(ms), s);
        await page.evaluate((ms) => window.__newsroom.renderAt(ms), t);
        const file = path.join(dir, `${path.basename(out, '.mp4')}_${vp}_${t}.png`);
        await page.screenshot({ path: file });
        const tel = await page.evaluate(() => { const x = window.__newsroom.telemetry(); return { cam: x.camera, wall: x.wall, lt: x.overlay.lowerThird, env: x.environment, envError: x.envError }; });
        console.log('SHOT', file, JSON.stringify(tel));
      }
      await ctx.close();
    }
  } else {
    const { page, info } = await openStage(W, H);
    console.log(`[render] ${info.duration_ms}ms · ${info.shots} shots · timing ${info.timing_source}${info.estimated ? ' (ESTIMATED)' : ''}`);
    for (const w of info.warnings) console.log('[render] warning:', w);
    const from = Number(args.from ?? 0);
    const to = Math.min(Number(args.to ?? info.duration_ms), info.duration_ms);
    const framesDir = `${out}.frames`;
    fs.mkdirSync(framesDir, { recursive: true });
    const n = Math.ceil(((to - from) / 1000) * fps);
    const t0 = Date.now();
    const camLog = [];
    for (let i = 0; i < n; i++) {
      const t = from + (i * 1000) / fps;
      const file = path.join(framesDir, `f_${String(i).padStart(6, '0')}.jpg`);
      if (fs.existsSync(file) && fs.statSync(file).size > 0) {
        // resume: the frame is on disk; still step the clock now and then so events apply in order
        if (i % fps === 0) await page.evaluate((ms) => window.__newsroom.renderAt(ms), t);
        continue;
      }
      await page.evaluate((ms) => window.__newsroom.renderAt(ms), t);
      const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
      fs.writeFileSync(file, buf);
      if (i % fps === 0) {
        const tel = await page.evaluate(() => { const x = window.__newsroom.telemetry(); return { cam: x.camera, wall: x.wall?.layout, lt: x.overlay.lowerThird?.name ?? null }; });
        camLog.push({ t: Math.round(t), ...tel });
        if (i % (fps * 5) === 0) console.log(`[render] frame ${i}/${n} t=${Math.round(t)}ms cam=${tel.cam} wall=${tel.wall} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
      }
    }
    // 4) encode
    const audioIn = args.audio ? ['-i', path.resolve(args.audio)]
      : args.tone ? ['-f', 'lavfi', '-i', 'sine=frequency=196:sample_rate=48000,volume=0.02']
      : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'];
    const ff = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(framesDir, 'f_%06d.jpg'), ...audioIn,
      '-map', '0:v', '-map', '1:a', '-t', String(n / fps), '-vf', 'scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p', '-c:v', 'libx264', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-crf', '20', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out], { stdio: 'inherit' });
    if (ff.status !== 0) throw new Error('ffmpeg failed');
    const tl = await page.evaluate(() => window.__newsroom.timeline());
    fs.writeFileSync(out.replace(/\.mp4$/, '') + '.json', JSON.stringify({
      rundown: rundown.id, style: tl.style, duration_ms: tl.duration_ms, rendered: { from, to, fps, size: `${W}x${H}`, frames: n },
      timing_source: tl.timing_source, estimated: tl.estimated, wpm: tl.wpm, cadence: tl.cadence,
      audio: args.audio ? path.basename(args.audio) : args.tone ? 'placeholder tone' : 'silent',
      shots: tl.shots, warnings: tl.warnings, camera_log: camLog,
    }, null, 1));
    if (!args['keep-frames']) fs.rmSync(framesDir, { recursive: true, force: true });
    console.log('MP4', out, `${n} frames`, `${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
} finally {
  await browser.close();
  server.close();
}
