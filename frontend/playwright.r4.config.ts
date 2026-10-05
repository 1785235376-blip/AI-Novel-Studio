import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(frontend, '..');
const python = process.env.R4_PYTHON || 'python';
const data = process.env.R4_BROWSER_DATA_ROOT || fs.mkdtempSync(path.join(os.tmpdir(), 'ai-novel-r4-browser-'));
const flags = 'advanced_planning_v2,semantic_import_v2,world_character_engines_v2,unified_review_inbox,agent_team_recipes,media_adapter_registry,cover_storyboard_generation,visual_embeddings,audiobook_v2,writing_recovery_v2,workspace_tools_v2,local_ai_workflow_inspector_v2,author_context_inspector_v2,writing_focus_v2,temporal_story_graph_v2,character_mind_v2,asset_lineage_v2,production_manifest_v2,style_dna_v2,narrative_quality_judge_v2,change_impact_v2,story_simulator_v2,research_library_v2,revision_intelligence_v2,selection_assistant_v2,reader_preflight_v2,writing_sessions_v2,ai_director_v2,timeline_exchange_v2,voice_direction_v2,subtitle_timeline_v2,portable_projects_v2,safe_batches_v2,multilingual_editions_v2,template_library_v2,declarative_agents_v2';
function backend(port: number, mode: string, experimental: string, acceptance = 'false', extraEnv: Record<string, string> = {}) {
  const isolated = path.join(data, mode); fs.mkdirSync(isolated, { recursive: true });
  return { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${port}`, cwd: root, url: `http://127.0.0.1:${port}/api/health`, timeout: 60000, reuseExistingServer: false,
    env: { HOME: isolated, XDG_DATA_HOME: path.join(isolated, 'xdg'), NOVEL_DATA_PATH: path.join(isolated, 'novels'), STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'false', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'false', MOCK_STREAM_DELAY_MS: '0', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: experimental, V1_ACCEPTANCE_MODE: acceptance, FRONTEND_ORIGIN: `http://127.0.0.1:${port - 2840}`, ...extraEnv } };
}
function frontendServer(port: number, apiPort: number) {
  return { command: `"${process.execPath}" node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port}`, cwd: frontend, url: `http://127.0.0.1:${port}`, timeout: 60000, reuseExistingServer: false, env: { V061_API_URL: `http://127.0.0.1:${apiPort}` } };
}
export default defineConfig({
  testDir: path.join(frontend, 'tests', 'e2e'), testMatch: '**/r4-*.spec.ts', outputDir: path.join(frontend, 'test-results', 'r4-ux'), fullyParallel: false, workers: 1, timeout: 300000, expect: { timeout: 15000 },
  reporter: [['list'], ['junit', { outputFile: process.env.CI_RECEIPTS ? path.join(process.env.CI_RECEIPTS, 'r4-ux.xml') : 'test-results-r4/r4-ux.xml' }]],
  use: { baseURL: 'http://127.0.0.1:5179', viewport: { width: 1440, height: 900 }, locale: 'zh-CN', actionTimeout: 15000, navigationTimeout: 30000, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined } }],
  webServer: [backend(8019, 'enabled', flags), frontendServer(5179, 8019), backend(8020, 'default-off', ''), frontendServer(5180, 8020), backend(8021, 'v1-acceptance', flags, 'true'),
    backend(8022, 'broker', `${flags},model_broker_v2,model_benchmark_v2`, 'false', {
      MOCK_STREAM_DELAY_MS: '350', COLLABORATION_DEV_SESSIONS_JSON: JSON.stringify([{ token: 'r4-broker-test-session', session_id: 'r4-broker-session-id', client_id: 'r4-broker-browser', actor_id: 'r4-broker-author', workspace_id: 'r4-broker-workspace' }]),
    }), frontendServer(5182, 8022)],
});
