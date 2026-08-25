import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Pata full-stack E2E tests.
 *
 * Prerequisites (CI sets these up automatically):
 *   - Backend: uvicorn api.main:app --port 8000  (PATA_DEMO_MODE=1)
 *   - Playground: npm run dev at frontend/playground  (port 5173)
 *   - Dashboard: npm run dev at frontend/review-dashboard  (port 5174)
 *
 * Run locally:
 *   cd frontend/e2e
 *   npm install
 *   npx playwright install chromium
 *   npx playwright test
 */
export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',

  // Generous timeout — PATA_DEMO_MODE=1 makes responses fast, but dev servers
  // can be slow to serve the first request.
  timeout: 60_000,
  expect: { timeout: 15_000 },

  // Stop at first failure in CI to save time; run all locally.
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,

  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],

  use: {
    // Playwright traces on failure for CI debugging
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',

    // Default: Chromium headless
    headless: true,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
