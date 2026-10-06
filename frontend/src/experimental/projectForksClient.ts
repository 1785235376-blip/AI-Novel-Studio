import type { ExperimentalClient } from './api';
export type ForkChoice = 'ORIGINAL' | 'FORK';
export type ForkNode = { type: string; text?: string; content?: ForkNode[]; attrs?: Record<string, unknown>; marks?: { type: string }[] };
export type ForkRecord = { id: string; version: number; status: string; title?: string; target_id: string; target_available?: boolean; preview_digest?: string; chapter_count?: number; active_merge?: string; fork_id?: string; kind?: string; error_code?: string; id_map?: { chapters: Record<string, string>; assets: Record<string, string> }; assets?: { id: string; license: string; sha256: string; version: number }[]; journal?: { index: number; kind: string; target: string; status: string; expected_version?: number; result_version?: number }[] };
export type ForkCatalog = { available: boolean; chapters: { id: string; title: string; version: number; asset_ids: string[]; supported?: boolean }[]; assets: { id: string; filename: string; version: number; sha256: string; available?: boolean }[]; limitations: string[] };
export type ForkSegment = { id: string; kind: string; reason?: string; base: ForkNode[]; ORIGINAL: ForkNode[]; FORK: ForkNode[]; choice?: ForkChoice };
export type ForkComparison = { fork_id: string; expected_version: number; preview_digest: string; can_apply: boolean; write_count: number; unresolved: number; blocked: { chapter_id: string; code: string }[]; chapters: { chapter_id: string; fork_chapter_id: string; title: string; original_version: number | null; fork_version: number | null; segments: ForkSegment[] }[] };
export type ForkCheckpointChapter = { id: string; title: string; version: number; archived: boolean; document: ForkNode };
export type ForkRecovery = { id: string; expected_version: number; status: string; preview_digest: string; can_restore: boolean; blocked: string[]; no_automatic_retry: true; observations: { chapter_id: string; checkpoint_version: number | null; current_version: number | null; state: string }[]; checkpoint: Record<string, ForkCheckpointChapter | null>; current: Record<string, ForkCheckpointChapter | null>; journal: ForkRecord['journal'] };
const key = encodeURIComponent;
export function projectForksClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<ForkCatalog>('/project-forks/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: ForkRecord[]; merges: ForkRecord[] }>('/project-forks/records', signal),
    preflight: (chapter_ids: string[], title: string, asset_permissions: { asset_id: string; version: number; sha256: string; license: string; allow_local_copy: true }[]) => client.post<ForkRecord>('/project-forks/preflight', { chapter_ids, title, asset_permissions }),
    create: (row: ForkRecord) => client.post<ForkRecord>(`/project-forks/${key(row.id)}/create`, { expected_version: row.version, preview_digest: row.preview_digest, confirmed: true }),
    compare: (row: ForkRecord, choices: Record<string, ForkChoice>) => client.post<ForkComparison>(`/project-forks/${key(row.id)}/compare`, { expected_version: row.version, choices }),
    apply: (row: ForkRecord, preview: ForkComparison, choices: Record<string, ForkChoice>) => client.post<ForkRecord>(`/project-forks/${key(row.id)}/apply`, { expected_version: row.version, preview_digest: preview.preview_digest, choices, confirmed: true }),
    recovery: (row: ForkRecord) => client.post<ForkRecovery>(`/project-forks/merges/${key(row.id)}/recovery`, { expected_version: row.version }),
    restore: (row: ForkRecord, preview: ForkRecovery) => client.post<ForkRecord>(`/project-forks/merges/${key(row.id)}/restore`, { expected_version: row.version, preview_digest: preview.preview_digest, confirmed: true }),
  };
}
