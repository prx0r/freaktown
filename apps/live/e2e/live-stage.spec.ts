/**
 * Live stage e2e — /control drives /stage through the LocalTransport
 * (BroadcastChannel + localStorage), exactly as an operator would.
 *
 * Verifies: audio clock advances on the WebAudio transport, mouth +
 * expression channels change, blink fires, ≥2 camera cuts (plan auto-cuts
 * + a human cut), pause freezes the clock, resume advances it, crowd
 * reaction reaches the stage as an event, and no console errors.
 *
 * Headless note: SwiftShader on linux-arm64 loses the WebGL context on
 * three's bone/morph textures, so the stage runs with ?cpuskin=1 (CPU
 * skinning) and ?quality=low here. Real GPUs use the default path.
 */

import { test, expect, type Page, type BrowserContext, type ConsoleMessage } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SHOTS = process.env.SHOTS_DIR || '/workspace/work/funnier-live/shots';
fs.mkdirSync(SHOTS, { recursive: true });

type Tele = {
  status: string; timeMs: number; mouth: number; camera: string; blinks: number;
  visemes: Record<string, number>; emotions: Record<string, number>;
  cuts: Array<{ camera: string; set_time_ms: number; source: string }>;
  avatar: { kind: string; name: string; mouthMode: string } | null;
  avatarFallback: string | null; mouthSource: string; word: string | null;
};

function watchConsole(page: Page, name: string, sink: string[]): void {
  page.on('console', (m: ConsoleMessage) => {
    if (m.type() === 'error') sink.push(`${name} console.error: ${m.text()}`);
  });
  page.on('pageerror', (e) => sink.push(`${name} pageerror: ${e.message}`));
}

const tele = (stage: Page) => stage.evaluate(() => window.__stage!.telemetry() as unknown as Tele);

async function openPair(context: BrowserContext, ep: string, stageQuery: string, errors: string[]) {
  const stage = await context.newPage();
  watchConsole(stage, 'stage', errors);
  await stage.goto(`/stage/${ep}?${stageQuery}`);
  await stage.waitForFunction(() => !!window.__stage);
  const control = await context.newPage();
  watchConsole(control, 'control', errors);
  await control.goto(`/control/${ep}`);
  await expect(control.getByTestId('link-status')).toContainText('connected');
  await control.getByTestId('reset').click();
  return { stage, control };
}

async function startSet(control: Page, stage: Page, setId: string) {
  await expect(control.locator('[data-testid=set-select] option')).toHaveCount(3);
  await control.getByTestId('set-select').selectOption(setId);
  await control.getByTestId('start').click();
  await stage.bringToFront(); // hidden tabs throttle rAF
  await stage.waitForFunction(() => window.__stage!.telemetry().status === 'PLAYING', null, { timeout: 90_000 });
  await expect(control.getByTestId('show-state')).toHaveText('live');
}

test('control drives the stage: clock, mouth, face, cameras, pause/resume, reactions', async ({ context }) => {
  const errors: string[] = [];
  const { stage, control } = await openPair(context, 'e2e-vrm', 'debug=1&quality=low&cpuskin=1', errors);
  await startSet(control, stage, 'captain-ata-ashcroft');

  const t0 = await tele(stage);
  expect(t0.avatar?.kind).toBe('vrm');
  expect(t0.avatar?.mouthMode).toBe('viseme');
  expect(t0.avatarFallback).toBeNull();
  expect(t0.mouthSource).toBe('plan');

  const samples: Tele[] = [];
  for (let i = 0; i < 20; i++) {
    await stage.waitForTimeout(450);
    samples.push(await tele(stage));
    if (i === 10) await control.getByTestId('cam-COMIC_CLOSE').click();
    if (i === 12) await control.getByTestId('react-laugh').click();
  }
  const last = samples[samples.length - 1];

  // 1. WebAudio clock advances monotonically
  const times = samples.map((s) => s.timeMs);
  for (let i = 1; i < times.length; i++) expect(times[i]).toBeGreaterThanOrEqual(times[i - 1]);
  expect(last.timeMs - t0.timeMs).toBeGreaterThan(6000);

  // 2. Mouth moves (plan visemes) and expressions change
  const mouths = new Set(samples.map((s) => s.mouth.toFixed(2)));
  expect(mouths.size).toBeGreaterThanOrEqual(5);
  expect(Math.max(...samples.map((s) => s.mouth))).toBeGreaterThan(0.5);
  const visemeKeys = new Set(samples.flatMap((s) => Object.entries(s.visemes).filter(([, v]) => v > 0.2).map(([k]) => k)));
  expect(visemeKeys.size).toBeGreaterThanOrEqual(2);
  const faceMax = Math.max(...samples.flatMap((s) => Object.values(s.emotions)));
  expect(faceMax).toBeGreaterThan(0.05);
  expect(last.blinks).toBeGreaterThanOrEqual(1);

  // 3. ≥2 camera cuts during the set, incl. one from the human director
  const cuts = last.cuts.filter((c) => c.source !== 'initial');
  expect(cuts.length).toBeGreaterThanOrEqual(2);
  expect(cuts.some((c) => c.source === 'human_director' && c.camera === 'COMIC_CLOSE')).toBe(true);
  expect(cuts.some((c) => c.source === 'auto_director')).toBe(true);
  expect(new Set(last.cuts.map((c) => c.camera)).size).toBeGreaterThanOrEqual(3);

  // 4. Crowd reaction reached the stage as an event (not a direct call)
  await expect.poll(() => stage.evaluate(() => window.__stage!.executor.executed.some((e) => e.type === 'crowd.reaction'))).toBe(true);

  // 5. Pause freezes the clock, resume advances it
  await control.getByTestId('pause').click();
  await stage.waitForFunction(() => window.__stage!.telemetry().status === 'PAUSED');
  const p1 = (await tele(stage)).timeMs;
  await stage.waitForTimeout(1200);
  const p2 = (await tele(stage)).timeMs;
  expect(Math.abs(p2 - p1)).toBeLessThan(50);
  await control.getByTestId('resume').click();
  await stage.waitForFunction(() => window.__stage!.telemetry().status === 'PLAYING');
  await stage.waitForTimeout(1200);
  expect((await tele(stage)).timeMs).toBeGreaterThan(p2 + 500);

  // 6. The log holds the whole show (replayable)
  const types = await stage.evaluate(() => window.__stage!.executor.executed.map((e) => e.type));
  for (const t of ['show.start', 'performance.preload', 'performance.ready', 'character.enter', 'performance.start', 'camera.cut', 'crowd.reaction', 'show.pause', 'show.resume']) {
    expect(types).toContain(t);
  }

  // Screenshots: three presets on the program feed (debug overlay off for
  // clean frames is a separate page; this one documents telemetry).
  for (const [cam, file] of [['WIDE_STAGE', 'wide'], ['COMIC_MEDIUM', 'mid'], ['COMIC_CLOSE', 'close']] as const) {
    await control.getByTestId(`cam-${cam}`).click();
    await stage.waitForFunction((c) => window.__stage!.telemetry().camera === c, cam);
    await stage.waitForTimeout(500);
    await stage.screenshot({ path: path.join(SHOTS, `stage_${file}_desktop.png`) });
  }
  await control.setViewportSize({ width: 1440, height: 900 });
  await control.screenshot({ path: path.join(SHOTS, 'control_desktop.png'), fullPage: true });

  await control.getByTestId('end').click();
  await stage.waitForFunction(() => window.__stage!.telemetry().status === 'ENDED');
  fs.writeFileSync(path.join(SHOTS, 'e2e_vrm_telemetry.json'), JSON.stringify({ first: t0, samples, last }, null, 1));

  expect(errors, errors.join('\n')).toEqual([]);
});

test('BASIC robot performs with a jaw mouth; mobile 390×844 framing', async ({ context }) => {
  const errors: string[] = [];
  const { stage, control } = await openPair(context, 'e2e-basic', 'quality=low', errors);
  await stage.setViewportSize({ width: 390, height: 844 });
  await startSet(control, stage, 'the-algorithm');
  const t0 = await tele(stage);
  expect(t0.avatar?.kind).toBe('basic');
  expect(t0.avatar?.mouthMode).toBe('jaw');
  const mouths: number[] = [];
  for (let i = 0; i < 12; i++) { await stage.waitForTimeout(400); mouths.push((await tele(stage)).mouth); }
  expect(new Set(mouths.map((m) => m.toFixed(2))).size).toBeGreaterThanOrEqual(4);
  for (const [cam, file] of [['WIDE_STAGE', 'wide'], ['COMIC_MEDIUM', 'mid'], ['COMIC_CLOSE', 'close']] as const) {
    await control.getByTestId(`cam-${cam}`).click();
    await stage.waitForFunction((c) => window.__stage!.telemetry().camera === c, cam);
    await stage.waitForTimeout(500);
    await stage.screenshot({ path: path.join(SHOTS, `stage_${file}_mobile_basic.png`) });
  }
  expect(errors, errors.join('\n')).toEqual([]);
});

test('VRM on mobile 390×844 (program feed, captions on)', async ({ context }) => {
  const errors: string[] = [];
  const { stage, control } = await openPair(context, 'e2e-mobile', 'quality=low&cpuskin=1', errors);
  await stage.setViewportSize({ width: 390, height: 844 });
  await startSet(control, stage, 'captain-ata-ashcroft');
  await stage.waitForTimeout(1500);
  for (const [cam, file] of [['WIDE_STAGE', 'wide'], ['COMIC_MEDIUM', 'mid'], ['COMIC_CLOSE', 'close']] as const) {
    await control.getByTestId(`cam-${cam}`).click();
    await stage.waitForFunction((c) => window.__stage!.telemetry().camera === c, cam);
    await stage.waitForTimeout(600);
    await stage.screenshot({ path: path.join(SHOTS, `stage_${file}_mobile.png`) });
  }
  await control.setViewportSize({ width: 390, height: 844 });
  await control.screenshot({ path: path.join(SHOTS, 'control_mobile.png'), fullPage: true });
  expect(errors, errors.join('\n')).toEqual([]);
});

test('late-joining stage replays the log and catches up', async ({ context }) => {
  const errors: string[] = [];
  const control = await context.newPage();
  watchConsole(control, 'control', errors);
  await control.goto('/control/e2e-late');
  await expect(control.getByTestId('link-status')).toContainText('connected');
  await control.getByTestId('reset').click();
  await control.getByTestId('set-select').selectOption('the-algorithm');
  await control.getByTestId('start').click();
  // No stage yet → operator presses Go anyway; the set "runs" in the log.
  await control.getByRole('button', { name: 'Go anyway' }).click();
  await control.waitForTimeout(6000);
  const stage = await context.newPage();
  watchConsole(stage, 'stage', errors);
  await stage.goto('/stage/e2e-late?quality=low');
  await stage.waitForFunction(() => window.__stage?.telemetry().status === 'PLAYING', null, { timeout: 60_000 });
  const t = await tele(stage);
  expect(t.timeMs).toBeGreaterThan(4000); // caught up instead of starting at 0
  expect(errors, errors.join('\n')).toEqual([]);
});
