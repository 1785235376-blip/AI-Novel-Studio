// Real-HTTP React integration, separate from actual Playwright/browser evidence.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.dirname(frontend);
const data = fs.mkdtempSync(path.join(os.tmpdir(), 'r3-ui-http-'));
const port = Number(process.env.R3_HTTP_PORT || 8019);
const base = `http://127.0.0.1:${port}`;
const home = path.join(data, 'home'); fs.mkdirSync(home);
const backend = spawn(process.env.R3_PYTHON || 'python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)], {
  cwd: root, stdio: 'inherit', env: { ...process.env, HOME: home, XDG_DATA_HOME: path.join(data, 'xdg'), NOVEL_DATA_PATH: path.join(data, 'novels'), STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'false', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'true', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', V1_ACCEPTANCE_MODE: 'false', EXPERIMENTAL_FEATURES: 'advanced_planning_v2,semantic_import_v2,world_character_engines_v2,unified_review_inbox,agent_team_recipes,media_adapter_registry,cover_storyboard_generation,visual_embeddings,audiobook_v2' },
});
let startupError;
backend.on('error', error => { startupError = error; });
const stop = () => { if (backend.exitCode == null) backend.kill('SIGTERM'); };
process.on('SIGINT', stop); process.on('SIGTERM', stop);
try {
  let healthy = false;
  for (let attempt = 0; attempt < 120; attempt++) {
    if (startupError) throw startupError;
    if (backend.exitCode != null) throw new Error(`Isolated backend exited ${backend.exitCode}`);
    try { healthy = (await fetch(base + '/api/health')).ok; } catch { /* Startup is pending. */ }
    if (healthy) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!healthy) throw new Error('Isolated backend startup timed out');
  const runner = spawn(process.execPath, ['node_modules/vitest/vitest.mjs', 'run', 'src/experimental/ExperimentalWorkbench.http.test.tsx', '--maxWorkers=1', '--minWorkers=1'], { cwd: frontend, stdio: 'inherit', env: { ...process.env, R3_HTTP_BASE: base } });
  const [code] = await once(runner, 'exit'); process.exitCode = code ?? 1;
} catch (error) { console.error(error); process.exitCode = 1; }
finally { stop(); }
