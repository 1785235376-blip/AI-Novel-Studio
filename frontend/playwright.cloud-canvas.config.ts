import {defineConfig} from '@playwright/test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const output = '/workspace/cloud-development-20261023/visual';
export default defineConfig({
  testDir: path.join(frontend, 'tests/e2e'),
  testMatch: /cloud-canvas-queue\.spec\.ts/,
  timeout: 60_000,
  globalTimeout: 180_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  outputDir: path.join(output, 'test-results'),
  reporter: [['list'], ['json', {outputFile: path.join(output, 'results.json')}]],
  use: {
    baseURL: 'http://127.0.0.1:5207',
    browserName: 'chromium',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    deviceScaleFactor: 1,
    colorScheme: 'light',
    reducedMotion: 'reduce',
    trace: 'off',
    screenshot: 'only-on-failure',
    launchOptions: {executablePath: '/usr/bin/chromium', chromiumSandbox: true},
  },
  webServer: {
    command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5207 --strictPort`,
    cwd: frontend,
    url: 'http://127.0.0.1:5207/tests/fixtures/cloud-canvas-queue.html',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
