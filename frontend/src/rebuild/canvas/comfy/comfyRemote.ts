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


export type RunQuote = {
  quote_id: string; quote_digest: string; kind: 'image' | 'video'; draft_version: number;
  provider_id: string; node_count: number; edge_count: number; output_nodes: string[];
  price: {currency: string; amount_micros: number; reason: string};
  expires_at: string; confirmation_required: boolean;
};
export type RunAsset = {id: string; filename?: string; media_type?: string; sha256?: string; size?: number; width?: number; height?: number; version?: number};
export type LowerCanvasRun = {
  id: string; contract: string; kind: 'image' | 'video'; status: 'RUNNING' | 'COMPLETED' | 'FAILED';
  draft_version: number; quote_digest: string; provider_id: string; node_count: number; edge_count: number;
  output_nodes: string[]; assets: RunAsset[]; error: {code?: string; reason?: string} | null; created_at: string; updated_at: string;
};

// [HERMIA-FE-20261031 DUALCANVAS-COMFY RUN] Local ComfyUI only; quote must be confirmed and
// consumed; the backend records the run and writes assets. Nothing here calls a model directly.
export async function preflightLowerCanvasRun(remote: ComfyRemoteContext, kind: 'image' | 'video',
                                              expectedVersion: number): Promise<RunQuote> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/lower-canvas/${kind}/runs/preflight`,
    {method: 'POST', headers: headers(remote, true),
     body: JSON.stringify({expected_version: expectedVersion})});
  if (!response.ok) throw new Error('COMFY_RUN_PREFLIGHT_' + response.status);
  return await parseJson(response) as RunQuote;
}

export async function dispatchLowerCanvasRun(remote: ComfyRemoteContext, kind: 'image' | 'video',
                                             quote: RunQuote): Promise<LowerCanvasRun> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/lower-canvas/${kind}/runs`,
    {method: 'POST', headers: headers(remote, true),
     body: JSON.stringify({expected_version: quote.draft_version, quote_id: quote.quote_id,
       quote_digest: quote.quote_digest})});
  if (!response.ok) throw new Error('COMFY_RUN_DISPATCH_' + response.status);
  return await parseJson(response) as LowerCanvasRun;
}

export async function fetchLowerCanvasRun(remote: ComfyRemoteContext, kind: 'image' | 'video',
                                           runId: string): Promise<LowerCanvasRun> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/lower-canvas/${kind}/runs/${encodeURIComponent(runId)}`,
    {method: 'GET', headers: headers(remote), cache: 'no-store'});
  if (!response.ok) throw new Error('COMFY_RUN_GET_' + response.status);
  return await parseJson(response) as LowerCanvasRun;
}


/** Read one generated asset for a bounded preview; no content is persisted in the draft. */
export async function downloadAssetBlob(remote: ComfyRemoteContext, assetId: string): Promise<Blob> {
  const f = fetchImpl();
  if (!f) throw new Error('COMFY_REMOTE_UNAVAILABLE');
  if (!/^[A-Za-z0-9_.:-]{1,240}$/.test(assetId)) throw new Error('COMFY_ASSET_ID_INVALID');
  const response = await f(`/api/projects/${encodeURIComponent(remote.projectId)}/studio/assets/${encodeURIComponent(assetId)}/download`,
    {method: 'GET', headers: headers(remote), cache: 'no-store'});
  if (!response.ok) throw new Error('COMFY_ASSET_DOWNLOAD_' + response.status);
  const blob = await response.blob();
  if (!blob.size || blob.size > 16 * 1024 * 1024) throw new Error('COMFY_ASSET_SIZE_INVALID');
  if (!/^image\/(png|jpeg|webp)$/.test(blob.type)) throw new Error('COMFY_ASSET_MEDIA_INVALID');
  return blob;
}
