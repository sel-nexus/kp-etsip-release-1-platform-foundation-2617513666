import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const frontendURL = new URL(baseURL);

export default defineConfig({
  testDir: './e2e',
  use: { baseURL, ...devices['Desktop Chrome'] },
  webServer: {
    command: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${Number(frontendURL.port || 5173)} --strictPort`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
  // Serialize journeys that temporarily modify shared preferences or role permissions.
  workers: 1,
  retries: 0,
});
