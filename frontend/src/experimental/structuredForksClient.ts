import type { ExperimentalClient } from './api';
import type { ForkChoice } from './projectForksClient';
export type StructuredSource = { key: string; kind: 'characters' | 'locations' | 'relationships'; record_id: string; title: string; source_digest: string; references: { field: string; key: string }[]; supported: boolean; reason?: string };
export type StructuredFork = { id: string; version: number; title?: string; status: string; target_id: string; target_available?: boolean; record_count: number; manuscript_fork?: { fork_id: string; expected_version: number; target_id: string; manuscript_source_digest: string } | null; preview_digest?: string; id_map?: Record<string, string>; provenance?: Record<string, unknown>; journal?: unknown[]; active_merge?: string; fork_id?: string; kind?: string };
export type StructuredComparison = { preview_digest: string; can_apply: boolean; write_count: number; unresolved: number; blocked: { key: string; field?: string; code: string }[]; records: { key: string; title: string; kind: string; original_digest: string; fork_digest: string; changes: { id: string; field: string; kind: string; reason: string; base: unknown; ORIGINAL: unknown; FORK: unknown }[] }[] };
export type StructuredRecovery = { preview_digest: string; can_restore: boolean; checkpoint: Record<string, unknown>; current: Record<string, unknown>; blocked: string[]; journal: unknown[]; no_automatic_retry: boolean };
const key = encodeURIComponent;
export function structuredForksClient(client: ExperimentalClient) {
  const base = '/project-forks/structured';
  const confirmation = (row: StructuredFork, preview_digest = row.preview_digest) => ({ expected_version: row.version, preview_digest, confirmed: true });
  return {
    catalog: (signal?: AbortSignal) => client.get<{ available: boolean; records: StructuredSource[]; truncated?: boolean }>(base + '/catalog', signal),
    records: (signal?: AbortSignal) => client.get<{ items: StructuredFork[]; merges: StructuredFork[] }>(base + '/records', signal),
    preflight: (title: string, selected: StructuredSource[], license: string, manuscript_fork?: { fork_id: string; expected_version: number }) => client.post<StructuredFork>(base + '/preflight', { title, ...(manuscript_fork ? { manuscript_fork } : {}), records: selected.map(row => ({ kind: row.kind, record_id: row.record_id, source_digest: row.source_digest, license, allow_local_copy: true })) }),
    create: (row: StructuredFork) => client.post<StructuredFork>(`${base}/${key(row.id)}/create`, confirmation(row)),
    compare: (row: StructuredFork, choices: Record<string, ForkChoice>) => client.post<StructuredComparison>(`${base}/${key(row.id)}/compare`, { expected_version: row.version, choices }),
    apply: (row: StructuredFork, preview: StructuredComparison, choices: Record<string, ForkChoice>) => client.post<StructuredFork>(`${base}/${key(row.id)}/apply`, { ...confirmation(row, preview.preview_digest), choices }),
    recovery: (row: StructuredFork) => client.post<StructuredRecovery>(`${base}/merges/${key(row.id)}/recovery`, { expected_version: row.version }),
    restore: (row: StructuredFork, preview: StructuredRecovery) => client.post<StructuredFork>(`${base}/merges/${key(row.id)}/restore`, confirmation(row, preview.preview_digest)),
  };
}
