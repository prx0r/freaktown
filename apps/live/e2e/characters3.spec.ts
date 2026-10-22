import { test, expect } from '@playwright/test';

test('/characters3: roster → Hark Lantern theory → sets → preview on stage', async ({ page }) => {
  await page.goto('/characters3');
  await expect(page.getByTestId('characters-roster')).toBeVisible();
  await page.getByTestId('character-card-hark-lantern').click();
  await expect(page.getByTestId('theory-view')).toContainText('Comic want');
  await expect(page.getByTestId('theory-view')).toContainText('Ledger of Please');
  await page.getByTestId('tab-sets').click();
  await expect(page.getByTestId('set-view')).toContainText('PUNCH', { ignoreCase: true });
  await page.getByTestId('set-preview').click();
  const frame = page.frameLocator('[data-testid="set-stage"]');
  await expect(frame.getByTestId('sketch-stage')).toBeVisible({ timeout: 30_000 });
});
