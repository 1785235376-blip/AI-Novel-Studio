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
export type StoryRevision = { version: number; status: string; spec: StorySpec; preview_digest: string };
export type StoryCapability = { supported: boolean; lossy: boolean; note: string };
export type StoryEngineRequirement = { name: string; minimum_version: string; executables: string[]; version_args: string[]; env_override?: string | null; search_hints?: string[]; gui: boolean; note?: string };
export type StoryEngineProbe = { status: 'READY' | 'NOT_INSTALLED' | 'UNSUPPORTED_VERSION' | 'PROBE_FAILED' | 'NOT_REQUIRED'; detected: boolean; executable: string | null; version: string | null; version_ok?: boolean; detail?: string; declared?: { name: string; minimum_version: string; gui: boolean } | null };
export type StoryCompatibilityIssue = { code: string; node_id?: string | null; choice_id?: string | null; character_id?: string | null; detail?: string };
export type StoryTargetCompatibility = { target_id: string; can_export: boolean; capabilities: Record<string, StoryCapability>; losses: string[]; issues: StoryCompatibilityIssue[]; notes: string[] };
export type StoryTargetDescriptor = { target_id: string; display_name: string; kind: 'RUNNABLE_PROJECT' | 'DATA_ONLY_ADAPTER' | 'LEGACY_FRAGMENT'; format_version: string; adapter_revision: number; engine: StoryEngineRequirement | null; capabilities: Record<string, StoryCapability>; losses: string[]; runtime_requirements: string[]; launch_instructions: string; integration_notes: string[]; evidence: Record<string, string> };
export type StoryExportTarget = StoryTargetDescriptor & { compatibility: StoryTargetCompatibility; engine_probe: StoryEngineProbe; export_ready: boolean; single_export_ready: boolean; runtime_claim: string };
export type StoryMediaManifestRow = { asset_id: string; missing: boolean; packaged: boolean; reason: string; kind?: string; version?: number; sha256?: string };
export type StoryExportTargets = { schema: string; contract_schema: string; contract_version: number; contract: Record<string, unknown>; adaptation: { id: string; version: number; status: string }; story: { title: string; entry_node_id: string; max_steps: number; nodes: number; variables: number; endings: number; spec_digest: string; source_digest: string }; witness: { node_id: string; ending: string; choices: string[] }[]; analysis: { can_review: boolean; analysis_complete: boolean; issues: StoryIssue[]; warnings: StoryIssue[]; states_checked: number }; targets: StoryExportTarget[]; media_manifest: StoryMediaManifestRow[]; can_export_any: boolean; target_runtime_policy: string; model_called: boolean };
export type StoryExportPreview = { ink_target?: { compatibility: 'SUPPORTED_SUBSET' | 'UNSUPPORTED'; version: string; artifact_runtime: string }; ink_issues?: { code: string; node_id?: string; choice_id?: string; character_id?: string }[]; preview_digest: string; can_export: boolean; losses: string[]; target_runtime: string; media_manifest: StoryMediaManifestRow[]; analysis: StoryAnalysis; targets?: StoryExportTarget[]; target_id?: string; selected_target?: StoryExportTarget };
export type StoryExportResult = { filename: string; mime: string; content_base64: string; sha256: string; target_runtime: string; target_id?: string; target_format_version?: string; adapter_revision?: number; file_count?: number; files_digest?: string; manifest?: Record<string, unknown>; losses?: string[]; capabilities?: Record<string, StoryCapability>; evidence?: Record<string, string>; runtime_claim?: string; published?: boolean };
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
    targets: (row: InteractiveStory) => client.post<StoryExportTargets>(path(row) + '/export-targets', { expected_version: row.version }),
    exportPreview: (row: InteractiveStory, targetId?: string) => client.post<StoryExportPreview>(path(row) + '/export-preview', { expected_version: row.version, ...(targetId ? { target_id: targetId } : {}) }),
    export: (row: InteractiveStory, preview: StoryExportPreview, targetId?: string) => client.post<StoryExportResult>(path(row) + '/export', { expected_version: row.version, preview_digest: preview.preview_digest, ...(targetId ? { target_id: targetId } : {}) }),
  };
}
