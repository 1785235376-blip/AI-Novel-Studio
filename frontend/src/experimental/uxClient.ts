import type { ExperimentalClient } from './api';
import type { WritingFocusPreferences } from './writingFocusClient';
export type WorkspaceAnchor = { offset: number; scroll: number };
export type WorkspaceView = { focus_active: boolean; references_visible: boolean };
export type WorkspaceRestore = { layout: WorkspaceLayout; view: WorkspaceView; focus_state: 'READY' | 'CHANGED' | 'UNAVAILABLE' | 'NOT_CAPTURED'; reference_recovery_required: boolean; focus_preferences?: WritingFocusPreferences };
export type WorkspaceNavigation = { kind: 'chapter' | 'feature' | 'generation'; task_authority?: string; parent_id?: string; record_kind?: 'volume' | 'scene' | 'character' | 'location' | 'timeline' | 'foreshadowing'; id: string; novel_id?: string; branch_id?: string | null; chapter_id?: string; signal?: AbortSignal; feature?: string; version?: number; anchor?: WorkspaceAnchor; stale?: boolean; coordinate?: 'EDITOR_TEXT_CODEPOINT'; workspace?: WorkspaceRestore };
export type WorkspaceLayout = { density: 'normal' | 'advanced'; section: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; show_failed_only: boolean; search_query: string; search_kind: '' | 'novel' | 'chapter' | 'volume' | 'scene' | 'character' | 'location' | 'timeline' | 'foreshadowing' | 'finding' | 'organization' | 'rule' | 'story_graph' | 'asset' | 'workflow' | 'review' | 'task'; search_current_chapter: boolean; search_scope: 'project' | 'authorized'; search_tag: string; search_recent_days: number; search_unresolved: boolean; search_fulltext: boolean; task_query: string };
export type ResumeItem = { id: string; version: number; chapter_id: string | null; chapter_version: number | null; chapter_title?: string; current_chapter_version?: number; anchor: WorkspaceAnchor; layout: WorkspaceLayout; view?: WorkspaceView; focus_state?: WorkspaceRestore['focus_state']; reference_recovery_required?: boolean; pending_tasks?: TaskItem[]; tasks_recovery_required?: boolean; tasks_capture_partial?: boolean; stopping_note: string; pinned_chapter_ids: string[]; recent_commands: string[]; guide_dismissed: boolean; layout_recovery_required?: boolean; updated_at: string };
export type ResumeResult = { item: ResumeItem | null; availability: 'EMPTY' | 'READY' | 'STALE' | 'UNAVAILABLE' };
export type SearchItem = { kind: 'novel' | 'chapter' | 'volume' | 'scene' | 'character' | 'location' | 'timeline' | 'foreshadowing' | 'finding' | 'organization' | 'rule' | 'story_graph' | 'asset' | 'workflow' | 'review' | 'task'; id: string; novel_id?: string; branch_id?: string | null; tags?: string[]; updated_at?: string; title: string; version?: number; revision: string; feature: string; offset: number; snippet: string; aliases: string[] };
export type SearchOptions = { q: string; kind: string; chapter_id?: string; scope: 'project' | 'authorized'; tag: string; recent_days: number; unresolved: boolean; fulltext: boolean; offset: number; request_id?: string };
export type SearchResult = { items: SearchItem[]; mode: string; truncated: boolean; branch_sources_available: boolean; match_count?: number; next_offset?: number | null; index_truncated?: boolean; suggestions?: string[]; source_rows_read?: number; updated_documents?: number; incremental_chapters?: boolean };
export type TaskItem = { source?: WorkspaceNavigation; id: string; authority: string; label: string; feature: string; status: string; stage_label: string; version?: number; progress: { completed: number; total: number; unit: string } | null; stale: boolean; error_code: string; history: { version?: number; status: string }[]; lifecycle: string; revision?: string; actions?: string[]; action_limits?: { cancel?: string | null; retry?: string; resume?: string; review?: string }; provider_id?: string | null; model_id?: string | null; route_state?: 'OBSERVED' | 'REQUESTED' | 'UNKNOWN' };
export type TaskResult = { items: TaskItem[]; unavailable: { authority: string; label: string; reason: string }[]; truncated: boolean };
export type DiagnosticOptions = { include_environment: boolean; include_task_states: boolean; include_error_codes: boolean };
export type DiagnosticResult = { schema: string; preview_digest: string; uploaded: false; sections: { environment?: { component: string; storage: string; scope_mode: string; diagnostic_contract: number }; task_states?: { authority: string; status: string; cost_state: string }[]; error_codes?: string[]; coverage?: { truncated: boolean; raw_logs_included: false } } };
export const defaultLayout: WorkspaceLayout = { density: 'normal', section: 'resume', show_failed_only: false, search_query: '', search_kind: '', search_current_chapter: false, search_scope: 'project', search_tag: '', search_recent_days: 0, search_unresolved: false, search_fulltext: false, task_query: '' };
export const defaultWorkspaceView: WorkspaceView = { focus_active: false, references_visible: true };
export function workspaceClient(client: ExperimentalClient) {
  const base = '/workspace';
  return {
    resume: (signal?: AbortSignal) => client.get<ResumeResult>(base + '/resume', signal),
    save: (body: unknown) => client.put<ResumeResult>(base + '/resume', body),
    reset: (version: number) => client.post<ResumeResult>(base + '/resume/reset-layout', { expected_version: version }),
    restore: (version: number, current = false) => client.post<WorkspaceNavigation>(base + '/resume/resolve', { expected_version: version, open_current: current }),
    history: (signal?: AbortSignal) => client.get<{ items: Pick<ResumeItem, 'version' | 'chapter_id' | 'chapter_version' | 'stopping_note' | 'updated_at'>[] }>(base + '/resume/history', signal),
    search: (query: string, kind: string, chapterId: string, signal?: AbortSignal) => client.get<SearchResult>(base + '/search?' + new URLSearchParams({ q: query, kind, ...(chapterId ? { chapter_id: chapterId } : {}) }), signal),
    searchScoped: (options: SearchOptions, signal?: AbortSignal) => client.get<SearchResult>(base + '/search?' + new URLSearchParams(Object.entries(options).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)])), signal),
    rebuild: (options?: SearchOptions) => client.post<SearchResult>(base + '/search/rebuild', options || {}),
    cancelSearch: (requestId: string) => client.post<{ state: string }>(base + '/search/cancel', { request_id: requestId }),
    resolve: (row: SearchItem, current = false) => client.post<WorkspaceNavigation>(base + '/search/resolve', { kind: row.kind, id: row.id, ...(row.novel_id ? { novel_id: row.novel_id, branch_id: row.branch_id || null } : {}), revision: row.revision, offset: row.offset, open_current: current }),
    tasks: (query: string, failed: boolean, signal?: AbortSignal) => client.get<TaskResult>(base + '/tasks?' + new URLSearchParams({ q: query, failed_only: String(failed) }), signal),
    cancelTask: (task: TaskItem) => client.post<{ item: TaskItem; cancellation_requested: boolean }>(base + '/tasks/' + encodeURIComponent(task.authority) + '/' + encodeURIComponent(task.id) + '/cancel', { expected_revision: task.revision }),
    preview: (options: DiagnosticOptions) => client.post<DiagnosticResult>(base + '/diagnostics/preview', options),
    export: (options: DiagnosticOptions, previewDigest: string) => client.post<DiagnosticResult>(base + '/diagnostics/export', { ...options, preview_digest: previewDigest }),
  };
}
