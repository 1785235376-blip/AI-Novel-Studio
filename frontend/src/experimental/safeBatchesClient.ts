import type { ExperimentalClient } from './api';
export type BatchInput = { kind: 'PROOF' | 'EXPORT' | 'SYNTHETIC_MEDIA'; chapter_ids?: string[]; start?: number; end?: number | null; format?: string; brief_id?: string; expected_brief_version?: number; adapter_id?: string };
export type BatchProposal = { id: string; version: number; status: string; asset_id?: string; media: { width?: number; height?: number }; verification: string };
export type BatchRecord = { id: string; version: number; status: string; snapshot_digest: string; confirmed?: boolean; stale?: boolean; concurrency?: number; budget?: { state: string; known_cost_microusd: number }; items?: { index: number; kind: string; status: string; attempts: number; chapter_ids: string[]; source_versions_digest: string; source_versions?: Record<string, number>; configuration_summary?: Record<string, unknown>; known_cost_microusd: number; permission: string; error_code?: string; download_available?: boolean; format?: string; findings?: { id: string; quote: string; explanation: string; chapter_id: string; offset: number }[]; proposals?: BatchProposal[] }[] };
export type BatchCatalog = { chapters: { id: string; title: string; version: number }[]; briefs: { id: string; title: string; version: number; kind: string }[]; formats: string[]; unsupported: string[]; concurrency: number; known_cost_microusd: number };
const key = encodeURIComponent;
export function safeBatchesClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<BatchCatalog>('/safe-batches/catalog', signal),
    list: (signal?: AbortSignal) => client.get<{ items: BatchRecord[] }>('/safe-batches', signal),
    preflight: (items: BatchInput[], skip_satisfied: boolean) => client.post<BatchRecord>('/safe-batches/preflight', { items, skip_satisfied, concurrency: 1, budget_microusd: 0 }),
    confirm: (row: BatchRecord) => client.post<BatchRecord>(`/safe-batches/${key(row.id)}/confirm`, { expected_version: row.version, snapshot_digest: row.snapshot_digest, budget_microusd: 0, confirmed: true }),
    dispatch: (row: BatchRecord) => client.post<BatchRecord>(`/safe-batches/${key(row.id)}/dispatch-next`, { expected_version: row.version }),
    stop: (row: BatchRecord) => client.post<BatchRecord>(`/safe-batches/${key(row.id)}/stop`, { expected_version: row.version }),
    retry: (row: BatchRecord) => client.post<BatchRecord>(`/safe-batches/${key(row.id)}/retry-failed`, { expected_version: row.version }),
    download: (row: BatchRecord, index: number) => client.blob(`/safe-batches/${key(row.id)}/items/${index}/file`),
    preview: (row: BatchRecord, proposal: BatchProposal) => client.blob(`/safe-batches/${key(row.id)}/proposals/${key(proposal.id)}/preview`),
    approve: (row: BatchRecord, proposal: BatchProposal) => client.post<BatchRecord>(`/safe-batches/${key(row.id)}/approve-media`, { expected_version: row.version, snapshot_digest: row.snapshot_digest, confirmed: true, budget_microusd: 0, proposal_id: proposal.id, proposal_version: proposal.version }),
  };
}
