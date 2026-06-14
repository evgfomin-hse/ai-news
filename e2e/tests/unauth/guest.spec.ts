import { expect, test } from "@playwright/test";

/**
 * Unauthenticated landing: assert the Login page renders and no signed-in chrome leaks in.
 * No screenshot baseline — selector-based assertions only so the test survives style tweaks.
 */
test.describe("guest", () => {
    test.beforeEach(async ({ context, page }) => {
        await context.clearCookies();
        await page.addInitScript(() => {
            localStorage.clear();
        });
    });

    test("landing shows the Login page", async ({ page }) => {
        await page.goto("/");

        // Title + lede copy from Login.tsx.
        await expect(
            page.getByRole("heading", { name: /stay up to date/i }),
        ).toBeVisible({ timeout: 5000 });
        await expect(page.getByText(/daily · ai news/i)).toBeVisible();

        // Header is shown but in its signed-out shape: no SETTINGS / LOGOUT controls.
        await expect(
            page.getByRole("link", { name: /^settings$/i }),
        ).toHaveCount(0);
        await expect(
            page.getByRole("button", { name: /^logout$/i }),
        ).toHaveCount(0);
    });

    test("deep-link to a protected route still renders Login (router guard)", async ({
        page,
    }) => {
        await page.goto("/settings");

        // App.tsx renders <Login /> whenever there's no user, regardless of URL.
        await expect(
            page.getByRole("heading", { name: /stay up to date/i }),
        ).toBeVisible({ timeout: 5000 });
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toHaveCount(0);
    });
});
