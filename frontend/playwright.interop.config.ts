import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(frontend, '..');
const python = process.env.INTEROP_PYTHON || 'python';
const isolated = fs.mkdtempSync(path.join(os.tmpdir(), 'local-interop-browser-mock-'));
const env = { LOCAL_INTEROP_BROWSER_FIXTURE: 'MOCK_ONLY', HOME: isolated, XDG_DATA_HOME: path.join(isolated, 'xdg'), NOVEL_DATA_PATH: path.join(isolated, 'novels'), PROJECT_ROOT: isolated, STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'true', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'true', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: 'local_tutor_interop_v1', V1_ACCEPTANCE_MODE: 'false', FRONTEND_ORIGIN: 'http://127.0.0.1:5251', PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: '1' };
export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: /local-interop\.spec\.ts/,
  outputDir: path.join(frontend, 'test-results', 'local-interop'), workers: 1, fullyParallel: false, timeout: 90_000,
  expect: { timeout: 15_000 }, reporter: [['list'], ['junit', { outputFile: path.join(frontend, 'test-results', 'local-interop.xml') }]],
  use: { baseURL: 'http://127.0.0.1:5251', viewport: { width: 1440, height: 900 }, locale: 'zh-CN', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined } }],
  webServer: [
    { command: `"${python}" frontend/scripts/local_interop_browser_host.py`, cwd: root, url: 'http://127.0.0.1:8051/api/health', env, reuseExistingServer: false, timeout: 60_000 },
    { command: `"${python}" scripts/run_synthetic_tutor.py --port 8052`, cwd: root, url: 'http://127.0.0.1:8052/interop/v1/discovery', env, reuseExistingServer: false, timeout: 30_000 },
    { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5251`, cwd: frontend, url: 'http://127.0.0.1:5251', env: { V061_API_URL: 'http://127.0.0.1:8051' }, reuseExistingServer: false, timeout: 30_000 },
  ],
});
