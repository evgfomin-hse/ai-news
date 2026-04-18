import { expect, test, type Page } from '@playwright/test';

function mockSession(page: Page) {
  return page.route('**/api/users/me', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: '1',
        username: 'Playwright User',
        email: 'e2e@example.com',
        avatarUrl: null,
      }),
    });
  });
}

function mockTransportsMe(page: Page) {
  return page.route('**/api/transports/me', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        transportId: null,
        telegramConfigured: false,
      }),
    });
  });
}

test.describe('authenticated (API mocked)', () => {
  test.beforeEach(async ({ page }) => {
    await mockSession(page);
  });

  test('home shows signed-in copy and news control', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible();
    await expect(page.getByText('You are signed in.')).toBeVisible();
    await page.getByRole('button', { name: 'Receive news' }).click();
    await expect(page.getByText('Lorem ipsum dolor sit amet')).toBeVisible();
  });

  test('navigates to settings and shows transport section', async ({ page }) => {
    await mockTransportsMe(page);
    await page.goto('/');
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
    const main = page.getByRole('main');
    await expect(main.getByText('Playwright User')).toBeVisible();
    await expect(main.getByText('e2e@example.com')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Transport' })).toBeVisible();
  });
});
