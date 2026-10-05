import type { ExperimentalClient } from './api';
export type WorkspaceAnchor = { offset: number; scroll: number };
export type WorkspaceNavigation = { kind: 'chapter' | 'feature' | 'generation'; id: string; chapter_id?: string; signal?: AbortSignal; feature?: string; version?: number; anchor?: WorkspaceAnchor; stale?: boolean; coordinate?: 'EDITOR_TEXT_CODEPOINT' };
export type WorkspaceLayout = { density: 'normal' | 'advanced'; section: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; show_failed_only: boolean };
export type ResumeItem = { id: string; version: number; chapter_id: string | null; chapter_version: number | null; chapter_title?: string; current_chapter_version?: number; anchor: WorkspaceAnchor; layout: WorkspaceLayout; stopping_note: string; pinned_chapter_ids: string[]; recent_commands: string[]; guide_dismissed: boolean; layout_recovery_required?: boolean; updated_at: string };
export type ResumeResult = { item: ResumeItem | null; availability: 'EMPTY' | 'READY' | 'STALE' | 'UNAVAILABLE' };
export type SearchItem = { kind: 'chapter' | 'character' | 'location' | 'foreshadowing'; id: string; title: string; version?: number; revision: string; feature: string; offset: number; snippet: string; aliases: string[] };
export type SearchResult = { items: SearchItem[]; mode: string; truncated: boolean; branch_sources_available: boolean };
export type TaskItem = { source?: WorkspaceNavigation; id: string; authority: string; label: string; feature: string; status: string; stage_label: string; version?: number; progress: { completed: number; total: number; unit: string } | null; stale: boolean; error_code: string; history: { version?: number; status: string }[]; lifecycle: string };
export type TaskResult = { items: TaskItem[]; unavailable: { authority: string; label: string; reason: string }[]; truncated: boolean };
export type DiagnosticOptions = { include_environment: boolean; include_task_states: boolean; include_error_codes: boolean };
export type DiagnosticResult = { schema: string; preview_digest: string; uploaded: false; sections: { environment?: { component: string; storage: string; scope_mode: string; diagnostic_contract: number }; task_states?: { authority: string; status: string; cost_state: string }[]; error_codes?: string[]; coverage?: { truncated: boolean; raw_logs_included: false } } };
export const defaultLayout: WorkspaceLayout = { density: 'normal', section: 'resume', show_failed_only: false };
export function workspaceClient(client: ExperimentalClient) {
  const base = '/workspace';
  return {
    resume: (signal?: AbortSignal) => client.get<ResumeResult>(base + '/resume', signal),
    save: (body: unknown) => client.put<ResumeResult>(base + '/resume', body),
    reset: (version: number) => client.post<ResumeResult>(base + '/resume/reset-layout', { expected_version: version }),
    restore: (version: number, current = false) => client.post<WorkspaceNavigation>(base + '/resume/resolve', { expected_version: version, open_current: current }),
    history: (signal?: AbortSignal) => client.get<{ items: Pick<ResumeItem, 'version' | 'chapter_id' | 'chapter_version' | 'stopping_note' | 'updated_at'>[] }>(base + '/resume/history', signal),
    search: (query: string, kind: string, chapterId: string, signal?: AbortSignal) => client.get<SearchResult>(base + '/search?' + new URLSearchParams({ q: query, kind, ...(chapterId ? { chapter_id: chapterId } : {}) }), signal),
    rebuild: () => client.post<SearchResult>(base + '/search/rebuild', {}),
    resolve: (row: SearchItem, current = false) => client.post<WorkspaceNavigation>(base + '/search/resolve', { kind: row.kind, id: row.id, revision: row.revision, offset: row.offset, open_current: current }),
    tasks: (query: string, failed: boolean, signal?: AbortSignal) => client.get<TaskResult>(base + '/tasks?' + new URLSearchParams({ q: query, failed_only: String(failed) }), signal),
    preview: (options: DiagnosticOptions) => client.post<DiagnosticResult>(base + '/diagnostics/preview', options),
    export: (options: DiagnosticOptions, previewDigest: string) => client.post<DiagnosticResult>(base + '/diagnostics/export', { ...options, preview_digest: previewDigest }),
  };
}
