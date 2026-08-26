import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'tests/e2e',
  testMatch:/acceptance-runtime\.spec\.ts/,
  timeout:60_000,
  expect:{timeout:15_000},
  workers:1,
  reporter:'list',
  use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure',screenshot:'only-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
});
