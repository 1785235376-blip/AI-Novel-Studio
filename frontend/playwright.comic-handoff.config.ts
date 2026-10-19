import { defineConfig } from '@playwright/test';
import base from './playwright.visual.config';
export default defineConfig({ ...base, testMatch: /comic-handoff\.spec\.ts/, outputDir: 'test-results/comic-handoff', reporter: 'list',
  use: { ...base.use, baseURL: 'http://127.0.0.1:5185' },
  webServer: { ...base.webServer, command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5185 --strictPort`,
    url: 'http://127.0.0.1:5185/ui-fixture', reuseExistingServer: false },
});
