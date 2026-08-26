import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'tests/e2e',
  testMatch:/v061-(?:remaining|pass2)-acceptance\.spec\.ts/,
  timeout:15_000,
  expect:{timeout:4_000},
  workers:1,
  reporter:'line',
  use:{baseURL:process.env.V061_PREVIEW_URL||'http://127.0.0.1:4173',trace:'retain-on-failure',screenshot:'only-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
});
