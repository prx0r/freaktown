import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test('write-a-minute: draft → tweak → suggest → preview on stage → submit', async ({ page }) => {
  await page.goto('/minute');
  await expect(page.getByTestId('minute-premise')).toHaveValue('users have infinite demands and no manners');
  await page.getByTestId('minute-draft').click();
  const lines = page.getByTestId('minute-lines');
  await expect(lines).toContainText('Hark Lantern');
  const punch = page.locator('[data-testid^="minute-line-"]').filter({ hasText: 'punch' }).first();
  await punch.locator('textarea').fill('An edited punchline, deadpan.');
  await punch.locator('select').selectOption('pause');
  await page.getByTestId('minute-suggest').click();
  await expect(punch.locator('select')).toHaveValue('deadpan');
  await expect(punch.locator('textarea')).toHaveValue('An edited punchline, deadpan.');
  await page.getByTestId('minute-preview').click();
  const frame = page.frameLocator('[data-testid="minute-stage"]');
  await expect(frame.getByTestId('sketch-stage')).toBeVisible({ timeout: 30_000 });
  await expect(frame.getByTestId('sketch-caption')).toBeVisible({ timeout: 30_000 });
  const dl = page.waitForEvent('download');
  await page.getByTestId('minute-submit').click();
  const file = await (await dl).path();
  const sub = JSON.parse(fs.readFileSync(file!, 'utf8'));
  expect(sub.schema).toBe('funnier.minute-submission/v1');
  expect(sub.performance.schema).toBe('funnier.sketch/v1');
  expect(JSON.stringify(sub.performance).toLowerCase()).toContain('an edited punchline, deadpan.');
  await expect(page.getByTestId('minute-status')).toContainText('Submitted');
});
