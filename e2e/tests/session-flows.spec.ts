import { expect, test } from '@playwright/test';
import { bootstrapSession } from './helpers/bootstrap';

test.describe('authenticated', () => {
  test.beforeEach(async ({ context }) => {
    const outcome = await bootstrapSession(context);
    if (outcome === 'missing-client-secret') {
      test.skip(true, 'Set E2E_BOOTSTRAP_SECRET in backend/.env (loaded by e2e/playwright.config.ts).');
    }
    if (outcome === 'disabled-on-server') {
      test.skip(
        true,
        'API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend process and restart it.',
      );
    }
  });

  test('signed-in smoke: home, summary modal, settings, logout', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible();
    await expect(
      page.getByText(/page 1 \//i).or(page.getByText('0 rows in public.summaries')),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: /generate now/i }).click();
    await expect(page.getByText(/page 1 \//i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Daily summary/)).toBeVisible();

    const row = page.locator('.bullet-list .bullet').first();
    await expect(row).toBeVisible();
    await row.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/Daily summary/)).toBeVisible();
    await dialog.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();

    await page.getByRole('link', { name: /tune settings/i }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole('heading', { name: /settings\.config/i })).toBeVisible();
    await expect(page.getByText('E2E User')).toBeVisible();
    await expect(page.getByText('bot token', { exact: true })).toBeVisible();

    const marker = `e2e-${Date.now()}`;
    await page.getByPlaceholder(/machine learning/i).fill(marker);
    await page.getByRole('button', { name: 'Save interests' }).click();
    await expect(page.getByText('Interests saved.')).toBeVisible({ timeout: 15_000 });

    await page.getByRole('link', { name: 'home' }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.goto('/no-such-route');
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible();

    await page.getByRole('button', { name: 'logout' }).click();
    await expect(page.getByText('sign_in.sh')).toBeVisible({ timeout: 10_000 });
  });
});
