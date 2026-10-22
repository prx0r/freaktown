import { test, expect } from '@playwright/test';

/**
 * TNTS vs agents, with a fake webcam: a recorded synthetic blendshape stream
 * (public/tnts/feeds/grin-after-6s.json: neutral for 6 s, then a held grin)
 * replaces MediaPipe output. It flows through the same path as a camera:
 * blendshapes → smileFusion → neutral calibration → rules (threshold + hold)
 * → the human is eliminated while the agents (simulated smiles) play on.
 * Chromium also runs with a fake media device so getUserMedia works.
 */
test.use({ launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] } });

test('a recorded grin eliminates the human; agents keep playing', async ({ page }) => {
  await page.goto('/tnts?feed=recorded&src=/tnts/feeds/grin-after-6s.json&quality=low&turn=12000&seed=e2e');
  await expect(page.getByTestId('tnts-room')).toBeVisible();
  await expect(page.getByTestId('seat-human')).toBeVisible();
  await expect(page.getByTestId('seat-seat1')).toContainText('Doug Deadline');
  // calibration (3 s of neutral) → auto start
  await page.waitForFunction(() => window.__tnts?.state()?.phase === 'turn', null, { timeout: 30_000 });
  const cal = await page.evaluate(() => window.__tnts!.state()!.players.you);
  expect(cal.calibrated).toBe(true);
  expect(cal.baseline).toBeLessThan(0.1);
  // the grin starts at 6 s; with 3 lives + 1.5 s grace the human is out within a few turns
  await page.waitForFunction(() => window.__tnts?.state()?.players.you.out === true, null, { timeout: 90_000 });
  const log = await page.evaluate(() => window.__tnts!.log());
  const breaks = log.filter((e) => e.type === 'smile.break' && e.id === 'you');
  expect(breaks.length).toBe(3);
  for (const b of breaks) expect(b).toMatchObject({ simulated: false });
  expect(log.some((e) => e.type === 'player.out' && e.id === 'you')).toBe(true);
  await expect(page.getByTestId('seat-human')).toContainText('OUT');
  // agents remain in the game (or it finished cleanly with an agent winner)
  const st = await page.evaluate(() => window.__tnts!.state()!);
  expect(Object.values(st.players).filter((p) => p.kind === 'agent' && !p.out).length).toBeGreaterThan(0);
});

test('neutral face survives; low light pauses judging with a warning', async ({ page }) => {
  await page.goto('/tnts?feed=recorded&src=/tnts/feeds/neutral-dark-window.json&quality=low&seed=e2e2');
  await page.waitForFunction(() => window.__tnts?.state()?.phase === 'turn', null, { timeout: 30_000 });
  await page.waitForFunction(() => window.__tnts!.log().some((e) => e.type === 'lighting.warning'), null, { timeout: 30_000 });
  await page.waitForFunction(() => window.__tnts!.log().some((e) => e.type === 'lighting.ok'), null, { timeout: 30_000 });
  const you = await page.evaluate(() => window.__tnts!.state()!.players.you);
  expect(you.strikes).toBe(0);
});

test('camera mode asks for the webcam and keeps video local', async ({ page }) => {
  await page.goto('/tnts?quality=low');
  await expect(page.getByTestId('tnts-setup')).toBeVisible();
  await page.getByTestId('tnts-camera').click();
  // fake device → a <video> lands in the human tile; nothing is uploaded
  await expect(page.locator('[data-testid="seat-human"] video')).toHaveCount(1, { timeout: 20_000 });
  await expect(page.getByTestId('seat-human')).toContainText('video stays on this device');
});
