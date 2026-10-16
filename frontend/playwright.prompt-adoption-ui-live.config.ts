import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const receipts = process.env.STUDIO_PROMPT_ADOPTION_UI_BROWSER_RECEIPTS;
if (!receipts) throw new Error('Use the isolated packaged adoption UI launcher.');

export default defineConfig({
  testDir: path.join(frontend, 'tests/e2e'), testMatch: 'v2-prompt-adoption-ui-live.spec.ts',
  outputDir: path.join(receipts, 'test-results'), workers: 1, fullyParallel: false,
  retries: 0, forbidOnly: true, timeout: 180_000, expect: { timeout: 25_000 },
  reporter: [['list'], ['json', { outputFile: path.join(receipts, 'results.json') }],
    ['junit', { outputFile: path.join(receipts, 'junit.xml') }]],
  use: { baseURL: process.env.STUDIO_PROMPT_ADOPTION_UI_BROWSER_BASE_URL,
    channel: 'msedge', locale: 'zh-CN', timezoneId: 'Asia/Shanghai',
    reducedMotion: 'reduce', actionTimeout: 25_000,
    // Never retain bootstrap/session headers in traces.
    trace: 'off', screenshot: 'only-on-failure', video: 'off' },
  projects: [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]
    .map(viewport => ({ name: `prompt-adoption-ui-${viewport.width}x${viewport.height}`, use: { viewport } })),
});
