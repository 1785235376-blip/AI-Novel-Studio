import { ApiError, type CollaborationContext } from '../api';
import type {
  AppContextCapsule, DiagnosticCapsule, HandoffTarget, ProductDescriptor,
  TutorGuidance, VerifierResult,
} from '../../../contracts/local-interop/v1/protocol';

// Browser-to-host API only. The host owns the protocol transport, authorization,
// source snapshots and peer credentials. Never fetch a Tutor URL in the browser.
export type MetadataField = 'task' | 'error' | 'model' | 'runtime';
export type DiagnosticField = 'software_id' | 'software_version' | 'feature' | 'error_code' | 'task_state' | 'runtime' | 'model' | 'capability_state';
export type ContentKind = 'NONE' | 'SELECTION' | 'CHAPTER' | 'SPECIFIC_CONTEXT';
export type InteropStatus = {
  feature_enabled: boolean; enabled: boolean; acceptance_mode: boolean;
  product: ProductDescriptor; capabilities: string[]; disabled_capabilities: string[];
  desktop_status: 'LOCAL_REQUIRED';
};
export type InteropSession = {
  request_id: string; session_id: string; protocol_session_id: string; product: ProductDescriptor;
  capabilities: string[]; desktop_status: 'LOCAL_REQUIRED'; mode: 'MOCK_ONLY' | 'LOCAL_REFERENCE';
};
export type ContextPreview = { request_id: string; session_id: string; preview_id: string; capsule: AppContextCapsule; expires_at: string };
export type DiagnosticPreview = { request_id: string; session_id: string; preview_id: string; diagnostic: DiagnosticCapsule; capsule: AppContextCapsule; expires_at: string };
export type HostRoute = {
  action: 'OPEN_FEATURE' | 'OPEN_PROJECT' | 'OPEN_CHAPTER' | 'OPEN_TASK';
  feature?: string; project_id?: string; chapter_id?: string; task_id?: string;
  task_kind?: 'generation'; task_status?: string;
  chapter_version?: number;
  scope?: { workspace_id: string; project_id: string; storyline_id: string; branch_id: string };
};
export const metadataFields: MetadataField[] = ['task', 'error', 'model', 'runtime'];
export const diagnosticFields: DiagnosticField[] = ['software_id', 'software_version', 'feature', 'error_code', 'task_state', 'runtime', 'model', 'capability_state'];
export const newInteropRequestId = () => crypto.randomUUID();

export function interopErrorMessage(error: unknown): string {
  const code = error instanceof ApiError ? error.problem.code : 'TRANSPORT_ERROR';
  const labels: Record<string, string> = {
    PROTOCOL_INCOMPATIBLE: '协议版本不兼容，未建立连接。',
    PRODUCT_NOT_AVAILABLE: '未发现可用的本机 Tutor，Studio 可继续正常使用。',
    TUTOR_UNAVAILABLE: 'Tutor 当前不可用，Studio 可继续正常使用。',
    CAPABILITY_NOT_SUPPORTED: '对方没有协商此能力。',
    SESSION_REQUIRED: '请先连接已授权的本机 Tutor。',
    SESSION_REVOKED: '连接已撤销，请重新核对权限并连接。',
    PERMISSION_DENIED: '当前身份没有此操作权限。',
    CONTEXT_NOT_AUTHORIZED: '此来源尚未授权，未共享正文。',
    CONTEXT_STALE: '预览已过期或来源已变化，请重新预览。',
    SOURCE_CHANGED: '来源版本已变化，请重新预览。',
    HANDOFF_TARGET_NOT_FOUND: '目标不存在或不可访问，未导航。',
    VERIFIER_UNAVAILABLE: '当前没有可用的验证器。',
    MODEL_NOT_AVAILABLE: '模型当前不可用。',
    TIMEOUT: '等待超时，已取消本次请求。',
    CANCELLED: '本次请求已取消。',
    INVALID_MESSAGE: '协议数据无效，已停止本次操作。',
    TRANSPORT_ERROR: '本机连接未完成，请检查 Tutor 状态后重试。',
  };
  // Never render arbitrary exception/HTML/provider text or personal paths.
  return labels[code] ?? '操作未完成，请核对权限与本机服务后重试。';
}

export function interopClient(context: CollaborationContext) {
  const captured = { ...context, scope: context.scope ? { ...context.scope } : undefined };
  async function request<T>(path: string, body: unknown | undefined, signal?: AbortSignal): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (captured.sessionToken) headers['X-Session-Token'] = captured.sessionToken;
    if (captured.scope?.branchId) headers['X-Branch-Id'] = captured.scope.branchId;
    const response = await fetch(`/api/local-interop${path}`, {
      method: body === undefined ? 'GET' : 'POST', headers, signal,
      redirect: 'error', credentials: 'same-origin',
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) {
      let raw: Record<string, any> = {};
      try { raw = await response.json(); } catch { /* Fail closed without displaying arbitrary server data. */ }
      const error = raw.detail ?? raw.error ?? raw;
      const code = typeof error?.code === 'string' ? error.code : response.status === 401 ? 'SESSION_REQUIRED' : response.status === 403 ? 'PERMISSION_DENIED' : response.status === 404 ? 'PRODUCT_NOT_AVAILABLE' : 'TRANSPORT_ERROR';
      throw new ApiError({ status: response.status, code, message: 'Local Interop request failed' });
    }
    if (response.status === 204) return undefined as T;
    const value = await response.json();
    // The host may revoke authority after HTTP headers have already started.
    // A typed error frame replaces the body; 200 is never sufficient authority.
    if (value?.protocol_name === 'PoemSeed Local Interop' && typeof value.code === 'string')
      throw new ApiError({ status: response.status, code: value.code, message: 'Local Interop request rejected' });
    return value as T;
  }
  return {
    status: (signal?: AbortSignal) => request<InteropStatus>('/status', undefined, signal),
    settings: (enabled: boolean, request_id: string, signal?: AbortSignal) => request<InteropStatus>('/settings', { enabled, request_id }, signal),
    connect: (body: { request_id: string; endpoint: string; project_id: string; scope?: HostRoute['scope']; module: string; surface: string; chapter_id?: string; task_id?: string }, signal?: AbortSignal) => request<InteropSession>('/connect', body, signal),
    sources: (session_id: string, signal?: AbortSignal) => request<{ session_id: string; items: ContextSource[] }>(`/context/sources?session_id=${encodeURIComponent(session_id)}`, undefined, signal),
    preview: (body: { request_id: string; session_id: string; chapter_id?: string; expected_chapter_version?: number; content_kind: ContentKind; selection_start?: number; selection_end?: number; context_ids?: string[]; metadata_fields: MetadataField[] }, signal?: AbortSignal) => request<ContextPreview>('/context/preview', body, signal),
    ask: (session_id: string, preview_id: string, request_id: string, signal?: AbortSignal) => request<{ request_id: string; session_id: string; guidance: TutorGuidance }>('/ask', { session_id, preview_id, request_id, confirmed: true }, signal),
    diagnosticPreview: (session_id: string, fields: DiagnosticField[], request_id: string, signal?: AbortSignal) => request<DiagnosticPreview>('/diagnostics/preview', { session_id, fields, request_id }, signal),
    diagnosticShare: (session_id: string, preview_id: string, request_id: string, signal?: AbortSignal) => request<{ request_id: string; session_id: string; guidance: TutorGuidance }>('/diagnostics/share', { session_id, preview_id, request_id, confirmed: true }, signal),
    verify: (session_id: string, guidance_id: string, request_id: string, signal?: AbortSignal) => request<{ request_id: string; session_id: string; result: VerifierResult }>('/verify', { session_id, guidance_id, request_id }, signal),
    handoff: (session_id: string, handoff: HandoffTarget, request_id: string, signal?: AbortSignal) => request<{ request_id: string; session_id: string; route: HostRoute }>('/handoff', { session_id, handoff, request_id, explicit_click: true }, signal),
    cancel: (request_id: string, session_id?: string) => request('/cancel', { request_id, ...(session_id ? { session_id } : {}) }),
    disconnect: (session_id: string) => request('/disconnect', { session_id, request_id: newInteropRequestId() }),
  };
}
export type InteropClient = ReturnType<typeof interopClient>;

export type ContextSource = { id: string; label: string; version: number };
