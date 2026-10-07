import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(frontend, '..');
const isolated = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-novel-branch-browser-'));
const python = process.env.SURFACE_PYTHON || 'python';
export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: '**/branch-manuscript-live.spec.ts',
  outputDir: path.join(frontend, 'test-results', 'branch-surface'), workers: 1, timeout: 120000,
  reporter: [['list'], ['junit', { outputFile: process.env.CI_RECEIPTS ? path.join(process.env.CI_RECEIPTS, 'branch-surface-browser.xml') : 'test-results/branch-surface.xml' }]],
  expect: { timeout: 15000 }, use: { baseURL: 'http://127.0.0.1:5217', viewport: { width: 1440, height: 900 }, locale: 'zh-CN', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined } }],
  webServer: [
    { command: `"${python}" tests/branch_manuscript_browser_server.py`, cwd: root, url: 'http://127.0.0.1:8057/api/health', timeout: 60000, reuseExistingServer: false,
      env: { HOME: isolated, XDG_DATA_HOME: path.join(isolated, 'xdg'), NOVEL_DATA_PATH: path.join(isolated, 'novels'), STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'true', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'false', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: 'branch_manuscript_v1,workspace_tools_v2', V1_ACCEPTANCE_MODE: 'false', FRONTEND_ORIGIN: 'http://127.0.0.1:5217',
        COLLABORATION_DEV_SESSIONS_JSON: JSON.stringify(['surface-writer-a', 'surface-writer-b'].map(actor => ({ token: actor, actor_id: actor, workspace_id: 'surface-branch-workspace', session_id: actor + '-session', client_id: actor + '-client' }))) } },
    { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5217`, cwd: frontend, url: 'http://127.0.0.1:5217', timeout: 60000, reuseExistingServer: false, env: { V061_API_URL: 'http://127.0.0.1:8057' } },
  ],
});
