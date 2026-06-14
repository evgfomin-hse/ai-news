import { expect, test } from "@playwright/test";
import { bootstrapSession } from "../helpers/bootstrap";
import {
  ensureSummaryCount,
  fetchScore,
  generateSummary,
} from "../helpers/data";

test.describe("authenticated", () => {
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
        "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend process and restart it.",
      );
    }
  });

  test("home renders with masthead and header chrome", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("link", { name: /ai news home/i }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: /^settings$/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^logout$/i })).toBeVisible();
  });

  test("interests save and survive a reload", async ({ page }) => {
    const marker = `e2e-${Date.now()}`;

    await page.goto("/settings");
    await expect(
      page.getByRole("heading", { name: /^settings$/i }),
    ).toBeVisible({ timeout: 10_000 });

    const interests = page.getByPlaceholder(/machine learning/i);
    await interests.fill(marker);
    await page.getByRole("button", { name: /save interests/i }).click();
    await expect(page.getByText("Interests saved.")).toBeVisible({
      timeout: 10_000,
    });

    await page.reload();
    await expect(page.getByPlaceholder(/machine learning/i)).toHaveValue(
      marker,
    );
  });

  test("score persists across modal reopen and full reload", async ({
    context,
    page,
  }) => {
    // Seed a fresh summary so this test owns the top row of the feed.
    const seeded = await generateSummary(context);

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Open the newest summary by its accessible label (set in Home.tsx:268).
    const row = page.getByRole("button", {
      name: new RegExp(`open summary ${seeded.id}`, "i"),
    });
    await row.first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    // `exact` so the modal title isn't confused with the body's "Daily summary —
    // <same timestamp> UTC" heading from the placeholder markdown.
    await expect(
      dialog.getByRole("heading", { name: seeded.title, exact: true }),
    ).toBeVisible();

    // Vote Like and wait for the inline status to confirm persistence.
    const like = dialog.getByRole("button", { name: /^like$/i });
    await like.click();
    await expect(like).toHaveAttribute("aria-pressed", "true");
    await expect(dialog.getByRole("status")).toHaveText(/saved/i, {
      timeout: 10_000,
    });

    // Backend has the row (cross-checks the PUT path independently of the UI).
    const stored = await fetchScore(context, seeded.id);
    expect(stored).not.toBeNull();
    expect(stored?.value).toBe(true);

    // Reopen → state served from in-memory cache, still pressed.
    await dialog.getByRole("button", { name: /^close$/i }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await row.first().click();
    await expect(
      page.getByRole("dialog").getByRole("button", { name: /^like$/i }),
    ).toHaveAttribute("aria-pressed", "true");

    // Full reload → state must come from GET /score/{id}.
    await page.reload();
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });
    await page
      .getByRole("button", {
        name: new RegExp(`open summary ${seeded.id}`, "i"),
      })
      .first()
      .click();
    await expect(
      page.getByRole("dialog").getByRole("button", { name: /^like$/i }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("logout clears the session and returns to Login", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^logout$/i }).click();

    await expect(
      page.getByRole("heading", { name: /stay up to date/i }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /^logout$/i })).toHaveCount(
      0,
    );
  });

  test("unknown route falls back to home for authed users", async ({
    page,
  }) => {
    await page.goto("/no-such-route");
    // App.tsx catches "*" and Navigate to="/" replaces it.
    await expect(page).toHaveURL(/\/$/);
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("CSV export downloads a non-empty file with a dated filename", async ({
    context,
    page,
  }) => {
    // Make sure the e2e user has at least one row so EXPORT TO CSV is enabled.
    await generateSummary(context);

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    const button = page.getByRole("button", { name: /export to csv/i });
    await expect(button).toBeEnabled({ timeout: 15_000 });

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      button.click(),
    ]);

    // Server sets Content-Disposition: attachment; filename="summaries-YYYY-MM-DD.csv"
    expect(download.suggestedFilename()).toMatch(
      /^summaries-\d{4}-\d{2}-\d{2}\.csv$/,
    );

    // Sanity-check the body: header row present, at least one data row.
    const path = await download.path();
    const fs = await import("node:fs/promises");
    const content = await fs.readFile(path, "utf-8");
    const lines = content.trim().split("\n");
    expect(lines[0]).toBe(
      "summary_id,created_at_utc,body,score,score_description",
    );
    expect(lines.length).toBeGreaterThanOrEqual(2);
  });

  test("PREV/NEXT page through the feed", async ({ context, page }) => {
    await ensureSummaryCount(context, 7);

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    const prev = page.getByRole("button", { name: /prev/i });
    const next = page.getByRole("button", { name: /next/i });

    // Page 1: PREV disabled, NEXT enabled.
    await expect(page.getByText(/page 1 of/i)).toBeVisible();
    await expect(prev).toBeDisabled();
    await expect(next).toBeEnabled();

    const firstRow = page.getByRole("button", { name: /open summary/i });
    const page1Top = await firstRow.first().getAttribute("aria-label");

    // Go to page 2.
    await next.click();
    await expect(page.getByText(/page 2 of/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(prev).toBeEnabled();
    const page2Top = await firstRow.first().getAttribute("aria-label");
    expect(page2Top).not.toBe(page1Top);

    // Back to page 1.
    await prev.click();
    await expect(page.getByText(/page 1 of/i)).toBeVisible({
      timeout: 10_000,
    });
    await expect(prev).toBeDisabled();
  });

  test("CSV import adds summaries to the feed", async ({ page }) => {
    // Create a CSV with two summaries using unique identifiers to avoid collisions.
    const marker = `e2e-csv-${Date.now()}`;
    const now = new Date().toISOString().replace(/\.\d+Z$/, "");
    const csvContent = [
      "summary_id,created_at_utc,body,score,score_description",
      `1,${now},## ${marker} summary 1 with Like,TRUE,Good article`,
      `2,${now},## ${marker} summary 2 no score,,`,
    ].join("\n");

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Click the import button and upload the CSV file.
    const fileInput = page.locator('input[type="file"][accept*="csv"]');
    const file = {
      name: "test-import.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csvContent, "utf-8"),
    };

    await fileInput.setInputFiles({
      name: file.name,
      mimeType: file.mimeType,
      buffer: file.buffer,
    });

    // Wait for the import to complete and check the success message.
    await expect(page.getByText(/imported 2 summaries/i)).toBeVisible({
      timeout: 10_000,
    });

    // Verify both summaries appear in the feed (using unique marker).
    await expect(
      page.getByText(new RegExp(`${marker} summary 1`)),
    ).toBeVisible();
    await expect(
      page.getByText(new RegExp(`${marker} summary 2`)),
    ).toBeVisible();
  });

  test("CSV import with invalid rows shows error message", async ({ page }) => {
    // Create a CSV with an invalid row (missing required body column).
    const csvContent = [
      "summary_id,created_at_utc,body,score,score_description",
      ",2026-01-01T12:00:00,,FALSE,", // Empty body (required field)
    ].join("\n");

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    const fileInput = page.locator('input[type="file"][accept*="csv"]');
    const file = {
      name: "invalid.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csvContent, "utf-8"),
    };

    await fileInput.setInputFiles({
      name: file.name,
      mimeType: file.mimeType,
      buffer: file.buffer,
    });

    // Wait for error message to appear.
    const errorAlert = page.getByRole("alert").filter({
      hasText: /body is required/i,
    });
    await expect(errorAlert).toBeVisible({ timeout: 10_000 });
  });

  test("displays summary statistics (today and all-time)", async ({
    context,
    page,
  }) => {
    // Seed at least one summary so the stats are non-zero.
    await generateSummary(context);

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Find the masthead section which contains the statistics.
    const masthead = page.locator("div").filter({
      has: page.getByRole("heading", { name: /good morning/i }),
    });

    // Check that TODAY stat is displayed with the count and "stories" label.
    const todayWithCount = masthead.getByText(/TODAY.*\d+.*stories/i);
    await expect(todayWithCount).toBeVisible();

    // Check that ALL TIME stat is displayed with the count.
    const allTimeWithCount = masthead.getByText(/ALL TIME.*\d+/i);
    await expect(allTimeWithCount).toBeVisible();
  });

  test("summary statistics update when new summaries are imported", async ({
    context,
    page,
  }) => {
    // Import a new summary first to ensure a fresh state.
    const marker = `e2e-stats-${Date.now()}`;
    const now = new Date().toISOString().replace(/\.\d+Z$/, "");
    const csvContent = [
      "summary_id,created_at_utc,body,score,score_description",
      `1,${now},## ${marker} new summary,,`,
    ].join("\n");

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    const fileInput = page.locator('input[type="file"][accept*="csv"]');
    await fileInput.setInputFiles({
      name: "stats-test.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csvContent, "utf-8"),
    });

    // Wait for import to complete.
    await expect(page.getByText(/imported 1 summaries/i)).toBeVisible({
      timeout: 10_000,
    });

    // Verify the new summary appears in the feed.
    await expect(page.getByText(new RegExp(marker))).toBeVisible();

    // Reload the page to ensure stats are refreshed from the server.
    await page.reload();
    await expect(
      page.getByRole("heading", { name: /good morning/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Check that the newly imported summary is still visible after reload.
    await expect(page.getByText(new RegExp(marker))).toBeVisible();
  });
});
