import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '../tests/playwright',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  // The P0 full-product stage owns this spec and injects its isolated local
  // stack. Generic caregiver browser runs must not launch it without that stack.
  testIgnore: process.env.P0_E2E_BASE_URL ? [] : ['**/p0_full_product.spec.ts'],
  reporter: [
    ['list'],
    ['html', { outputFolder: '../evidence/playwright-report', open: 'never' }],
    ['json', { outputFile: '../evidence/playwright-results.json' }]
  ],
  use: {
    baseURL: process.env.PWA_BASE_URL || 'http://127.0.0.1:8766',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 7'] } }
  ],
});
