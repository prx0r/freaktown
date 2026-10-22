/**
 * Stand-up mic: the comic speaks INTO the mic. The stage fits the stand to the
 * body's mouth anchor (head bone / eyes / BASIC mouth); the grille must sit in
 * front of and just below the mouth, and stay close while the comic talks.
 * Runs in capture mode (deterministic frames), VRM + BASIC robot bodies.
 */
import { test, expect, type Page } from '@playwright/test';

type Mic = { mouth: number[]; mic: number[]; distance: number; restMouth: number[]; avatar: string | null };

async function preload(page: Page, setId: string) {
  await page.goto(`/stage/mic-${setId}?capture=1&captions=0&cpuskin=1&quality=low`);
  await page.waitForFunction(() => !!window.__stage);
  const catalog = await (await page.request.get('/sets/index.json')).json();
  const set = catalog.sets.find((s: { id: string }) => s.id === setId);
  await page.evaluate(async (set) => {
    const tr = window.__stage!.runtime.consumer.transport as unknown as { reset(): void; command(t: string, p: unknown): Promise<unknown> };
    tr.reset();
    await tr.command('performance.preload', { performance_id: `mic-${set.id}`, set_url: set.set_url, audio_url: set.audio_url, avatar_url: set.avatar_url, character_name: set.character_name });
  }, set);
  await page.waitForFunction(() => window.__stage!.telemetry().status === 'READY', null, { timeout: 120_000 });
}

const report = (page: Page) => page.evaluate(() => (window.__stage!.runtime as unknown as { micReport(): Mic }).micReport());

for (const [setId, kind] of [['captain-ata-ashcroft', 'vrm'], ['the-algorithm', 'basic']] as const) {
  test(`mic sits at the mouth (${kind})`, async ({ page }) => {
    await preload(page, setId);
    const rest = await report(page);
    expect(rest.avatar).toBe(kind);
    const [mx, my, mz] = rest.mouth, [gx, gy, gz] = rest.mic;
    expect(rest.distance).toBeLessThan(0.18);            // grille within 18 cm of the lips
    expect(gz - mz).toBeGreaterThan(0.05);               // in front of the face
    expect(my - gy).toBeGreaterThan(0.0);                // a little below the mouth …
    expect(my - gy).toBeLessThan(0.12);                  // … but at mouth height, not chest height
    expect(Math.abs(gx - mx)).toBeLessThan(0.06);        // centred on the face
    // while talking (incl. a punchline lean-in) the mouth stays near the mic
    let worst = 0;
    for (let t = 2000; t <= 12000; t += 1000) {
      await page.evaluate((ms) => window.__stage!.runtime.captureAt(ms), t);
      worst = Math.max(worst, (await report(page)).distance);
    }
    expect(worst).toBeLessThan(0.22);
  });
}
