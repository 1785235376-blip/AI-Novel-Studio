import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const receipts = process.env.STUDIO_DIRECTOR_BROWSER_RECEIPTS
  || path.resolve(frontend, '../docs/delivery/v2-development/director-console-20261016');

/** Explicitly started, isolated real backend only. No fixture server or route replay. */
export default defineConfig({
  testDir: path.join(frontend, 'tests/e2e'), testMatch: 'v2-director-console-live.spec.ts',
  outputDir: path.join(receipts, 'test-results'), workers: 1, fullyParallel: false, retries: 0,
  timeout: 90_000, expect: { timeout: 15_000 }, forbidOnly: true,
  reporter: [['list'], ['json', { outputFile: path.join(receipts, 'results.json') }],
    ['junit', { outputFile: path.join(receipts, 'junit.xml') }]],
  use: { baseURL: process.env.STUDIO_DIRECTOR_BROWSER_BASE_URL || 'http://127.0.0.1:5198',
    channel: 'msedge', locale: 'zh-CN', timezoneId: 'Asia/Shanghai', reducedMotion: 'reduce', actionTimeout: 15_000,
    // Auth is entered through the shipped UI. Traces would retain its private
    // request headers, so retain screenshots and redacted network receipts only.
    trace: 'off', screenshot: 'only-on-failure' },
  projects: [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]
    .map(viewport => ({ name: `director-${viewport.width}x${viewport.height}`, use: { viewport } })),
});
