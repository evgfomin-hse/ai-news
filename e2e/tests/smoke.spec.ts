import { expect, test } from '@playwright/test';

test.describe('unauthenticated', () => {
  test.beforeEach(async ({ context }) => {
    await context.clearCookies();
  });

  test('shows sign-in screen when session cookie is absent', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });
});
