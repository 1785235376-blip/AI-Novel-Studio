import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { isPackagedDesktopHost } from '../packagedHost';
import type { CreativeAsset, CreativeCapabilities, CreativeDocument, CreativeInput, CreativeReferences, DirectorSceneNote } from './types';

export type DirectorModelRoute = { route_id: string; provider_id: string; model_id: string; model_version?: string | null; synthetic: boolean; available: boolean; reasons: string[] };
export type DirectorModelPreview = { preview_digest: string; execution_available: boolean; model_called: false; allow_cloud_fallback: false; automatic_retry: false; timeout_seconds: number; source_strategy: string; request: Record<string, unknown>; broker: { chosen?: { provider_id?: string; model_id?: string; price?: { reserve_microusd?: number } } | null } };
export type DirectorProposal = { id: string; version: number; status: string; source_document_id: string; source_version: number; title: string; director_notes: DirectorSceneNote[]; output_digest: string; provenance: { model_called?: boolean; [key: string]: unknown }; model_preview?: DirectorModelPreview | null; model_execution?: { job_id: string; status: string; model_called: boolean; receipt_state: string; usage_state: string; failure_code?: string } | null };
export type CreativeHistory = { document_id: string; current_version: number; items: CreativeDocument[] };
export function creativeClient(novelId: string, context: CollaborationContext) {
  // Capture a complete origin. No request may borrow a later session or branch.
  const token = context.sessionToken || (!context.scope && !context.actor && !isPackagedDesktopHost() ? (context.localHostToken ?? useLocalHostSession.getState().token) : '');
  const branch = context.scope?.branchId;
  const root = `/api/novels/${encodeURIComponent(novelId)}`;
  const base = `${root}/experimental/creative`;
  async function request<T>(url: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Request-ID': crypto.randomUUID() };
    if (token) headers['X-Session-Token'] = token;
    if (branch) headers['X-Branch-Id'] = branch;
    if (method !== 'GET') headers['Idempotency-Key'] = crypto.randomUUID();
    const response = await fetch(url, { method, headers, signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    if (!response.ok) {
      let raw: { code?: unknown; detail?: { code?: unknown } } = {};
      try { raw = await response.json(); } catch { /* Never render server HTML or provider details. */ }
      const code = raw.code ?? raw.detail?.code;
      throw new ApiError({ status: response.status, code: typeof code === 'string' ? code : 'CREATIVE_REQUEST_FAILED', message: response.status === 409 ? '版本或来源已经变化。当前草稿已保留，请核对服务端版本。' : response.status === 401 || response.status === 403 ? '当前会话无权访问此内容。请重新核对身份和分支。' : response.status === 404 ? '记录不可用，或此功能尚未启用。' : '请求未完成。请核对输入与连接状态。' });
    }
    return response.json() as Promise<T>;
  }
  return {
    capabilities: (signal?: AbortSignal) => request<CreativeCapabilities>(`${base}/capabilities`, 'GET', undefined, signal),
    list: (signal?: AbortSignal) => request<{ items: CreativeDocument[] }>(`${base}/documents`, 'GET', undefined, signal),
    get: (id: string, signal?: AbortSignal) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'GET', undefined, signal),
    create: (body: CreativeInput) => request<CreativeDocument>(`${base}/documents`, 'POST', body),
    update: (id: string, version: number, body: CreativeInput) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'PUT', { ...body, expected_version: version }),
    derive: (source: CreativeDocument, mode: 'STORYBOARD' | 'PRODUCTION') => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/derive`, 'POST', { expected_version: source.version, mode }),
    restore: (source: CreativeDocument, restoreVersion: number) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/restore`, 'POST', { expected_version: source.version, restore_version: restoreVersion }),
    history: (id: string, signal?: AbortSignal) => request<CreativeHistory>(`${base}/documents/${encodeURIComponent(id)}/history`, 'GET', undefined, signal),
    export: (id: string) => request<{ document: CreativeDocument; document_digest: string; format: string; boundary: string }>(`${base}/documents/${encodeURIComponent(id)}/export`),
    references: (signal?: AbortSignal) => request<CreativeReferences>(`${root}/creation-reference-data`, 'GET', undefined, signal),
    assets: (signal?: AbortSignal) => request<CreativeAsset[]>(`${root}/assets`, 'GET', undefined, signal),
    modelRoutes: (signal?: AbortSignal) => request<{ items: DirectorModelRoute[] }>(`${base}/director-proposals/model-routes`, 'GET', undefined, signal),
    previewModel: (proposal: DirectorProposal, routeId: string) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/preview`, 'POST', { expected_version: proposal.version, route_id: routeId }),
    dispatchModel: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/dispatch`, 'POST', { expected_version: proposal.version, reviewed_preview_digest: proposal.model_preview?.preview_digest }),
    refreshModel: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/refresh`, 'POST', { expected_version: proposal.version }),
    proposals: (signal?: AbortSignal) => request<{ items: DirectorProposal[] }>(`${base}/director-proposals`, 'GET', undefined, signal),
    propose: (source: CreativeDocument) => request<DirectorProposal>(`${base}/director-proposals`, 'POST', { source_document_id: source.id, expected_source_version: source.version }),
    review: (proposal: DirectorProposal, title: string, notes: DirectorSceneNote[]) => request<{ proposal: DirectorProposal; document: CreativeDocument }>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/review`, 'POST', { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title, director_notes: notes }),
    cancelProposal: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/cancel`, 'POST', { expected_version: proposal.version }),
  };
}
export type CreativeClient = ReturnType<typeof creativeClient>;
