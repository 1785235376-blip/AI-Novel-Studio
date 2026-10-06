import { ApiError, type CollaborationContext } from '../api';

export type AuthorPreviewOptions = {
  enabled: boolean; chapterId: string; chapterVersion: number; source: string;
  profile: 'LOCAL_ONLY' | 'HYBRID' | 'QUALITY'; styleProfileId?: string; plotPlanId?: string;
  context: CollaborationContext; saved: boolean;
  characterId?: string;
  sceneId?: string;
  onExitCharacter?: () => void;
};
export type AuthorSourceControl = { key: string; source_digest: string; include: boolean };
export type AddedAuthorSource = { kind: 'CHAPTER' | 'CANON' | 'STORY_GRAPH' | 'RESEARCH'; id: string; version?: number | null; source_digest: string; citation?: { source_id: string; source_version: number; paragraph: number; quote_sha256: string; page?: number | null }; include: boolean; max_characters: number };
export type AddedSourceItem = AddedAuthorSource & { key: string; label: string; privacy_level: string; preview: string; characters: number; preview_truncated: boolean };
export type NativeSourceCatalog = { items: AddedSourceItem[]; truncated: boolean; branch_sources_available: boolean };
export type SourceCatalogRequest = { kind: AddedAuthorSource['kind']; query: string; provider_id: string };
export type AuthorSourceManifest = { added_items?: (AddedAuthorSource & { key: string; label: string; included: boolean; characters: number; truncated: boolean; truncation_reason: string | null })[]; items: { key: string; kind: string; label: string; version: number | null; version_state: string; source_digest: string; included: boolean; pinned: boolean }[]; dependent_context_omitted: boolean; omission_reason: string | null; unidentified_sources_require_bundle_removal: boolean; primary_manuscript_and_author_input_separate: boolean; granularity: string };
export type AuthorRequestScope = { added_sources?: AddedAuthorSource[]; source_items?: AuthorSourceControl[]; source_mode: 'AUTO' | 'SELECTION_ONLY' | 'NONE'; include_automatic_context: boolean; include_style_reference: boolean; include_plan_reference: boolean };
export const defaultAuthorRequestScope: AuthorRequestScope = { source_mode: 'AUTO', include_automatic_context: true, include_style_reference: true, include_plan_reference: true };
export type AuthorPreviewReceipt = { requestBody: AuthorRequestBody; previewDigest: string; chapterVersion: number; requestKey: string; requestId: string };
export type AuthorRequestBody = {
  novel_id: string; chapter_id: string; chapter_version: number; operation: string;
  instruction: string; style: string; profile: string; provider_id: string; model_id: string;
  request_scope?: AuthorRequestScope;
  source: string; selected_text: string; style_profile_id?: string; plot_plan_id?: string; preview_digest?: string; generation_request_id?: string;
  character_id?: string; scene_id?: string; world_time?: number; calendar?: string;
  revision_selection?: { chapter_id: string; chapter_version: number; from_pos: number; to_pos: number; text: string };
  revision_selection_digest?: string;
};
export type AuthorVariantsInput = { author: AuthorRequestBody; count: number; group_id: string; receipts?: { variant_index: number; preview_digest: string }[] };
export type AuthorVariantsReceipt = { requestBody: AuthorRequestBody; requestKey: string; chapterVersion: number; batch: AuthorVariantsInput; jobIds: string[] };
export type AuthorVariantsPreview = { group_id: string; count: number; variants: (AuthorPreview & { variant: { job_id: string; variant_index: number } })[] };
export type AuthorVariantsResult = { group_id: string; count: number; batch_state: string; variants: { job_id: string; variant_index: number; base_chapter_version: number; status: string; receipt_state: string }[] };
export const authorVariantsKey = (body: AuthorRequestBody, count: number, context: CollaborationContext) => JSON.stringify([authorRequestKey(body, context), count]);
export type AuthorPreview = {
  variant_policy?: Record<string, unknown>;
  variant?: { job_id: string; variant_index: number; group_id: string; count: number };
  scope_changes_supported?: boolean; request_scope?: AuthorRequestScope; source_manifest?: AuthorSourceManifest | null;
  scope_effects?: { automatic_context_included: boolean; references_omitted_for_source_isolation: boolean; granularity: string; reason: string | null };
  contract: string; preview_digest: string; chapter_id: string; chapter_version: number;
  target: 'local' | 'cloud'; provider_id: string; model_id: string; prompt_characters: number;
  source_characters: number; source_strategy: string; truncation: string; token_count: null;
  context_sections: { name: string; characters: number; included_in_adapter_request: boolean }[];
  privacy_omissions: { reason: string }[]; creation_records: { id: string; version: number }[];
  request: { prompt: string; context: Record<string, unknown>; parameters: Record<string, unknown>; system_instruction: string | null };
};
export async function authorContextRequest<T>(novelId: string, action: 'preview' | 'generate', body: AuthorRequestBody, context: CollaborationContext, signal?: AbortSignal): Promise<T> {
  return sendAuthorRequest(novelId, action, body, context, signal);
}
export async function authorContextVariants<T>(novelId: string, action: 'preview-variants' | 'generate-variants', body: AuthorVariantsInput, context: CollaborationContext, signal?: AbortSignal): Promise<T> {
  return sendAuthorRequest(novelId, action, body, context, signal);
}
export async function authorContextSources(novelId: string, body: SourceCatalogRequest, context: CollaborationContext, signal?: AbortSignal) {
  return sendAuthorRequest<NativeSourceCatalog>(novelId, 'sources', body, context, signal);
}
async function sendAuthorRequest<T>(novelId: string, action: string, body: AuthorRequestBody | AuthorVariantsInput | SourceCatalogRequest, context: CollaborationContext, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (action === 'generate') headers['Idempotency-Key'] = (body as AuthorRequestBody).generation_request_id || globalThis.crypto.randomUUID();
  if (context.sessionToken) headers['X-Session-Token'] = context.sessionToken;
  if (context.scope?.branchId) headers['X-Branch-Id'] = context.scope.branchId;
  const response = await fetch(`/api/novels/${encodeURIComponent(novelId)}/experimental/author-context/${action}`, { method: 'POST', headers, body: JSON.stringify(body), signal });
  if (!response.ok) {
    let value: any = {}; try { value = await response.json(); } catch { /* No raw HTML or server error text. */ }
    const code = typeof value?.detail?.code === 'string' ? value.detail.code : 'AUTHOR_PREVIEW_FAILED';
    throw new ApiError({ status: response.status, code, message: ['AUTHOR_VARIANT_POLICY_GUARD_UNAVAILABLE', 'AUTHOR_VARIANT_POLICY_UNAVAILABLE', 'AUTHOR_VARIANTS_BROKER_POLICY_REQUIRES_RESERVATION', 'AUTHOR_VARIANTS_LOCAL_ONLY_BUDGET_REQUIRED'].includes(code) ? '逐方案预检需要本地模型且没有适用的调度预算策略。云端或已有调度策略的批次尚需组预算预占；请使用调度面板逐次预占，不能直接绕过预算。' : ['GENERATION_FEATURE_DISABLED', 'AUTHOR_ADDED_SOURCE_UNAVAILABLE_OR_CHANGED'].includes(code) ? '原始来源、权限、隐私或功能已变化，请重新读取来源并预检。' : code === 'AUTHOR_SELECTION_REQUIRED' ? '此范围需要已保存的选区，请选中文字后重新检查。' : response.status === 401 || response.status === 403 ? '没有读取或生成权限，请重新确认会话与项目。' : response.status === 409 ? '来源、选区、隐私或预检已改变，请保存正文并重新检查。' : response.status === 404 ? '真实请求预检未启用或当前章节不可用。' : '预检未完成，请核对输入后重试。' });
  }
  return response.json();
}

export function authorRequestKey(body: AuthorRequestBody, context: CollaborationContext) {
  const stable = (value: unknown): unknown => Array.isArray(value) ? value.map(stable) : value && typeof value === 'object'
    ? Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined).sort(([a], [b]) => a.localeCompare(b)).map(([name, item]) => [name, stable(item)])) : value;
  return JSON.stringify(stable([body, context.sessionToken, context.scope, context.actor]));
}
