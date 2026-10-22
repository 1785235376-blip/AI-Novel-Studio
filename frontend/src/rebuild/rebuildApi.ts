// [HERMIA-FE-20261022 REBUILD] Thin real-endpoint client for the prototype-style rebuild.
// Every function hits the real backend path; failures surface as ApiError (no fake success).
import { call, ApiError } from '../api';
const e = encodeURIComponent;

export type NovelExport = { format: string; filename: string; content: string };
export type ExportJob = { id: string; novel_id: string; format: string; status: string; progress?: number; progress_message?: string; error?: unknown; created_at?: string };
export type CredentialStatus = { provider: string; configured: boolean; backend?: string; persistent?: boolean; degraded?: boolean; degraded_reason?: string | null };
export type ModelCenterHealth = { status: string; models: number; ready_models: number; runtimes: number; mutation_authorization?: { can_mutate: boolean; mutation_auth_mode?: string } };
export type ResearchRecord = { id: string; title: string; source_type: string; author?: string; url?: string; excerpt?: string; notes?: string; tags?: string[]; updated_at?: string };
export type ResearchList = { items: ResearchRecord[]; total: number; external_fetch?: boolean; storage?: string };
export type MediaTasks = { novel_id: string; audiobook: { id: string; status: string; chapter_id?: string }[]; motion: { id: string; status: string }[] };
export type AssetTaskStats = { total: number; by_status: Record<string, number>; latest_at: string | null };
export type WorkspaceTasks = { items: { id: string; authority: string; title?: string; status: string }[] };
export type TrashList = { items: { id: string; name?: string; title?: string; kind?: string; deleted_at?: string }[]; total: number; recoverable?: boolean };

export const CREDENTIAL_PROVIDERS = ['openai', 'claude', 'gemini', 'deepseek', 'aliyun-bailian', 'siliconflow', 'kling', 'runway', 'minimax', 'seedance'] as const;
export const NOVEL_EXPORT_FORMATS = [{ id: 'txt', label: '纯文本 TXT' }, { id: 'markdown', label: 'Markdown' }, { id: 'json', label: '工程 JSON' }] as const;
export const RENDER_EXPORT_FORMATS = [{ id: 'docx', label: 'Word' }, { id: 'pdf', label: 'PDF' }, { id: 'epub', label: 'EPUB' }, { id: 'screenplay', label: '剧本' }, { id: 'shot-list', label: '分镜表' }] as const;

export const rb = {
  novelExport: (nid: string, format: string) => call<NovelExport>(`/api/novels/${e(nid)}/export?format=${e(format)}`),
  listExports: (nid: string) => call<{ items: ExportJob[] }>(`/api/exports?novel_id=${e(nid)}&limit=20`),
  createExport: (nid: string, format: string) => call<ExportJob>(`/api/exports?novel_id=${e(nid)}`, { method: 'POST', body: JSON.stringify({ format }) }),
  exportDownloadUrl: (id: string) => `/api/exports/${e(id)}/download`,
  credential: (p: string) => call<CredentialStatus>(`/api/credentials/${e(p)}`),
  setCredential: (p: string, credential: string) => call<CredentialStatus>(`/api/credentials/${e(p)}`, { method: 'PUT', body: JSON.stringify({ provider: p, credential }) }),
  deleteCredential: (p: string) => call<unknown>(`/api/credentials/${e(p)}`, { method: 'DELETE' }),
  testCredential: (p: string) => call<{ provider: string; configured: boolean; reachable: boolean }>(`/api/credentials/${e(p)}/test`, { method: 'POST' }),
  modelHealth: () => call<ModelCenterHealth>('/api/model-center/health'),
  research: (nid: string) => call<ResearchList>(`/api/novels/${e(nid)}/research`),
  addResearch: (nid: string, body: { title: string; source_type?: string; url?: string; notes?: string }) => call<ResearchRecord>(`/api/novels/${e(nid)}/research`, { method: 'POST', body: JSON.stringify(body) }),
  deleteResearch: (nid: string, id: string) => call<unknown>(`/api/novels/${e(nid)}/research/${e(id)}`, { method: 'DELETE' }),
  knowledgeReview: (nid: string) => call<{ id?: string; status?: string }>(`/api/novels/${e(nid)}/knowledge-base/review`, { method: 'POST' }),
  mediaTasks: (nid: string) => call<MediaTasks>(`/api/novels/${e(nid)}/media-tasks`),
  assetTaskStats: (nid: string) => call<AssetTaskStats>(`/api/novels/${e(nid)}/asset-tasks/stats`),
  workspaceTasks: (nid: string) => call<WorkspaceTasks>(`/api/novels/${e(nid)}/experimental/workspace/tasks`),
  assetTrash: (nid: string) => call<TrashList>(`/api/novels/${e(nid)}/asset-trash`),
};

/** Honest error label: never claims success; maps feature-off to a plain sentence. */
export function rbError(err: unknown): string {
  if (err instanceof ApiError) {
    const code = String(err.problem.code || '');
    if (code === 'EXPERIMENTAL_FEATURE_DISABLED') return '后端未开启此功能（实验开关关闭）';
    if (err.status === 404) return '后端没有这个接口（404）';
    if (err.status === 401 || code === 'SESSION_REQUIRED') return '需要登录会话';
    if (err.status === 403) return '没有权限';
    return `后端返回错误 ${err.status}${code && code !== 'HTTP_ERROR' ? ` · ${code}` : ''}`;
  }
  return '后端不可用（无法连接）';
}
