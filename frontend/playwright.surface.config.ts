import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(frontend, '..');
const isolated = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-novel-surface-browser-'));
const python = process.env.SURFACE_PYTHON || 'python';
export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: '**/surface-freeze-*.spec.ts',
  outputDir: path.join(frontend, 'test-results', 'functional-surface'), fullyParallel: false,
  workers: 1, timeout: 120000, expect: { timeout: 15000 },
  reporter: [['list'], ['junit', { outputFile: process.env.CI_RECEIPTS ? path.join(process.env.CI_RECEIPTS, 'functional-surface-browser.xml') : 'test-results/functional-surface-browser.xml' }]],
  use: { baseURL: 'http://127.0.0.1:5207', viewport: { width: 1440, height: 900 }, locale: 'zh-CN', actionTimeout: 15000, navigationTimeout: 30000, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined } }],
  webServer: [
    { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8047`, cwd: root, url: 'http://127.0.0.1:8047/api/health', timeout: 60000, reuseExistingServer: false,
      env: { HOME: isolated, XDG_DATA_HOME: path.join(isolated, 'xdg'), NOVEL_DATA_PATH: path.join(isolated, 'novels'), STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'false', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'false', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: 'workspace_tools_v2,workspace_interaction_v1,visual_embeddings,semantic_import_v2,world_character_engines_v2,temporal_story_graph_v2,research_library_v2,story_record_versions_v1,finding_review_v1,adaptation_lifecycle_v1', V1_ACCEPTANCE_MODE: 'false', FRONTEND_ORIGIN: 'http://127.0.0.1:5207' } },
    { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5207`, cwd: frontend, url: 'http://127.0.0.1:5207', timeout: 60000, reuseExistingServer: false, env: { V061_API_URL: 'http://127.0.0.1:8047' } },
  ],
});
