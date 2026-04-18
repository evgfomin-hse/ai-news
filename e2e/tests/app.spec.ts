import { expect, test } from '@playwright/test';

test.describe('authenticated (real API)', () => {
  test.beforeEach(async ({ context }) => {
    const secret = process.env.E2E_BOOTSTRAP_SECRET?.trim();
    test.skip(!secret, 'Set E2E_BOOTSTRAP_SECRET in backend/.env (see backend/.env.example)');

    const res = await context.request.post('/api/auth/e2e/bootstrap-session', {
      headers: { 'X-E2E-Bootstrap-Secret': secret },
    });
    if (!res.ok()) {
      throw new Error(
        `bootstrap-session failed: ${res.status()} ${await res.text()}`,
      );
    }
  });

  test('home shows signed-in copy and summary control', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible();
    await expect(page.getByText('You are signed in.')).toBeVisible();
    await page.getByRole('button', { name: 'Generate now' }).click();
    await expect(page.getByText(/Page 1 of/)).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole('heading', { name: /Daily summary/ }),
    ).toBeVisible();
  });

  test('navigates to settings and shows transport section', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    const main = page.getByRole('main');
    await expect(main.getByText('E2E User')).toBeVisible();
    await expect(main.getByText('e2e-playwright@example.invalid')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Transport' })).toBeVisible();
  });
});
