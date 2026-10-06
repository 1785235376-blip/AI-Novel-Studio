import type { ExperimentalClient } from './api';
import { segment } from './api';
export type ImpactSource = { kind: 'CHAPTER' | 'CHARACTER' | 'WORLD_RECORD' | 'ASSET'; id: string; label: string; binding: unknown };
export type ImpactNode = { key: string; kind: string; id: string; label: string; version: number; status: string; feature?: string; stale: boolean; locked: boolean; lock_version: number; refresh_candidate: boolean; refresh_reason: string | null; knowledge_category?: string; evidence: { key: string; label: string; state: string; recorded_version?: number | null; current_version?: number | null }[] };
export type ImpactView = { source: ImpactSource; items: ImpactNode[]; coverage: string; inferred: unknown[]; unrecorded_dependencies: 'UNKNOWN'; automatic_regeneration: false };
export type ImpactPreflight = { id: string; version: number; preflight_digest: string; ready: boolean; source_snapshot?: ImpactSource; maximum_candidates: number; items: { key: string; label: string; blockers: string[] }[]; cost: { state: string; currency: string; estimate_microusd: number | null }; verification: string };
export type ImpactRefresh = { id: string; version: number; node_key: string; task_id: string; task_version: number; status: string; source_current: boolean; outputs: { id: string; status: string }[]; recovery: string | null };
export function changeImpactClient(client: ExperimentalClient) {
  return {
    sources: (signal?: AbortSignal) => client.get<{ items: ImpactSource[] }>('/change-impact/sources', signal),
    query: (source: ImpactSource) => client.post<ImpactView>('/change-impact/query', { source: { kind: source.kind, id: source.id } }),
    lock: (node: ImpactNode) => client.put<ImpactNode>('/change-impact/locks', { key: node.key, expected_version: node.version, expected_lock_version: node.lock_version, locked: !node.locked }),
    preflight: (source: ImpactSource, selected: ImpactNode[]) => client.post<ImpactPreflight>('/change-impact/preflights', { source: { kind: source.kind, id: source.id }, selected: selected.map(node => ({ key: node.key, expected_version: node.version })) }),
    prepare: (plan: ImpactPreflight, key: string) => client.post<{ items: ImpactRefresh[] }>(`/change-impact/preflights/${segment(plan.id)}/prepare`, { expected_version: plan.version, preflight_digest: plan.preflight_digest, idempotency_key: key }),
    refreshes: (signal?: AbortSignal) => client.get<{ items: ImpactRefresh[] }>('/change-impact/refreshes', signal),
    execute: (row: ImpactRefresh) => client.post<ImpactRefresh>(`/change-impact/refreshes/${segment(row.id)}/execute`, { expected_task_version: row.task_version }),
    cancel: (row: ImpactRefresh) => client.post<ImpactRefresh>(`/change-impact/refreshes/${segment(row.id)}/cancel`, { expected_task_version: row.task_version }),
  };
}
