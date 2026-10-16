import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const receipts = process.env.STUDIO_NAVIGATION_BROWSER_RECEIPTS;
if (!receipts) throw new Error('Use the ordinary navigation-intent browser launcher.');

export default defineConfig({
  testDir: path.join(frontend, 'tests/e2e'), testMatch: 'v2-navigation-intent-live.spec.ts',
  outputDir: path.join(receipts, 'test-results'), workers: 1, fullyParallel: false,
  retries: 0, forbidOnly: true, timeout: 420_000, expect: { timeout: 30_000 },
  reporter: [['list'], ['json', { outputFile: path.join(receipts, 'results.json') }],
    ['junit', { outputFile: path.join(receipts, 'junit.xml') }]],
  use: { baseURL: process.env.STUDIO_NAVIGATION_BROWSER_BASE_URL,
    channel: 'msedge', locale: 'zh-CN', timezoneId: 'Asia/Shanghai',
    contextOptions: { reducedMotion: 'reduce' }, actionTimeout: 30_000,
    trace: 'off', screenshot: 'only-on-failure', video: 'off' },
  projects: [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]
    .map(viewport => ({ name: `navigation-intent-${viewport.width}x${viewport.height}`, use: { viewport } })),
});
