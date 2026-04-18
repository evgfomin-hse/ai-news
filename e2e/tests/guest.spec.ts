import { expect, test } from '@playwright/test';

/**
 * Unauthenticated landing: visual regression only (minimal assertion surface).
 * Baseline: `npx playwright test tests/guest.spec.ts --update-snapshots`
 */
test('unauthenticated landing matches screenshot', async ({ context, page }) => {
  await context.clearCookies();
  await page.addInitScript(() => {
    localStorage.clear();
  });
  await page.goto('/');
  await expect(page.locator('.auth-term .accent')).toContainText('read:news', {
    timeout: 5000,
  });
  await expect(page).toHaveScreenshot('unauthenticated-landing.png', {
    fullPage: true,
    animations: 'disabled',
    mask: [
      page.locator('.ascii-block'),
      page.locator('footer.statusbar span').last(),
      page.locator('iframe[src*="accounts.google"]'),
    ],
    maxDiffPixels: 800,
  });
});
