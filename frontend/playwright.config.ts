import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {defineConfig, devices} from '@playwright/test';
import {buildBackendEnvironment, buildFixtureEnvironment, buildFrontendEnvironment, resolveE2EDatabaseContract} from './src/e2eDatabaseContract';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(frontend, '..');
const python = path.join(root, '.venv', 'Scripts', 'python.exe');
const fixture = path.join(root, 'tests', 'e2e', 'database_fixture.py');
const databaseContract = resolveE2EDatabaseContract(process.env);
const fixtureEnvironment = buildFixtureEnvironment(process.env, databaseContract);
const backendEnvironment = buildBackendEnvironment(process.env, databaseContract);
const frontendEnvironment = buildFrontendEnvironment(process.env);
export const mockProviderForVerification = (value=process.env.REAL_PROVIDER_VERIFICATION) => value === 'true' ? 'false' : 'true';
execFileSync(python, [fixture, 'prepare'], {stdio: 'inherit', env: fixtureEnvironment});

export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'),
  testMatch: /(writer-flow|conflict-recovery|workspace-management|novel-production-flow|text-model-selection|visual-text-workflow|runtime-diagnostics|route-readiness-guidance)\.spec\.ts/,
  timeout: 120_000,
  expect: {timeout: 15_000},
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['json', {outputFile: path.join(root, 'browser_e2e_results.json')}]],
  globalTeardown: path.join(root, 'tests', 'e2e', 'global-teardown.ts'),
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{name: 'chromium', use: {...devices['Desktop Chrome'], acceptDownloads: true}}],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: root,
      env: {...backendEnvironment, STORAGE_BACKEND: 'postgres', MOCK_PROVIDER: mockProviderForVerification(), MOCK_STREAM_DELAY_MS: '0', FRONTEND_ORIGIN: 'http://127.0.0.1:5173', COLLABORATION_DEV_SESSIONS_JSON: JSON.stringify([{token:'e2e-admin-session',actor_id:'e2e-admin',workspace_id:'e2e-workspace-a',session_id:'e2e-session',client_id:'e2e-browser'}])},
      url: 'http://127.0.0.1:8000/api/health',
      timeout: 60_000,
      reuseExistingServer: false,
    },
    {
      command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173`,
      cwd: frontend,
      env: frontendEnvironment,
      url: 'http://127.0.0.1:5173',
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
});
