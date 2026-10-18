import { directorSceneScopeBody, checkedDirectorSceneScopeResult } from './directorSceneScope';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import { parseScreenplayPresets, type ScreenplayPresetCatalog } from './screenplayPresets';
import { createStoryboardClient } from './studioStoryboardClient';
import { createDirectorModelClient } from './directorModelClient';
import { ApiError, type CollaborationContext } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { isPackagedDesktopHost } from '../packagedHost';
import type { CreativeAsset, CreativeCapabilities, CreativeDocument, CreativeInput, CreativeReferences, CreativeShot, DirectorSceneNote, VisualTarget } from './types';

export const STORYBOARD_SOURCE_CONTRACT = 'STORYBOARD_SHOT_CONTEXT_V1' as const;
export type DirectorModelCapabilities = { independent_director_contract?: string; independent_screenplay_contract?: string; storyboard_source_contract?: string; storyboard_preview_suffix?: string; storyboard_dispatch_suffix?: string; token_fit_guaranteed?: boolean };
export type DirectorModelRoute = { route_id: string; provider_id: string; model_id: string; model_version?: string | null; synthetic: boolean; available: boolean; reasons: string[] };
export type DirectorModelPreview = { preview_digest: string; execution_available: boolean; model_called: false; allow_cloud_fallback: false; automatic_retry: false; timeout_seconds: number; max_output_bytes?: number; source_strategy: string; source_contract?: string; source_mode?: string; author?: { instruction?: string }; source_document_id?: string; source_version?: number; input_digest?: string; source_mapping?: { source_shot_id: string; note_id: string; scene_id: string; source_number: number }[]; token_fit_guaranteed?: boolean; request: Record<string, unknown>; broker: { chosen?: { provider_id?: string; model_id?: string; price?: { reserve_microusd?: number } } | null } };
export type DirectorSourceShot = { note_id: string; source_shot_id: string; source_number: number; scene_id: string; source_shot: CreativeShot; copied_fields: string[]; suggested_fields: string[]; retained_source_only_fields: string[] };
export type DirectorProposal = { unavailable_reason?: string; rule_checks?: { note_id: string; camera: { classification: Record<string, string> } }[]; id: string; version: number; status: string; source_document_id: string; source_version: number; source_digest?: string; document_id?: string | null; title: string; director_notes: DirectorSceneNote[]; visual_target?: VisualTarget | null; output_digest: string; provenance: { model_called?: boolean; source_mode?: 'SCREENPLAY' | 'STORYBOARD'; source_shots?: DirectorSourceShot[]; [key: string]: unknown }; model_preview?: DirectorModelPreview | null; model_execution?: { source_contract?: string; preview_digest?: string; job_id: string; status: string; model_called: boolean; receipt_state: string; usage_state: string; failure_code?: string } | null };
export type AdaptationSource = { ordinal: number; chapter_id: string; source_version: number; source_digest: string; selected_text: string; selection_digest: string; native_source_digest: string };
export type AdaptationChange = { source_ordinal?: number; id: string; kind: 'SCENE_SPLIT' | 'VISUALIZATION' | 'DIALOGUE' | 'OMISSION' | 'INFERENCE'; source_quote: string; scene_ids: string[]; note: string };
export type AdaptationOutput = { scenes: (import('./types').CreativeScene & { source_ordinal?: number })[]; report: { summary: string; changes: AdaptationChange[] } };
export type AdaptationAssetOutput = { contract: string; state: string; asset_id: string | null; version: number | null; sha256?: string; size?: number; reason?: string; execution_receipt?: Record<string, unknown> };
export type AdaptationProposal = { sources?: AdaptationSource[]; ordered_sources_digest?: string; source_mode?: string; asset_output?: AdaptationAssetOutput; id: string; version: number; status: string; title: string; chapter_id: string; source_version: number; source_digest: string; selection_digest: string; selected_text: string; output: AdaptationOutput | null; output_digest: string | null; model_preview: DirectorModelPreview | null; model_execution: DirectorProposal['model_execution']; provenance: Record<string, unknown> | null; document_id: string | null };
export type CreativeHistory = { document_id: string; current_version: number; items: CreativeDocument[]; snapshot_digests?: { version: number; digest: string }[] };
export type ScreenplayExportFormat = 'fountain' | 'docx' | 'markdown' | 'epub';
export type ScriptExportFormat = 'txt' | 'docx' | 'markdown';
export type ScreenplayDownload = { blob: Blob; filename: string; documentVersion: number; documentDigest: string; sha256: string };
export function creativeClient(novelId: string, context: CollaborationContext) {
  // Capture a complete origin. No request may borrow a later session or branch.
  const token = context.sessionToken || (!context.scope && !context.actor && !isPackagedDesktopHost() ? (context.localHostToken ?? useLocalHostSession.getState().token) : '');
  const branch = context.scope?.branchId;
  const directorScope = context.scope ? { ...context.scope } : undefined;
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
  async function verifiedTextExport(source: CreativeDocument, format: string, kind: 'SCREENPLAY' | 'SCRIPT' | 'DIRECTOR' | 'STORYBOARD', signal?: AbortSignal): Promise<ScreenplayDownload> {
    const sheet = kind === 'DIRECTOR' || kind === 'STORYBOARD';
    const exportName = kind === 'DIRECTOR' ? 'director-sheet' : kind === 'STORYBOARD' ? 'storyboard-sheet' : kind === 'SCRIPT' ? 'script' : 'screenplay';
    const formats: Record<string, [string, string]> = sheet ? { csv: ['text/csv', 'csv'] } : { ...(kind === 'SCREENPLAY' ? { fountain: ['text/x-fountain', 'fountain'] as [string, string], epub: ['application/epub+zip', 'epub'] as [string, string] } : { txt: ['text/plain', 'txt'] as [string, string] }), docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx'], markdown: ['text/markdown', 'md'] };
    const invalid = () => new ApiError({ status: 502, code: 'CREATIVE_EXPORT_RECEIPT_INVALID', message: '导出文件与当前版本不一致或校验失败。未下载文件，请重新核对已保存版本。' });
    if (source.mode !== kind || !formats[format] || !Number.isSafeInteger(source.version) || source.version < 1) throw invalid();
    const response = await responseFor(`${base}/documents/${encodeURIComponent(source.id)}/${exportName}-export?${sheet ? '' : `format=${format}&`}expected_version=${source.version}`, 'GET', undefined, signal);
    const [mime, extension] = formats[format];
    const digest = response.headers.get('X-Creative-Document-Digest') || '', hash = response.headers.get('X-Content-SHA256') || '';
    if (response.headers.get('X-Creative-Document-Version') !== String(source.version) || !/^[a-f0-9]{64}$/.test(digest) || !/^[a-f0-9]{64}$/.test(hash)
        || response.headers.get('Content-Type')?.split(';')[0].trim() !== mime) throw invalid();
    const maximum = sheet ? 2_000_000 : 8_000_000;
    const declared = response.headers.get('Content-Length');
    if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > maximum)) throw invalid();
    const bytes = await response.arrayBuffer();
    if (!bytes.byteLength || bytes.byteLength > maximum || signal?.aborted) throw invalid();
    const actual = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(value => value.toString(16).padStart(2, '0')).join('');
    if (actual !== hash || signal?.aborted) throw invalid();
    return { blob: new Blob([bytes], { type: mime }), filename: `creative-${exportName}-v${source.version}.${extension}`, documentVersion: source.version, documentDigest: digest, sha256: hash };
  }
  return {
    // Lazy and request-free. Reuse the already captured original transport;
    // constructing an ordinary legacy client does not activate new endpoints.
    independentDirector: (sourceMode: 'STORYBOARD' | 'SCREENPLAY' = 'STORYBOARD') => createDirectorModelClient(novelId, { json: request }, directorScope, sourceMode),
    ...createStoryboardClient(novelId, base, branch ?? null, request),
    capabilities: (signal?: AbortSignal) => request<CreativeCapabilities>(`${base}/capabilities`, 'GET', undefined, signal),
    screenplayPresets: async (signal?: AbortSignal): Promise<ScreenplayPresetCatalog> => parseScreenplayPresets(await request<unknown>(`${base}/screenplay-presets`, 'GET', undefined, signal)),
    list: (signal?: AbortSignal) => request<{ items: CreativeDocument[] }>(`${base}/documents`, 'GET', undefined, signal),
    get: (id: string, signal?: AbortSignal) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'GET', undefined, signal),
    create: (body: CreativeInput) => request<CreativeDocument>(`${base}/documents`, 'POST', body),
    update: (id: string, version: number, body: CreativeInput) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(id)}`, 'PUT', { ...body, expected_version: version }),
    derive: (source: CreativeDocument, mode: 'STORYBOARD' | 'PRODUCTION', shotPolicy?: 'DIRECTOR_NOTES') => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/derive`, 'POST', { expected_version: source.version, mode, ...(shotPolicy ? { shot_policy: shotPolicy } : {}) }),
    deriveDirectorScope: async (source: CreativeDocument, snapshot: PlanningSnapshot, responsibility: string, scenes: string[]) => {
      const body = directorSceneScopeBody(source, snapshot, responsibility, scenes);
      const result = await request<unknown>(`${base}/documents/${encodeURIComponent(source.id)}/derive`, 'POST', body);
      return checkedDirectorSceneScopeResult(result, source, snapshot, responsibility, scenes);
    },
    deriveScriptScreenplay: (source: CreativeDocument) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/derive`, 'POST', { expected_version: source.version, mode: 'SCREENPLAY', script_policy: 'TEXT_CHUNKS' }),
    restore: (source: CreativeDocument, restoreVersion: number) => request<CreativeDocument>(`${base}/documents/${encodeURIComponent(source.id)}/restore`, 'POST', { expected_version: source.version, restore_version: restoreVersion }),
    history: (id: string, signal?: AbortSignal) => request<CreativeHistory>(`${base}/documents/${encodeURIComponent(id)}/history`, 'GET', undefined, signal),
    export: (id: string) => request<{ document: CreativeDocument; document_digest: string; format: string; boundary: string }>(`${base}/documents/${encodeURIComponent(id)}/export`),
    screenplayExport: (source: CreativeDocument, format: ScreenplayExportFormat, signal?: AbortSignal) => verifiedTextExport(source, format, 'SCREENPLAY', signal),
    storyboardSheetExport: (source: CreativeDocument, signal?: AbortSignal) => verifiedTextExport(source, 'csv', 'STORYBOARD', signal),
    directorSheetExport: (source: CreativeDocument, signal?: AbortSignal) => verifiedTextExport(source, 'csv', 'DIRECTOR', signal),
    scriptExport: (source: CreativeDocument, format: ScriptExportFormat, signal?: AbortSignal) => verifiedTextExport(source, format, 'SCRIPT', signal),
    references: (signal?: AbortSignal) => request<CreativeReferences>(`${root}/creation-reference-data`, 'GET', undefined, signal),
    assets: (signal?: AbortSignal) => request<CreativeAsset[]>(`${root}/assets`, 'GET', undefined, signal),
    adaptations: (signal?: AbortSignal) => request<{ items: AdaptationProposal[] }>(`${base}/adaptation-proposals`, 'GET', undefined, signal),
    adaptationRoutes: (signal?: AbortSignal) => request<{ items: DirectorModelRoute[] }>(`${base}/adaptation-proposals/model-routes`, 'GET', undefined, signal),
    createAdaptation: (body: { title: string; instruction: string } & ({ chapter_id: string; expected_source_version: number; selected_text: string } | { sources: { chapter_id: string; expected_source_version: number }[] })) => request<AdaptationProposal>(`${base}/adaptation-proposals`, 'POST', body),
    previewAdaptation: (proposal: AdaptationProposal, routeId: string) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/preview`, 'POST', { expected_version: proposal.version, route_id: routeId, allow_synthetic: false }),
    dispatchAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/dispatch`, 'POST', { expected_version: proposal.version, reviewed_preview_digest: proposal.model_preview?.preview_digest }),
    refreshAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/refresh`, 'POST', { expected_version: proposal.version }),
    reviewAdaptation: (proposal: AdaptationProposal, title: string, output: AdaptationOutput) => request<{ proposal: AdaptationProposal; document: CreativeDocument }>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/review`, 'POST', { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title, output }),
    cancelAdaptation: (proposal: AdaptationProposal) => request<AdaptationProposal>(`${base}/adaptation-proposals/${encodeURIComponent(proposal.id)}/cancel`, 'POST', { expected_version: proposal.version }),
    modelCapabilities: (signal?: AbortSignal) => request<DirectorModelCapabilities>(`${base}/director-proposals/model-capabilities`, 'GET', undefined, signal),
    previewStoryboardModel: (proposal: DirectorProposal, routeId: string) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/storyboard-preview`, 'POST', { expected_version: proposal.version, route_id: routeId, source_contract: STORYBOARD_SOURCE_CONTRACT }),
    dispatchStoryboardModel: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/storyboard-dispatch`, 'POST', { expected_version: proposal.version, reviewed_preview_digest: proposal.model_preview?.preview_digest, source_contract: STORYBOARD_SOURCE_CONTRACT }),
    modelRoutes: (signal?: AbortSignal) => request<{ items: DirectorModelRoute[] }>(`${base}/director-proposals/model-routes`, 'GET', undefined, signal),
    previewModel: (proposal: DirectorProposal, routeId: string) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/preview`, 'POST', { expected_version: proposal.version, route_id: routeId }),
    dispatchModel: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/dispatch`, 'POST', { expected_version: proposal.version, reviewed_preview_digest: proposal.model_preview?.preview_digest }),
    refreshModel: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/refresh`, 'POST', { expected_version: proposal.version }),
    proposals: (signal?: AbortSignal) => request<{ items: DirectorProposal[] }>(`${base}/director-proposals`, 'GET', undefined, signal),
    proposal: (id: string, signal?: AbortSignal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(id)}`, 'GET', undefined, signal),
    propose: (source: CreativeDocument, visualTarget?: VisualTarget) => request<DirectorProposal>(`${base}/director-proposals`, 'POST', { source_document_id: source.id, expected_source_version: source.version, ...(visualTarget ? { visual_target: visualTarget } : {}) }),
    review: (proposal: DirectorProposal, title: string, notes: DirectorSceneNote[], visualTarget?: VisualTarget | null) => request<{ proposal: DirectorProposal; document: CreativeDocument }>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/review`, 'POST', { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title, director_notes: notes, ...(visualTarget === undefined ? {} : { visual_target: visualTarget }) }),
    cancelProposal: (proposal: DirectorProposal) => request<DirectorProposal>(`${base}/director-proposals/${encodeURIComponent(proposal.id)}/cancel`, 'POST', { expected_version: proposal.version }),
  };
}
export type CreativeClient = ReturnType<typeof creativeClient>;
export type DirectorProposalClient = Pick<CreativeClient, 'proposals' | 'proposal' | 'propose' | 'review' | 'cancelProposal' | 'get'
  | 'modelRoutes' | 'previewModel' | 'dispatchModel' | 'refreshModel'> & Partial<Pick<CreativeClient, 'modelCapabilities' | 'previewStoryboardModel' | 'dispatchStoryboardModel' | 'independentDirector' | 'export'>>;
