import { ApiError, getCollaborationContext, type CollaborationContext } from '../api';

export type ExperimentalFlags = { experimental: boolean; default_enabled: false; features: Record<string, boolean> };
export type Row = Record<string, any> & { id: string; version: number; status?: string; stale?: boolean };
export type Rows = { items: Row[]; total?: number };
const requestId = () => globalThis.crypto?.randomUUID?.() || `experimental-${Date.now()}-${Math.random().toString(16).slice(2)}`;
export const segment = encodeURIComponent;
export const enabled = (flags: ExperimentalFlags | undefined, key: string) => flags?.features?.[`experimental.${key}`] === true;

async function request<T>(url: string, method: string, body?: unknown, context?: CollaborationContext, signal?: AbortSignal, asBlob = false): Promise<T> {
  const current = context ?? getCollaborationContext();
  const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Request-ID': requestId() };
  if (current.sessionToken) headers['X-Session-Token'] = current.sessionToken;
  if (current.scope?.branchId) headers['X-Branch-Id'] = current.scope.branchId;
  if (method !== 'GET') headers['Idempotency-Key'] = requestId();
  const response = await fetch(url, { method, headers, signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  if (!response.ok) {
    let raw: any = {};
    try { raw = await response.json(); } catch { /* Never render arbitrary server HTML. */ }
    const detail = raw.detail ?? raw.error ?? raw;
    const code = raw.code ?? detail?.code ?? (response.status === 403 ? 'FORBIDDEN' : response.status === 409 ? 'VERSION_CONFLICT' : 'EXPERIMENTAL_REQUEST_FAILED');
    throw new ApiError({ status: response.status, code: typeof code === 'string' ? code : 'EXPERIMENTAL_REQUEST_FAILED', message: response.status === 409 ? '版本或来源已改变。草稿已保留，请刷新并核对后再操作。' : response.status === 403 ? '当前身份没有此操作权限。' : response.status === 404 ? '功能未启用或记录不可用。' : '操作未完成，请核对输入后重试。', request_id: raw.request_id ?? response.headers.get('X-Request-ID') ?? undefined });
  }
  return response.status === 204 ? undefined as T : asBlob ? response.blob() as Promise<T> : response.json();
}
export const experimentalFeatures = (signal?: AbortSignal, context?: CollaborationContext) => request<ExperimentalFlags>('/api/experimental/features', 'GET', undefined, context, signal);
export function experimentalClient(novelId: string, context: CollaborationContext) {
  // Capture the originating session/branch: a later navigation cannot redirect a request.
  const captured = { ...context, scope: context.scope ? { ...context.scope } : undefined };
  const base = `/api/novels/${segment(novelId)}/experimental`;
  return {
    get: <T = any>(path: string, signal?: AbortSignal) => request<T>(base + path, 'GET', undefined, captured, signal),
    blob: (path: string, signal?: AbortSignal) => request<Blob>(base + path, 'GET', undefined, captured, signal, true),
    post: <T = any>(path: string, body: unknown) => request<T>(base + path, 'POST', body, captured),
    put: <T = any>(path: string, body: unknown) => request<T>(base + path, 'PUT', body, captured),
  };
}
export type ExperimentalClient = ReturnType<typeof experimentalClient>;
