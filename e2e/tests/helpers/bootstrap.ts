import type { BrowserContext } from '@playwright/test';

export function getBootstrapSecret(): string | undefined {
  return process.env.E2E_BOOTSTRAP_SECRET?.trim();
}

/** Result when the client has a secret but the running API was built without bootstrap (404). */
export type BootstrapResult = 'ok' | 'missing-client-secret' | 'disabled-on-server';

export async function bootstrapSession(context: BrowserContext): Promise<BootstrapResult> {
  const secret = getBootstrapSecret();
  if (!secret) {
    return 'missing-client-secret';
  }
  const res = await context.request.post('/api/auth/e2e/bootstrap-session', {
    headers: { 'X-E2E-Bootstrap-Secret': secret },
  });
  if (res.status() === 404) {
    return 'disabled-on-server';
  }
  if (!res.ok()) {
    throw new Error(`bootstrap-session failed: ${res.status()} ${await res.text()}`);
  }
  return 'ok';
}
