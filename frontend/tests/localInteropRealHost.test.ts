// Opt-in HTTP/client integration, distinct from browser rendering and Desktop integration.
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { interopClient } from '../src/interop/client';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const API = 'http://127.0.0.1:8051';
const scope = { workspaceId: 'interop-browser-workspace', projectId: 'interop-browser-book', storylineId: 'interop-browser-story', branchId: 'interop-browser-branch' };
const context = { sessionToken: 'interop-browser-mock-session', scope };
const hostScope = { workspace_id: scope.workspaceId, project_id: scope.projectId, storyline_id: scope.storylineId, branch_id: scope.branchId };
const nativeFetch = globalThis.fetch;
const processes: ChildProcess[] = [];
let logs = '';
let chapter: { id: string; version: number; content: string };
const id = () => crypto.randomUUID();

async function waitFor(url: string) {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (processes.some(child => child.exitCode !== null)) throw new Error(`MOCK_ONLY fixture exited: ${logs}`);
    try { if ((await nativeFetch(url)).ok) return; } catch { /* Startup only. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`MOCK_ONLY fixture startup timeout: ${logs}`);
}

describe.skipIf(process.env.LOCAL_INTEROP_REAL_HOST_TEST !== '1')('real frontend client / isolated Studio / Synthetic Tutor (MOCK_ONLY)', () => {
  beforeAll(async () => {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), 'local-interop-client-mock-'));
    const env = { ...process.env, LOCAL_INTEROP_BROWSER_FIXTURE: 'MOCK_ONLY', HOME: home, XDG_DATA_HOME: path.join(home, 'xdg'), NOVEL_DATA_PATH: path.join(home, 'novels'), PROJECT_ROOT: home, STORAGE_BACKEND: 'file', ENABLE_COLLABORATION_RUNTIME: 'true', ENABLE_PACKAGED_RUNTIME: 'false', MOCK_PROVIDER: 'true', ENABLE_CLOUD: 'false', CREDENTIAL_VAULT_BACKEND: 'memory', CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK: 'true', EXPERIMENTAL_FEATURES: 'local_tutor_interop_v1', V1_ACCEPTANCE_MODE: 'false', PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: '1' };
    const python = process.env.INTEROP_PYTHON || 'python';
    for (const args of [['frontend/scripts/local_interop_browser_host.py'], ['scripts/run_synthetic_tutor.py', '--port', '8052']]) {
      const child = spawn(python, args, { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
      child.stderr?.on('data', chunk => { logs += String(chunk); });
      child.stdout?.on('data', chunk => { logs += String(chunk); }); processes.push(child);
    }
    await Promise.all([waitFor(API + '/api/health'), waitFor('http://127.0.0.1:8052/interop/v1/discovery')]);
    globalThis.fetch = ((url: string | URL | Request, init?: RequestInit) => nativeFetch(typeof url === 'string' && url.startsWith('/') ? API + url : url, init)) as typeof fetch;
    const chapters = await (await fetch(`/api/collaboration/workspaces/${scope.workspaceId}/projects/${scope.projectId}/storylines/${scope.storylineId}/branches/${scope.branchId}/chapters`, { headers: { 'X-Session-Token': context.sessionToken } })).json();
    expect(chapters.items.length).toBe(1);
    chapter = await (await fetch(`/api/chapters/${encodeURIComponent(chapters.items[0].id)}`, { headers: { 'X-Session-Token': context.sessionToken, 'X-Branch-Id': scope.branchId } })).json();
    expect(chapter.content).toContain('合成😀选区');
  }, 25_000);
  afterAll(async () => {
    globalThis.fetch = nativeFetch;
    await Promise.all(processes.map(child => new Promise<void>(resolve => {
      if (child.exitCode !== null) { resolve(); return; }
      child.once('exit', () => { clearTimeout(timer); resolve(); }); child.kill('SIGTERM');
      const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(); }, 5000);
    })));
  });
  it('matches the actual immutable context, wire session, diagnostic, verifier and handoff contracts', async () => {
    const client = interopClient(context);
    expect((await client.status()).enabled).toBe(false);
    await client.settings(true, id());
    const connected = await client.connect({ request_id: id(), endpoint: 'http://127.0.0.1:8052', project_id: scope.projectId, scope: hostScope, module: 'NOVEL', surface: 'editor', chapter_id: chapter.id });
    expect(connected.mode).toBe('MOCK_ONLY'); expect(connected.protocol_session_id).toBeTruthy();
    expect(connected.protocol_session_id).not.toBe(connected.session_id);
    const preview = await client.preview({ request_id: id(), session_id: connected.session_id, chapter_id: chapter.id, content_kind: 'NONE', metadata_fields: ['task', 'error', 'model', 'runtime'] });
    expect(preview.capsule.content?.level).toBe('NONE'); expect(preview.capsule.content?.text).toBeNull();
    const guide = await client.ask(connected.session_id, preview.preview_id, id());
    expect(guide.session_id).toBe(connected.session_id); expect(guide.guidance.session_id).toBe(connected.protocol_session_id);
    expect(guide.guidance.summary).toContain('MOCK_ONLY');
    const selected = await client.preview({ request_id: id(), session_id: connected.session_id, chapter_id: chapter.id, expected_chapter_version: chapter.version, content_kind: 'SELECTION', selection_start: 0, selection_end: 5, metadata_fields: [] });
    expect(selected.capsule.content?.text).toBe('合成😀选区');
    const diagnostic = await client.diagnosticPreview(connected.session_id, ['software_version', 'task_state'], id());
    expect(diagnostic.diagnostic.software_id).toBeNull(); expect(diagnostic.diagnostic.feature).toBeNull();
    expect(diagnostic.capsule.project_id).toBeNull(); expect(diagnostic.capsule.content?.level).toBe('NONE');
    const shared = await client.diagnosticShare(connected.session_id, diagnostic.preview_id, id());
    expect(shared.guidance.session_id).toBe(connected.protocol_session_id);
    const verified = await client.verify(connected.session_id, guide.guidance.guidance_id, id());
    expect(verified.result.session_id).toBe(connected.protocol_session_id); expect(verified.result.status).toBe('UNKNOWN');
    const route = await client.handoff(connected.session_id, guide.guidance.steps![0].handoff!, id());
    expect(route.route.action).toBe('OPEN_FEATURE'); expect(route.route.feature).toBe('model-center');
    const unchanged = await (await fetch(`/api/chapters/${encodeURIComponent(chapter.id)}`, { headers: { 'X-Session-Token': context.sessionToken, 'X-Branch-Id': scope.branchId } })).json();
    expect(unchanged.content).toBe(chapter.content); expect(unchanged.version).toBe(chapter.version);
    await client.disconnect(connected.session_id);
    await expect(client.preview({ request_id: id(), session_id: connected.session_id, content_kind: 'NONE', metadata_fields: [] })).rejects.toMatchObject({ problem: { code: 'SESSION_REVOKED' } });
    await client.settings(false, id()); expect((await client.status()).enabled).toBe(false);
  }, 20_000);
});
