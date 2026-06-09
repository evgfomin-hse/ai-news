import { expect, test } from "@playwright/test";
import { bootstrapSession } from "../helpers/bootstrap";
import { clearTransport } from "../helpers/transport";

// All users share one transport row, so these mutate shared state and must not
// run in parallel with each other.
test.describe.configure({ mode: "serial" });

test.describe("settings · telegram transport", () => {
    test.beforeEach(async ({ context, page }) => {
        const outcome = await bootstrapSession(context);
        if (outcome === "missing-client-secret") {
            test.skip(
                true,
                "Set E2E_BOOTSTRAP_SECRET in backend/.env (loaded by e2e/playwright.config.ts).",
            );
        }
        if (outcome === "disabled-on-server") {
            test.skip(
                true,
                "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend and restart it.",
            );
        }
        await clearTransport(context);
        await page.goto("/settings");
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
    });

    test("with no transport, test and send are disabled", async ({ page }) => {
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeDisabled();
        await expect(
            page.getByRole("button", { name: /send test message/i }),
        ).toBeDisabled();
    });

    test("saving a bot token enables test and clear", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();

        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeEnabled();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeEnabled();
    });

    test("non-numeric chat id is rejected", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });

        await page.getByPlaceholder("e.g. 123456789").fill("not-a-number");
        await page.getByRole("button", { name: /save chat id/i }).click();

        await expect(page.getByText(/must be a numeric/i)).toBeVisible({
            timeout: 10_000,
        });
    });

    test("valid chat id saves and survives reload", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });

        await page.getByPlaceholder("e.g. 123456789").fill("123456789");
        await page.getByRole("button", { name: /save chat id/i }).click();
        await expect(page.getByText("Chat id saved.")).toBeVisible({
            timeout: 10_000,
        });
        // chatDisplay groups digits in threes: "123 456 789".
        await expect(page.getByText(/123 456 789/)).toBeVisible();

        await page.reload();
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
        await expect(page.getByText(/123 456 789/)).toBeVisible();
    });

    test("clearing the token resets configuration and survives reload", async ({
        page,
    }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeEnabled({ timeout: 10_000 });

        await page.getByRole("button", { name: /clear token/i }).click();
        await expect(
            page.getByText("Token removed (chat id cleared too)."),
        ).toBeVisible({ timeout: 10_000 });
        await expect(page.getByText(/chat not set/i)).toBeVisible();
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();

        await page.reload();
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();
    });
});
