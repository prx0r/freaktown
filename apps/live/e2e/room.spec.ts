/**
 * Same show over the EpisodeRoom Durable Object (`wrangler dev`).
 * Skipped unless ROOM_URL is set, e.g.:
 *   (cd edge && cp .dev.vars.example .dev.vars && npx wrangler dev --assets ../apps/live/dist --local)
 *   ROOM_URL=http://127.0.0.1:8787 npx playwright test e2e/room.spec.ts
 */
import { test, expect } from '@playwright/test';

const ROOM = process.env.ROOM_URL;
test.skip(!ROOM, 'ROOM_URL not set (needs wrangler dev)');

test('EpisodeRoom transport: control → DO → stage (token-gated)', async ({ context, request }) => {
  const ep = `room-e2e-${Date.now()}`;
  const errors: string[] = [];
  const res = await request.post(`${ROOM}/live/${ep}/stage-token`, { data: { role: 'stage' } });
  expect(res.ok()).toBe(true);
  const { token } = await res.json();

  // A forged token is rejected by the DO (HMAC), and the stage says so.
  const bad = await context.newPage();
  await bad.goto(`${ROOM}/stage/${ep}?transport=room&token=forged.sig&quality=low`);
  await expect(bad.getByText(/stage link rejected/)).toBeVisible({ timeout: 15_000 });
  await bad.close();

  const stage = await context.newPage();
  stage.on('console', (m) => { if (m.type() === 'error') errors.push(`stage: ${m.text()}`); });
  stage.on('pageerror', (e) => errors.push(`stage: ${e.message}`));
  await stage.goto(`${ROOM}/stage/${ep}?transport=room&token=${encodeURIComponent(token)}&quality=low&debug=1`);
  await stage.waitForFunction(() => window.__stage?.runtime.consumer.connected === true, null, { timeout: 20_000 });

  const control = await context.newPage();
  control.on('pageerror', (e) => errors.push(`control: ${e.message}`));
  await control.goto(`${ROOM}/control/${ep}?transport=room`);
  await expect(control.getByTestId('link-status')).toContainText('connected');
  await control.getByTestId('set-select').selectOption('the-algorithm');
  await control.getByTestId('start').click();
  await stage.bringToFront();
  await stage.waitForFunction(() => window.__stage!.telemetry().status === 'PLAYING', null, { timeout: 60_000 });
  await stage.waitForTimeout(3500);
  await control.getByTestId('cam-COMIC_CLOSE').click();
  await stage.waitForFunction(() => window.__stage!.telemetry().cuts.some((c) => c.source === 'human_director'));
  const t = await stage.evaluate(() => window.__stage!.telemetry());
  expect(t.timeMs).toBeGreaterThan(2500);
  expect(t.cuts.filter((c) => c.source !== 'initial').length).toBeGreaterThanOrEqual(2);
  // The DO persisted the stage ACK as an event (replay invariant).
  const types = await stage.evaluate(() => window.__stage!.executor.executed.map((e) => e.type));
  expect(types).toEqual(expect.arrayContaining(['show.start', 'performance.preload', 'performance.ready', 'performance.start', 'camera.cut']));
  await stage.screenshot({ path: '/workspace/work/funnier-live/shots/stage_room_mode.png' });
  expect(errors, errors.join('\n')).toEqual([]);
});
