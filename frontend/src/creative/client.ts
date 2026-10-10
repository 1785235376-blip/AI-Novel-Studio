import { parseScreenplayPresets, type ScreenplayPresetCatalog } from './screenplayPresets';
import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { isPackagedDesktopHost } from '../packagedHost';
import type { CreativeAsset, CreativeCapabilities, CreativeDocument, CreativeInput, CreativeReferences, DirectorSceneNote } from './types';

export type DirectorModelRoute = { route_id: string; provider_id: string; model_id: string; model_version?: string | null; synthetic: boolean; available: boolean; reasons: string[] };
export type DirectorModelPreview = { preview_digest: string; execution_available: boolean; model_called: false; allow_cloud_fallback: false; automatic_retry: false; timeout_seconds: number; source_strategy: string; request: Record<string, unknown>; broker: { chosen?: { provider_id?: string; model_id?: string; price?: { reserve_microusd?: number } } | null } };
export type DirectorProposal = { id: string; version: number; status: string; source_document_id: string; source_version: number; title: string; director_notes: DirectorSceneNote[]; output_digest: string; provenance: { model_called?: boolean; [key: string]: unknown }; model_preview?: DirectorModelPreview | null; model_execution?: { job_id: string; status: string; model_called: boolean; receipt_state: string; usage_state: string; failure_code?: string } | null };
export type AdaptationChange = { id: string; kind: 'SCENE_SPLIT' | 'VISUALIZATION' | 'DIALOGUE' | 'OMISSION' | 'INFERENCE'; source_quote: string; scene_ids: string[]; note: string };
export type AdaptationOutput = { scenes: import('./types').CreativeScene[]; report: { summary: string; changes: AdaptationChange[] } };
export type AdaptationAssetOutput = { contract: string; state: string; asset_id: string | null; version: number | null; sha256?: string; size?: number; reason?: string; execution_receipt?: Record<string, unknown> };
export type AdaptationProposal = { asset_output?: AdaptationAssetOutput; id: string; version: number; status: string; title: string; chapter_id: string; source_version: number; source_digest: string; selection_digest: string; selected_text: string; output: AdaptationOutput | null; output_digest: string | null; model_preview: DirectorModelPreview | null; model_execution: DirectorProposal['model_execution']; provenance: Record<string, unknown> | null; document_id: string | null };
export type CreativeHistory = { document_id: string; current_version: number; items: CreativeDocument[] };
export type ScreenplayExportFormat = 'fountain' | 'docx' | 'markdown' | 'epub';
export type ScriptExportFormat = 'txt' | 'docx' | 'markdown';
export type ScreenplayDownload = { blob: Blob; filename: string; documentVersion: number; documentDigest: string; sha256: string };
export function creativeClient(novelId: string, context: CollaborationContext) {
  // Capture a complete origin. No request may borrow a later session or branch.
  const token = context.sessionToken || (!context.scope && !context.actor && !isPackagedDesktopHost() ? (context.localHostToken ?? useLocalHostSession.getState().token) : '');
  const branch = context.scope?.branchId;
  const root = `/api/novels/${encodeURIComponent(novelId)}`;
  const base = `${root}/experimental/creative`;
  async function responseFor(url: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<Response> {
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
    return response;
  }
  async function request<T>(url: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    return (await responseFor(url, method, body, signal)).json() as Promise<T>;
  }
  async function verifiedTextExport(source: CreativeDocument, format: string, kind: 'SCREENPLAY' | 'SCRIPT', signal?: AbortSignal): Promise<ScreenplayDownload> {
    const formats: Record<string, [string, string]> = { ...(kind === 'SCREENPLAY' ? { fountain: ['text/x-fountain', 'fountain'] as [string, string], epub: ['application/epub+zip', 'epub'] as [string, string] } : { txt: ['text/plain', 'txt'] as [string, string] }), docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx'], markdown: ['text/markdown', 'md'] };
    const invalid = () => new ApiError({ status: 502, code: 'CREATIVE_EXPORT_RECEIPT_INVALID', message: '导出文件与当前版本不一致或校验失败。未下载文件，请重新核对已保存版本。' });
    if (source.mode !== kind || !formats[format] || !Number.isSafeInteger(source.version) || source.version < 1) throw invalid();
    const response = await responseFor(`${base}/documents/${encodeURIComponent(source.id)}/${kind === 'SCRIPT' ? 'script' : 'screenplay'}-export?format=${format}&expected_version=${source.version}`, 'GET', undefined, signal);
    const [mime, extension] = formats[format];
    const digest = response.headers.get('X-Creative-Document-Digest') || '', hash = response.headers.get('X-Content-SHA256') || '';
    if (response.headers.get('X-Creative-Document-Version') !== String(source.version) || !/^[a-f0-9]{64}$/.test(digest) || !/^[a-f0-9]{64}$/.test(hash)
        || response.headers.get('Content-Type')?.split(';')[0].trim() !== mime) throw invalid();
    const declared = response.headers.get('Content-Length');
    if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > 8_000_000)) throw invalid();
    const bytes = await response.arrayBuffer();
    if (!bytes.byteLength || bytes.byteLength > 8_000_000 || signal?.aborted) throw invalid();
    const actual = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(value => value.toString(16).padStart(2, '0')).join('');
    if (actual !== hash || signal?.aborted) throw invalid();
    return { blob: new Blob([bytes], { type: mime }), filename: `creative-${kind === 'SCRIPT' ? 'script' : 'screenplay'}-v${source.version}.${extension}`, documentVersion: source.version, documentDigest: digest, sha256: hash };
  }
  return {
    capabilities: (signal?: AbortSignal) => request<CreativeCapabilities>(`${base}/capabilities`, 'GET', undefined, signal),
    screenplayPresets: async (signal?: AbortSignal): Promise<ScreenplayPresetCatalog> => parseScreenplayPresets(await request<unknown>(`${base}/screenplay-presets`, 'GET', undefined, signal)),
    list: (signal?: AbortSignal) => request<{ items: CreativeDocument[] }>(`${base}/documents`, 'GET', undefined, signal),
    get: (id: string, signal?: AbortSignal) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'GET', undefined, signal),
    create: (body: CreativeInput) => request<CreativeDocument>(`${base}/documents`, 'POST', body),
    update: (id: string, version: number, body: CreativeInput) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'PUT', { ...body, expected_version: version }),
    derive: (source: CreativeDocument, mode: 'STORYBOARD' | 'PRODUCTION') => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/derive`, 'POST', { expected_version: source.version, mode }),
    restore: (source: CreativeDocument, restoreVersion: number) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/restore`, 'POST', { expected_version: source.version, restore_version: restoreVersion }),
    history: (id: string, signal?: AbortSignal) => request<CreativeHistory>(`${base}/documents/${encodeURIComponent(id)}/history`, 'GET', undefined, signal),
    export: (id: string) => request<{ document: CreativeDocument; document_digest: string; format: string; boundary: string }>(`${base}/documents/${encodeURIComponent(id)}/export`),
    screenplayExport: (source: CreativeDocument, format: ScreenplayExportFormat, signal?: AbortSignal) => verifiedTextExport(source, format, 'SCREENPLAY', signal),
    scriptExport: (source: CreativeDocument, format: ScriptExportFormat, signal?: AbortSignal) => verifiedTextExport(source, format, 'SCRIPT', signal),
    references: (signal?: AbortSignal) => request<CreativeReferences>(`${root}/creation-reference-data`, 'GET', undefined, signal),
    assets: (signal?: AbortSignal) => request<CreativeAsset[]>(`${root}/assets`, 'GET', undefined, signal),
    adaptations: (signal?: AbortSignal) => request<{ items: AdaptationProposal[] }>(`${base}/adaptation-proposals`, 'GET', undefined, signal),
    adaptationRoutes: (signal?: AbortSignal) => request<{ items: DirectorModelRoute[] }>(`${base}/adaptation-proposals/model-routes`, 'GET', undefined, signal),
    createAdaptation: (body: { chapter_id: string; expected_source_version: number; title: string; instruction: string; selected_text: string }) => request<AdaptationProposal>(`${base}/adaptation-proposals`, 'POST', body),
    previewAdaptation: (proposal: AdaptationProposal, routeId: string) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/preview`, 'POST', { expected_version: proposal.version, route_id: routeId, allow_synthetic: false }),
    dispatchAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/dispatch`, 'POST', { expected_version: proposal.version, reviewed_preview_digest: proposal.model_preview?.preview_digest }),
    refreshAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/refresh`, 'POST', { expected_version: proposal.version }),
    reviewAdaptation: (proposal: AdaptationProposal, title: string, output: AdaptationOutput) => request<{ proposal: AdaptationProposal; document: CreativeDocument }>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/review`, 'POST', { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title, output }),
    cancelAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/cancel`, 'POST', { expected_version: proposal.version }),
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
