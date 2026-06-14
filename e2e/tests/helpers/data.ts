import type { BrowserContext } from "@playwright/test";

// Seeding goes through POST /api/summary/import.csv (the export-format CSV), so it
// never depends on a running LLM and needs no dedicated generate endpoint. Each
// imported line becomes one brand-new summary owned by the e2e user.
const CSV_HEADER = "summary_id,created_at_utc,body,score,score_description";
const SEED_BODY = "## E2E seeded summary";

/** ISO-8601 without timezone/millis, matching the backend's naive-UTC column. */
function nowNaiveIso(): string {
    return new Date().toISOString().replace(/\.\d+Z$/, "");
}

/**
 * Imports one fresh summary row for the e2e user via the CSV import endpoint.
 * `created_at` is "now" so the row sorts to the top of the feed. The body has no
 * commas/quotes/newlines, so no CSV escaping is needed. `summary_id` is ignored
 * by the importer; score columns are left blank (no score row created).
 */
async function importOneSummary(context: BrowserContext): Promise<void> {
    const csv = `${CSV_HEADER}\n,${nowNaiveIso()},${SEED_BODY},,\n`;
    const res = await context.request.post("/api/summary/import.csv", {
        multipart: {
            file: {
                name: "seed.csv",
                mimeType: "text/csv",
                buffer: Buffer.from(csv, "utf-8"),
            },
        },
    });
    if (!res.ok()) {
        throw new Error(
            `POST /api/summary/import.csv failed: ${res.status()} ${await res.text()}`,
        );
    }
}

async function readTotal(context: BrowserContext): Promise<number> {
    const res = await context.request.get("/api/summary?page=1&page_size=1");
    if (!res.ok()) {
        throw new Error(
            `GET /api/summary failed: ${res.status()} ${await res.text()}`,
        );
    }
    const body = (await res.json()) as { total: number };
    return body.total;
}

/**
 * Seeds one new summary row for the e2e user and returns the latest summary from a
 * follow-up GET /api/summary so the caller can assert against it. Requires a session
 * cookie (call `bootstrapSession` first).
 */
export async function generateSummary(
    context: BrowserContext,
): Promise<{ id: string; title: string; body: string }> {
    await importOneSummary(context);
    const list = await context.request.get("/api/summary?page=1&page_size=1");
    if (!list.ok()) {
        throw new Error(
            `GET /api/summary failed: ${list.status()} ${await list.text()}`,
        );
    }
    const body = (await list.json()) as {
        items: Array<{ id: string; title: string; body: string }>;
    };
    if (!body.items.length) {
        throw new Error("Summary list is empty right after seeding.");
    }
    return body.items[0];
}

/** Read the current stored score for a summary; null if none. Throws on real errors. */
export async function fetchScore(
    context: BrowserContext,
    summaryId: string | number,
): Promise<{ value: boolean | null; description: string | null } | null> {
    const res = await context.request.get(`/api/score/${summaryId}`);
    if (res.status() === 404) return null;
    if (!res.ok()) {
        throw new Error(
            `GET /api/score/${summaryId} failed: ${res.status()} ${await res.text()}`,
        );
    }
    const body = await res.json();
    if (body === null) return null;
    return { value: body.value, description: body.description };
}

/**
 * Ensures the e2e user has at least `min` summary rows, seeding only the shortfall.
 * Rows only accumulate, so this keeps a ">= N pages" precondition stable across runs.
 * Returns the resulting total.
 */
export async function ensureSummaryCount(
    context: BrowserContext,
    min: number,
): Promise<number> {
    let total = await readTotal(context);
    while (total < min) {
        await importOneSummary(context);
        total += 1;
    }
    return total;
}
