import type { BrowserContext } from "@playwright/test";

/**
 * Hits POST /api/summary/generate to insert one new summary row for the e2e user.
 *
 * Returns the latest summary id from a follow-up GET /api/summary so the caller can
 * assert against it. Requires a session cookie (call `bootstrapSession` first).
 */
export async function generateSummary(
    context: BrowserContext,
): Promise<{ id: string; title: string; body: string }> {
    const gen = await context.request.post("/api/summary/generate");
    if (!gen.ok()) {
        throw new Error(
            `POST /api/summary/generate failed: ${gen.status()} ${await gen.text()}`,
        );
    }
    const list = await context.request.get(
        "/api/summary?page=1&page_size=1",
    );
    if (!list.ok()) {
        throw new Error(
            `GET /api/summary failed: ${list.status()} ${await list.text()}`,
        );
    }
    const body = (await list.json()) as {
        items: Array<{ id: string; title: string; body: string }>;
    };
    if (!body.items.length) {
        throw new Error("Summary list is empty right after generate.");
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
