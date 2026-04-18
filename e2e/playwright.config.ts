import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { config as loadEnv } from 'dotenv';
import { defineConfig, devices } from '@playwright/test';

const e2eDir = fileURLToPath(new URL('.', import.meta.url));
const frontendDir = path.join(e2eDir, '../frontend');
const backendDir = path.join(e2eDir, '../backend');

// So E2E_BOOTSTRAP_SECRET and DATABASE_URL match the API process (backend loads the same file from cwd).
loadEnv({ path: path.join(backendDir, '.env') });

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: backendDir,
      url: 'http://127.0.0.1:8000/openapi.json',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --strictPort --port 5173',
      cwd: frontendDir,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
