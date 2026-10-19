import { defineConfig } from '@playwright/test';
import base from './playwright.visual.config';

export default defineConfig({ ...base, testMatch: /comic-handoff-live\.spec\.ts/, timeout: 120_000,
  outputDir: 'test-results/comic-handoff-live', reporter: 'list', webServer: undefined,
  use: { ...base.use, baseURL: 'http://127.0.0.1:5186', trace: 'off', launchOptions: { args: ['--disable-gpu'] } },
});
