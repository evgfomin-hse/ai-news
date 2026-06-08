import { expect, test } from "@playwright/test";
import { bootstrapSession } from "./helpers/bootstrap";
import { fetchScore, generateSummary } from "./helpers/data";

test.describe("authenticated · feedback", () => {
    test.beforeEach(async ({ context }) => {
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
    });

    test("dislike with a comment persists and survives reload", async ({
        context,
        page,
    }) => {
        const seeded = await generateSummary(context);
        const comment = `e2e dislike ${Date.now()}`;

        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        const row = page.getByRole("button", {
            name: new RegExp(`open summary ${seeded.id}`),
        });
        await row.first().click();

        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();

        // Comment is locked before any vote — the placeholder says so.
        await expect(
            dialog.getByLabel(/what did you like or dislike/i),
        ).toHaveAttribute("placeholder", /like or dislike first/i);

        // Vote Dislike.
        const dislike = dialog.getByRole("button", { name: /^dislike$/i });
        await dislike.click();
        await expect(dislike).toHaveAttribute("aria-pressed", "true");

        // Type a comment; debounced save lands after the vote is cast.
        await dialog.getByLabel(/what did you like or dislike/i).fill(comment);
        await expect(dialog.getByRole("status")).toHaveText(/saved/i, {
            timeout: 10_000,
        });

        // Backend cross-check (independent of the UI).
        const stored = await fetchScore(context, seeded.id);
        expect(stored).not.toBeNull();
        expect(stored?.value).toBe(false);
        expect(stored?.description).toBe(comment);

        // Full reload → state must come from GET /score/{id}.
        await page.reload();
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });
        await page
            .getByRole("button", {
                name: new RegExp(`open summary ${seeded.id}`),
            })
            .first()
            .click();
        const reopened = page.getByRole("dialog");
        await expect(
            reopened.getByRole("button", { name: /^dislike$/i }),
        ).toHaveAttribute("aria-pressed", "true");
        await expect(
            reopened.getByLabel(/what did you like or dislike/i),
        ).toHaveValue(comment);
    });
});
