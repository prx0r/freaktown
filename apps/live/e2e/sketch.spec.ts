/**
 * /sketch — a sketch script compiled in-page (@funnier/sketch) and played on a
 * SetStage. Capture mode: the frame at t is a pure function of (script, t), so
 * the stage camera must match the compiled shot list, scripted looks must be
 * live at their times, and the blackout must land at the end.
 */
import { test, expect } from '@playwright/test';

type Tele = { camera: string; looks?: Record<string, { yaw: number; pitch: number; scripted: string | null }>; blackout?: number; seats: Array<{ seat: string }>; setId: string | null };
type Shot = { start_ms: number; end_ms: number; cue: string };
type Look = { role: string; start_ms: number; end_ms: number; target: unknown; source: string };

test('sketch route: demo compiles, cameras follow the director, looks + blackout land', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/sketch/wall-of-news?capture=1&cpuskin=1&quality=low');
  await page.waitForFunction(() => window.__sketch?.ready === true, null, { timeout: 120_000 });
  const tl = await page.evaluate(() => {
    const t = window.__sketch!.timeline()!;
    return { duration: t.duration_ms, shots: t.shots as Shot[], looks: t.gaze.looks as Look[], set: t.set, cast: t.cast };
  });
  expect(tl.set).toBe('news-studio');
  expect(tl.shots.length).toBeGreaterThan(10);
  const tele = await page.evaluate(() => window.__sketch!.telemetry() as unknown as Tele);
  expect(tele.setId).toBe('news-studio');
  expect(tele.seats.map((s) => s.seat).sort()).toEqual(['anchor1', 'anchor2', 'floor-mark']);

  // cameras: sample the middle of a few shots
  for (const s of tl.shots.filter((_, i) => i % 4 === 1)) {
    const mid = Math.round((s.start_ms + s.end_ms) / 2);
    await page.evaluate((ms) => window.__sketch!.renderAt(ms), mid);
    const t = await page.evaluate(() => window.__sketch!.telemetry() as unknown as Tele);
    expect(t.camera, `@${mid}`).toBe(s.cue);
  }
  // a double-take snap-back is live on the stage at its time
  const dt = tl.looks.filter((l) => l.source === 'double-take')[2];
  await page.evaluate((ms) => window.__sketch!.renderAt(ms), dt.start_ms + 200);
  const t2 = await page.evaluate(() => window.__sketch!.telemetry() as unknown as Tele);
  expect(Object.values(t2.looks ?? {}).some((l) => l.scripted !== null)).toBe(true);
  // the walk to the mark re-keys the character
  const late = await page.evaluate(async (ms) => { await window.__sketch!.renderAt(ms); return window.__sketch!.telemetry() as unknown as Tele; }, Math.round(tl.duration * 0.75));
  expect(late.seats.map((s) => s.seat)).toContain('wall-mark');
  // blackout at the end
  await page.evaluate((ms) => window.__sketch!.renderAt(ms), tl.duration - 50);
  const end = await page.evaluate(() => window.__sketch!.telemetry() as unknown as Tele);
  expect(end.blackout).toBeGreaterThan(0.9);
  expect(errors).toEqual([]);
});

test('sketch control panel loads a demo script', async ({ page }) => {
  await page.goto('/sketch?quality=low&cpuskin=1');
  await expect(page.getByTestId('sketch-panel')).toBeVisible();
  await page.getByTestId('sketch-demo').selectOption('the-tell');
  await expect(page.getByTestId('sketch-status')).toContainText('The Tell', { timeout: 60_000 });
  await expect(page.getByTestId('sketch-script')).toHaveValue(/funnier\.sketch\/v1/);
  // a broken script is rejected with the validator's message
  await page.getByTestId('sketch-script').fill('{"schema":"funnier.sketch/v1","id":"x"}');
  await page.getByTestId('sketch-compile').click();
  await expect(page.getByTestId('sketch-status')).toContainText('script error');
});
