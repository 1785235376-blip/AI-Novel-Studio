import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(frontend, '..');
const python = process.env.R3_PYTHON || 'python';
const data = process.env.R3_BROWSER_DATA_ROOT || fs.mkdtempSync(path.join(os.tmpdir(), 'ai-novel-r3-browser-'));
const flags = 'advanced_planning_v2,semantic_import_v2,world_character_engines_v2,unified_review_inbox,agent_team_recipes,media_adapter_registry,cover_storyboard_generation,visual_embeddings,audiobook_v2';
function backend(port: number, mode: string, experimental: string, acceptance = 'false') {
  const isolated = path.join(data, mode); fs.mkdirSync(isolated, { recursive: true });
  return { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${port}`, cwd: root, url: `http://127.0.0.1:${port}/api/health`, timeout: 60000, reuseExistingServer: false,
    env: { HOME: isolated, XDG_DATA_HOME: path.join(isolated, 'xdg'), NOVEL_DATA_PATH: path.join(isolated, 'novels'), STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'false', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'true', MOCK_STREAM_DELAY_MS: '0', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: experimental, V1_ACCEPTANCE_MODE: acceptance, FRONTEND_ORIGIN: `http://127.0.0.1:${port - 2840}` } };
}
function frontendServer(port: number, apiPort: number) {
  return { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port}`, cwd: frontend, url: `http://127.0.0.1:${port}`, timeout: 60000, reuseExistingServer: false, env: { V061_API_URL: `http://127.0.0.1:${apiPort}` } };
}
export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: /r3-experimental\.spec\.ts/, outputDir: path.join(frontend, 'test-results', 'experimental'), fullyParallel: false, workers: 1, timeout: 120000, expect: { timeout: 15000 },
  reporter: [['list'], ['junit', { outputFile: process.env.CI_RECEIPTS ? path.join(process.env.CI_RECEIPTS, 'experimental.xml') : 'test-results-r3/experimental.xml' }]],
  use: { baseURL: 'http://127.0.0.1:5176', viewport: { width: 1440, height: 900 }, locale: 'zh-CN', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined } }],
  webServer: [backend(8016, 'enabled', flags), frontendServer(5176, 8016), backend(8017, 'default-off', ''), frontendServer(5177, 8017), backend(8018, 'v1-acceptance', flags, 'true')],
});
