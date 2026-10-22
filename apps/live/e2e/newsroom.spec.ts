import { expect, test, type Page } from '@playwright/test';

/**
 * Newsroom SDK: the compiled show drives the news-studio set; each story's
 * wall headline must actually appear (DOM mirror + telemetry + bright wall
 * pixels in the frame) on its wide / 3/4 shot before the single.
 * Capture mode: frames are a pure function of (rundown, t).
 */
const URL = '/newsroom/demo?rundown=/newsroom/demo-goodnight.json&capture=1&quality=low&cpuskin=1';

async function stepTo(page: Page, ms: number) {
  for (let t = 0; t < ms; t += 1000) await page.evaluate((x) => window.__newsroom!.renderAt(x), t);
  await page.evaluate((x) => window.__newsroom!.renderAt(x), ms);
}

/** Mean luma of a frame region (0..255), read from the stage canvas (preserveDrawingBuffer). */
async function luma(page: Page, rx0: number, ry0: number, rx1: number, ry1: number): Promise<number> {
  return page.evaluate(([a, b, c, d]) => {
    const src = document.querySelector('[data-testid="newsroom-stage"] canvas') as HTMLCanvasElement;
    const cv = document.createElement('canvas'); cv.width = 160; cv.height = 90;
    const ctx = cv.getContext('2d')!; ctx.drawImage(src, 0, 0, 160, 90);
    const px = ctx.getImageData(Math.round(a * 160), Math.round(b * 90), Math.round((c - a) * 160), Math.round((d - b) * 90)).data;
    let s = 0; for (let i = 0; i < px.length; i += 4) s += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
    return s / (px.length / 4);
  }, [rx0, ry0, rx1, ry1]);
}

for (const vp of [{ name: 'desktop', width: 1280, height: 720 }, { name: 'mobile', width: 390, height: 844 }]) {
  test(`wall headline appears before the single (${vp.name})`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(URL);
    await page.waitForFunction(() => window.__newsroom?.ready === true, null, { timeout: 90_000 });
    const tl = await page.evaluate(() => {
      const t = window.__newsroom!.timeline()!;
      return { stories: t.stories, shots: t.shots, estimated: t.estimated };
    });
    expect(tl.estimated).toBe(true);
    const s1 = tl.stories.find((s) => s.id === 's1')!;
    expect(s1.headline).toBe('Story one headline for the wall');
    const t = s1.headline_ms! + 1500;
    await stepTo(page, t);
    await expect(page.getByTestId('wall-headline')).toHaveText('Story one headline for the wall');
    await expect(page.getByTestId('wall-headline')).toHaveAttribute('data-layout', 'headline');
    const tel = await page.evaluate(() => window.__newsroom!.telemetry()!);
    expect(['wide', 'wall-ots']).toContain(tel.camera);
    expect(tel.wall?.text).toBe('Story one headline for the wall');
    // the paper-light wall card fills a good part of the frame (dark studio otherwise)
    const wallLuma = await luma(page, 0.3, 0.2, 0.9, 0.6);
    expect(wallLuma).toBeGreaterThan(110);
    // the single comes after the headline
    const firstSingle = tl.shots.find((s) => s.cls === 'one' && s.start_ms >= s1.start_ms);
    if (firstSingle) expect(firstSingle.start_ms).toBeGreaterThan(s1.headline_ms!);
    // themed overlays sit inside the viewport (no clipping)
    for (const id of ['bug', 'ticker']) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box, id).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.y + box!.height).toBeLessThanOrEqual(vp.height + 1);
    }
    await page.screenshot({ path: `test-results/newsroom-wall-${vp.name}.png` });
    expect(errors).toEqual([]);
  });
}

test('numbers line puts the figure on the wall; remote reporter gets the country card + lower third', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(URL);
  await page.waitForFunction(() => window.__newsroom?.ready === true, null, { timeout: 90_000 });
  const ev = await page.evaluate(() => window.__newsroom!.timeline()!.events.filter((e) => e.type === 'overlay.headline'));
  const num = ev.find((e) => e.payload.layout === 'numbers')!;
  await stepTo(page, num.t_ms + 1000);
  await expect(page.getByTestId('wall-headline')).toHaveAttribute('data-layout', 'numbers');
  const country = ev.find((e) => e.payload.layout === 'country')!;
  await stepTo(page, country.t_ms + 1000);
  await expect(page.getByTestId('wall-headline')).toHaveText('Kenya');
  await expect(page.getByTestId('lower-third')).toContainText('Test Reporter');
});
