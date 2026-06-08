import type { BrowserContext } from "@playwright/test";

/**
 * Resets the e2e user's transport to an empty baseline by clearing the bot
 * token. The backend drops both token and chat id when the token is emptied
 * (see backend/app/api/transports.py), so this yields a known clean state.
 * Requires a session cookie (call `bootstrapSession` first).
 */
export async function clearTransport(context: BrowserContext): Promise<void> {
    const res = await context.request.patch("/api/transports", {
        headers: { "Content-Type": "application/json" },
        data: { telegramBotToken: "" },
    });
    if (!res.ok()) {
        throw new Error(
            `PATCH /api/transports (clear) failed: ${res.status()} ${await res.text()}`,
        );
    }
}
