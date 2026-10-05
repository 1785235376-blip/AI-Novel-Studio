import { ApiError, type CollaborationContext } from '../api';

export type AuthorPreviewOptions = {
  enabled: boolean; chapterId: string; chapterVersion: number; source: string;
  profile: 'LOCAL_ONLY' | 'HYBRID' | 'QUALITY'; styleProfileId?: string; plotPlanId?: string;
  context: CollaborationContext; saved: boolean;
  characterId?: string;
  onExitCharacter?: () => void;
};
export type AuthorPreviewReceipt = { previewDigest: string; chapterVersion: number; requestKey: string; requestId: string };
export type AuthorRequestBody = {
  novel_id: string; chapter_id: string; chapter_version: number; operation: string;
  instruction: string; style: string; profile: string; provider_id: string; model_id: string;
  source: string; selected_text: string; style_profile_id?: string; plot_plan_id?: string; preview_digest?: string; generation_request_id?: string;
  character_id?: string; world_time?: number; calendar?: string;
  revision_selection?: { chapter_id: string; chapter_version: number; from_pos: number; to_pos: number; text: string };
  revision_selection_digest?: string;
};
export type AuthorPreview = {
  contract: string; preview_digest: string; chapter_id: string; chapter_version: number;
  target: 'local' | 'cloud'; provider_id: string; model_id: string; prompt_characters: number;
  source_characters: number; source_strategy: string; truncation: string; token_count: null;
  context_sections: { name: string; characters: number; included_in_adapter_request: boolean }[];
  privacy_omissions: { reason: string }[]; creation_records: { id: string; version: number }[];
  request: { prompt: string; context: Record<string, unknown>; parameters: Record<string, unknown>; system_instruction: string | null };
};
export async function authorContextRequest<T>(novelId: string, action: 'preview' | 'generate', body: AuthorRequestBody, context: CollaborationContext, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (action === 'generate') headers['Idempotency-Key'] = body.generation_request_id || globalThis.crypto.randomUUID();
  if (context.sessionToken) headers['X-Session-Token'] = context.sessionToken;
  if (context.scope?.branchId) headers['X-Branch-Id'] = context.scope.branchId;
  const response = await fetch(`/api/novels/${encodeURIComponent(novelId)}/experimental/author-context/${action}`, { method: 'POST', headers, body: JSON.stringify(body), signal });
  if (!response.ok) {
    let value: any = {}; try { value = await response.json(); } catch { /* No raw HTML or server error text. */ }
    const code = typeof value?.detail?.code === 'string' ? value.detail.code : 'AUTHOR_PREVIEW_FAILED';
    throw new ApiError({ status: response.status, code, message: response.status === 401 || response.status === 403 ? '没有读取或生成权限，请重新确认会话与项目。' : response.status === 409 ? '来源、选区、隐私或预检已改变，请保存正文并重新检查。' : response.status === 404 ? '真实请求预检未启用或当前章节不可用。' : '预检未完成，请核对输入后重试。' });
  }
  return response.json();
}

export function authorRequestKey(body: AuthorRequestBody, context: CollaborationContext) {
  return JSON.stringify([body, context.sessionToken, context.scope, context.actor]);
}
