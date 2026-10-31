// [HERMIA-FE-20261031 DUALCANVAS-COMFY] Read-only node-library import + lower-canvas
// backend sync. Network access is only constructed when a real workspace identity
// exists; no-identity canvases stay in session memory (as before).
import {parseObjectInfo, type CfGraph, type NodeDef} from './comfyRegistry';

export type ComfyRemoteContext = {projectId: string; token: string; branchId?: string};
export type ImportedObjectInfo = {defs: NodeDef[]; errors: number; sourceVersion: string};
export type RemoteGraph = {version: number; graph: CfGraph};
export type SaveRemoteResult = {ok: true; version: number} | {ok: false; currentVersion: number};

function fetchImpl(): typeof fetch | null {
  const f = (globalThis as {fetch?: typeof fetch}).fetch;
  return typeof f === 'function' ? f.bind(globalThis) : null;
}

function headers(remote: ComfyRemoteContext, json = false): Record<string, string> {
  const result: Record<string, string> = {'X-Request-ID': crypto.randomUUID()};
  if (json) result['Content-Type'] = 'application/json';
  if (remote.token) result['X-Session-Token'] = remote.token;
  if (remote.branchId) result['X-Branch-Id'] = remote.branchId;
  return result;
}

async function parseJson(response: Response): Promise<unknown> {
  try { return await response.json(); } catch { return null; }
}

/** GET /api/comfy/object_info. 503 / network failure → null (caller keeps built-ins). */
export async function fetchImportedObjectInfo(signal?: AbortSignal): Promise<ImportedObjectInfo | null> {
  const f = fetchImpl();
  if (!f) return null;
  const response = await f('/api/comfy/object_info', {method: 'GET', headers: headers({projectId: '', token: ''}), signal,
    cache: 'no-store'});
  if (!response.ok) return null;
  const raw = await parseJson(response);
  const parsed = parseObjectInfo(raw, 'imported');
  return {defs: parsed.defs, errors: parsed.errors.length,
    sourceVersion: response.headers.get('X-Comfy-Source-Version') || ''};
}

function normalizeGraph(raw: unknown): CfGraph | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const value = raw as {nodes?: unknown; edges?: unknown};
  if (!Array.isArray(value.nodes) || !Array.isArray(value.edges)) return null;
  return {nodes: value.nodes as CfGraph['nodes'], edges: value.edges as CfGraph['edges']};
}

/** GET /api/projects/{id}/studio/lower-canvas/{kind}. Empty/unavailable → version 0. */
export async function loadRemoteComfyGraph(kind: 'image' | 'video', remote: ComfyRemoteContext,
                                           signal?: AbortSignal): Promise<RemoteGraph> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/lower-canvas/${kind}`,
    {method: 'GET', headers: headers(remote), signal, cache: 'no-store'});
  if (response.status === 404 || response.status === 401 || response.status === 403) {
    return {version: 0, graph: {nodes: [], edges: []}};
  }
  if (!response.ok) throw new Error(`COMFY_REMOTE_LOAD_${response.status}`);
  const value = await parseJson(response) as {version?: unknown; graph?: unknown} | null;
  const version = Number(value?.version);
  const graph = normalizeGraph(value?.graph);
  if (!Number.isSafeInteger(version) || version < 0 || !graph) throw new Error('COMFY_REMOTE_GRAPH_INVALID');
  return {version, graph};
}

/** PUT /api/projects/{id}/studio/lower-canvas/{kind}; CAS version from the last GET/save. */
export async function saveRemoteComfyGraph(kind: 'image' | 'video', remote: ComfyRemoteContext,
                                           expectedVersion: number, graph: CfGraph): Promise<SaveRemoteResult> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/lower-canvas/${kind}`,
    {method: 'PUT', headers: headers(remote, true), body: JSON.stringify({expected_version: expectedVersion, graph})});
  if (response.status === 409) {
    const value = await parseJson(response) as {detail?: {current_version?: unknown}; current_version?: unknown} | null;
    const current = Number(value?.detail?.current_version ?? value?.current_version);
    return {ok: false, currentVersion: Number.isSafeInteger(current) && current >= 0 ? current : 0};
  }
  if (!response.ok) throw new Error(`COMFY_REMOTE_SAVE_${response.status}`);
  const value = await parseJson(response) as {version?: unknown} | null;
  const version = Number(value?.version);
  if (!Number.isSafeInteger(version) || version < 1) throw new Error('COMFY_REMOTE_SAVE_INVALID');
  return {ok: true, version};
}
