import { expect, test } from '@playwright/test';

test.describe('unauthenticated', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/users/me', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });
  });

  test('shows sign-in screen', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });
});
