import type { ExperimentalClient } from './api';
export type StoryVariable = { name: string; type: 'bool' | 'int'; initial: boolean | number; minimum: number; maximum: number };
export type StoryChoice = { id: string; label: string; target: string; condition: string; assignments: Record<string, boolean | number> };
export type StoryNode = { node_id: string; node_version: number; title: string; dialogue: string; character_id: string | null; background_asset_id: string | null; music_asset_id: string | null; ending: string; choices: StoryChoice[] };
export type StorySpec = { title: string; graph_id: string; graph_version: number; entry_node_id: string; nodes: StoryNode[]; variables: StoryVariable[]; graph_record_ids: string[]; max_steps: number };
export type StoryIssue = { code: string; node_id?: string; choice_id?: string };
export type StoryAnalysis = { issues: StoryIssue[]; warnings: StoryIssue[]; endings: { node_id: string; ending: string; choices: string[] }[]; states_checked: number; analysis_complete: boolean; state_limit_reached: boolean; step_limit_reached: boolean; max_steps: number; can_review: boolean };
export type InteractiveStory = { id: string; version: number; status: 'DRAFT' | 'REVIEW' | 'APPROVED' | 'ARCHIVED'; spec?: StorySpec; stale: boolean; content_withheld: boolean; analysis?: StoryAnalysis };
export type StoryCatalog = { graphs: { id: string; version: number; title: string; nodes: Pick<StoryNode, 'node_id' | 'node_version' | 'title'>[]; truncated: boolean }[]; characters: { id: string; name: string }[]; graph_records: { id: string; title: string; version: number }[]; assets: { id: string; label: string; kind: string; version: number }[]; target_runtime: string };
export type StoryPlay = { node: Omit<StoryNode, 'choices'>; character_name?: string; choices: { id: string; label: string; enabled: boolean }[]; variables: Record<string, boolean | number>; steps: number; max_steps: number; status: 'PLAYING' | 'ENDING' | 'STEP_CAP_REACHED' | 'NO_EXIT'; path: string[] };
export type StoryRefreshPreview = { preview_digest: string; retained_nodes: number; changed_source_count: number };
export type StoryReviewPreview = { preview_digest: string; can_approve: boolean; analysis: StoryAnalysis };
export type StoryExportPreview = { preview_digest: string; can_export: boolean; losses: string[]; target_runtime: string; media_manifest: { asset_id: string; missing: boolean; packaged: boolean; reason: string }[]; analysis: StoryAnalysis };
export type StoryRevision = { version: number; status: string; spec: StorySpec; preview_digest: string };
export function interactiveStoryClient(client: ExperimentalClient) {
  const base = '/interactive-stories', path = (row: InteractiveStory) => `${base}/${encodeURIComponent(row.id)}`;
  return {
    history: (row: InteractiveStory) => client.post<{ items: StoryRevision[]; truncated: boolean }>(path(row) + '/history', { expected_version: row.version }),
    restoreRevision: (row: InteractiveStory, revision: StoryRevision) => client.post<InteractiveStory>(path(row) + '/restore-revision', { expected_version: row.version, restore_version: revision.version, preview_digest: revision.preview_digest }),
    catalog: (signal?: AbortSignal) => client.get<StoryCatalog>(base + '/catalog', signal),
    list: (signal?: AbortSignal) => client.get<{ items: InteractiveStory[]; truncated: boolean }>(base, signal),
    get: (row: InteractiveStory) => client.get<InteractiveStory>(path(row)),
    create: (spec: StorySpec) => client.post<InteractiveStory>(base, { spec }),
    save: (row: InteractiveStory, spec: StorySpec) => client.put<InteractiveStory>(path(row), { expected_version: row.version, spec }),
    reviewPreview: (row: InteractiveStory) => client.post<StoryReviewPreview>(path(row) + '/review-preview', { expected_version: row.version }),
    review: (row: InteractiveStory, action: string, preview?: StoryReviewPreview) => client.post<InteractiveStory>(path(row) + '/review', { expected_version: row.version, action, ...(preview ? { preview_digest: preview.preview_digest } : {}) }),
    play: (row: InteractiveStory, choices: string[]) => client.post<StoryPlay>(path(row) + '/preview', { expected_version: row.version, choices }),
    refreshPreview: (row: InteractiveStory) => client.post<StoryRefreshPreview>(path(row) + '/refresh-preview', { expected_version: row.version }),
    refresh: (row: InteractiveStory, preview: StoryRefreshPreview) => client.post<InteractiveStory>(path(row) + '/refresh', { expected_version: row.version, preview_digest: preview.preview_digest }),
    exportPreview: (row: InteractiveStory) => client.post<StoryExportPreview>(path(row) + '/export-preview', { expected_version: row.version }),
    export: (row: InteractiveStory, preview: StoryExportPreview) => client.post<{ filename: string; mime: string; content_base64: string; sha256: string; target_runtime: string }>(path(row) + '/export', { expected_version: row.version, preview_digest: preview.preview_digest }),
  };
}
