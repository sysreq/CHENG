import { defineConfig } from '@playwright/test';

/**
 * Playwright E2E test configuration for CHENG.
 *
 * Assumes the full app (backend + frontend) is running on port 8000.
 * Start with: powershell -ExecutionPolicy Bypass -File .\startup.ps1
 *
 * Run tests: npx playwright test
 * Run headed: npx playwright test --headed
 */
export default defineConfig({
  testDir: '../tests/frontend/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    headless: true,
    viewport: { width: 1280, height: 800 },
    actionTimeout: 10_000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
