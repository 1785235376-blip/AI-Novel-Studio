// [HERMIA-FE-20261022] Browser config for workbench wiring. Expects an ALREADY RUNNING isolated
// backend + vite (see docs/delivery/HERMIA_FRONTEND_REFACTOR_20261022.md §5); does not run the
// Windows/Postgres fixture of playwright.config.ts and does not start/own any server.
import {defineConfig, devices} from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: /hermia-workbench\.spec\.ts/, timeout: 90_000, workers: 1,
  reporter: [['list']],
  use: {baseURL: process.env.HERMIA_BASE_URL || 'http://127.0.0.1:5199', screenshot: 'only-on-failure'},
  projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}],
});
