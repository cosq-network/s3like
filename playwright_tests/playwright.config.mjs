import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  timeout: 30_000,
  expect: {
    timeout: 5000,
  },
  use: {
    browser: 'chromium',
    headless: process.env.CI === 'true',
    baseURL: 'http://localhost:5000',
  },
  testMatch: ['**/*.spec.ts', '**/*.spec', '**/*.test.ts'],
});
