import { ApiError, type CollaborationContext, type WorkspaceNavigationPath } from '../api';

export type FirstUseReceipt = {
  id: string; version: number; stage: 'CREATING_PROJECT' | 'PROJECT_READY' | 'CREATING_CHAPTER' | 'CHAPTER_CREATED' | 'CHAPTER_READY' | 'SAVING_SAMPLE' | 'READY' | 'SOURCE_CHANGED';
  project_id: string | null; chapter_id: string | null; chapter_version?: number; seed_version?: number;
  path: WorkspaceNavigationPath | null; synthetic: true; sample_version: number;
  availability: 'AVAILABLE' | 'UNAVAILABLE' | 'UNKNOWN' | 'NOT_CREATED'; can_open?: boolean; can_recover?: boolean;
};
export type FirstUseResult = { item: FirstUseReceipt | null; model_calls: 0 };

export function firstUseClient(context: CollaborationContext, workspaceId?: string) {
  const token = context.sessionToken;
  const workspace = workspaceId || context.scope?.workspaceId;
  const query = workspace ? `?workspace_id=${encodeURIComponent(workspace)}` : '';
  async function request(method: 'GET' | 'POST', path = '', signal?: AbortSignal): Promise<FirstUseResult> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['X-Session-Token'] = token;
    const response = await fetch(`/api/experimental/first-use/sample${path}${method === 'GET' ? query : ''}`, {
      method, headers, signal, ...(method === 'POST' ? { body: JSON.stringify({ workspace_id: workspace || null }) } : {}),
    });
    if (!response.ok) {
      throw new ApiError({ status: response.status, code: 'FIRST_USE_REQUEST_FAILED', message:
        response.status === 401 ? '会话已失效，请重新打开应用。' :
        response.status === 403 ? '当前身份没有此操作权限。已创建的内容不会被删除。' :
        response.status === 404 ? '练习入口未启用，或原作品已不可用。' :
        response.status === 409 ? '另一个请求已更新练习记录，请先核对当前状态。' : '练习操作未确认。请先核对状态，避免重复创建。' });
    }
    return response.json();
  }
  return { read: (signal?: AbortSignal) => request('GET', '', signal), start: () => request('POST'), recover: () => request('POST', '/recover') };
}
