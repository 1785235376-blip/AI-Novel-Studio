import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(frontend, '..');
const runId = process.env.V2_LIVE_RUN_ID || `${Date.now()}-${process.pid}`;
const runtime = path.join(root, '.runtime', 'v2-live-browser', runId);
const receipts = process.env.CI_RECEIPTS || path.join(root, 'docs', 'delivery', 'v2-development', 'cloud-v2-creative-browser');
const python = process.env.V2_PYTHON || path.join(root, '.venv', 'bin', 'python');
fs.mkdirSync(receipts, { recursive: true });

function servers(name: string, apiPort: number, port: number, enabled: boolean, acceptance = false) {
  const owned = path.join(runtime, name);
  for (const directory of ['home', 'data', 'cache', 'config', 'local', 'tmp']) fs.mkdirSync(path.join(owned, directory), { recursive: true });
  const env = {
    HOME: path.join(owned, 'home'), XDG_DATA_HOME: path.join(owned, 'data'),
    XDG_CACHE_HOME: path.join(owned, 'cache'), XDG_CONFIG_HOME: path.join(owned, 'config'),
    LOCALAPPDATA: path.join(owned, 'local'), TMPDIR: path.join(owned, 'tmp'),
    TEMP: path.join(owned, 'tmp'), TMP: path.join(owned, 'tmp'),
    PROJECT_ROOT: root, NOVEL_DATA_PATH: path.join(owned, 'novel-data'),
    STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'false', ENABLE_PACKAGED_RUNTIME: 'false',
    MOCK_PROVIDER: 'true', MOCK_STREAM_DELAY_MS: '0', ENABLE_CLOUD: 'false', ENABLE_PROVIDER_FALLBACK: 'false',
    CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true',
    EXPERIMENTAL_FEATURES: enabled ? 'narrative_production_v2' : '', V1_ACCEPTANCE_MODE: String(acceptance),
    FRONTEND_ORIGIN: `http://127.0.0.1:${port}`,
  };
  return [
    { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${apiPort} 2>&1 | tee "${path.join(receipts, `${name}-backend.log`)}"`, cwd: root,
      url: `http://127.0.0.1:${apiPort}/api/health`, timeout: 90000, reuseExistingServer: false, env },
    { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port} 2>&1 | tee "${path.join(receipts, `${name}-vite.log`)}"`, cwd: frontend,
      url: `http://127.0.0.1:${port}`, timeout: 60000, reuseExistingServer: false, env: { ...env, V061_API_URL: `http://127.0.0.1:${apiPort}` } },
  ];
}

export default defineConfig({
  metadata: { v2LiveRuntime: runtime, verification: 'Synthetic fixture; real File and HTTP; browser success requires Chromium to launch.' },
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: /v2-(creative|independent-studio|asset-relationships)-live\.spec\.ts/,
  outputDir: path.join(receipts, 'test-results'), workers: 1, fullyParallel: false, timeout: 180000,
  expect: { timeout: 15000 }, retries: 0,
  reporter: [['list'], ['junit', { outputFile: path.join(receipts, 'junit.xml') }], ['json', { outputFile: path.join(receipts, 'results.json') }]],
  use: { locale: 'zh-CN', viewport: { width: 1440, height: 900 }, trace: 'retain-on-failure', screenshot: 'only-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined },
  projects: [
    { name: 'v2-live-chromium', grepInvert: /default-off|acceptance-mode/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: 'http://127.0.0.1:5177' } },
    { name: 'v1-chromium', grep: /default-off/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: 'http://127.0.0.1:5178' } },
    { name: 'v1-acceptance-chromium', grep: /acceptance-mode/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: 'http://127.0.0.1:5179' } },
  ],
  webServer: [...servers('enabled', 8017, 5177, true), ...servers('default-off', 8018, 5178, false), ...servers('acceptance-mode', 8019, 5179, true, true)],
});
