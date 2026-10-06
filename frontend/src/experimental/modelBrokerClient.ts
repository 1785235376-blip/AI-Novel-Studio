import type { ExperimentalClient, Row } from './api';
import type { AuthorRequestBody } from '../novel/authorContextClient';
export type BrokerRoute = { route_id: string; provider_id: string; model_id: string; adapter_id?: string; display_name: string; capability: string; available: boolean; eligible?: boolean; cloud: boolean; synthetic: boolean; fingerprint: string; reasons: string[]; context_window: number | null; verification: string; cost_state?: string; price?: { reserve_microusd: number; source: string } | null; identity: Record<string, unknown> };
export type BrokerBudget = { version: number; limit_microusd: number | null; max_inflight: number; require_known_estimate: boolean; committed_microusd: number; inflight: number; unknown_count: number; overrun_count: number };
export type BrokerStatus = { candidates: BrokerRoute[]; budget: BrokerBudget; prices: Row[]; author_execution_available: boolean };
export type BrokerPreview = Row & { chosen: BrokerRoute | null; candidates: BrokerRoute[]; decision_reason: string; warnings: string[]; will_send: Record<string, unknown> };
export type BrokerJob = { ledger: Row; job: { id: string; chapter_id: string; status: string; output: string; error?: string } | null; recovery: string | null; orphan_reconciliation_available?: boolean };
export function modelBrokerClient(client: ExperimentalClient) {
  const base = '/model-broker', benchmarks = '/model-benchmarks';
  return {
    status: (signal?: AbortSignal) => client.get<BrokerStatus>(base + '/status', signal),
    history: (signal?: AbortSignal) => client.get<{ decisions: BrokerPreview[]; ledger: Row[] }>(base + '/history', signal),
    preview: (body: Record<string, unknown>) => client.post<BrokerPreview>(base + '/preview', body),
    budget: (body: Record<string, unknown>) => client.put<BrokerBudget>(base + '/budget', body),
    price: (body: Record<string, unknown>) => client.put<Row>(base + '/price', body),
    generate: (preview: BrokerPreview, author: AuthorRequestBody, requestId: string) => client.post<{ job_id: string; reservation_id: string; status: string }>(base + '/generate', { preview_id: preview.id, expected_version: preview.version, author, request_id: requestId }),
    job: (reservationId: string, signal?: AbortSignal) => client.get<BrokerJob>(base + '/jobs/' + encodeURIComponent(reservationId), signal),
    reconcile: (row: Row, amount: number, note: string, orphan = false) => client.post<Row>(base + '/ledger/' + encodeURIComponent(row.id) + '/reconcile', { expected_version: row.version, actual_microusd: amount, evidence_note: note, upstream_terminal_confirmed: true, original_executor_stopped_confirmed: orphan }),
    cancel: (reservationId: string, expectedVersion: number) => client.post<BrokerJob>(base + '/jobs/' + encodeURIComponent(reservationId) + '/cancel', { expected_version: expectedVersion }),
    benchmarks: (signal?: AbortSignal) => client.get<{ sets: Row[]; runs: Row[]; evidence: Row[]; comparisons?: Row[] }>(benchmarks + '/status', signal),
    createSet: (body: Record<string, unknown>) => client.post<Row>(benchmarks + '/sets', body),
    updateSet: (id: string, body: Record<string, unknown>) => client.put<Row>(benchmarks + '/sets/' + encodeURIComponent(id), body),
    startBenchmark: (set: Row, routeId: string, requestId: string) => client.post<Row>(benchmarks + '/runs', { set_id: set.id, expected_set_version: set.version, route_id: routeId, request_id: requestId }),
    benchmarkAction: (row: Row, action: 'step' | 'cancel') => client.post<Row>(benchmarks + '/runs/' + encodeURIComponent(row.id) + '/' + action, { expected_version: row.version }),
    compareBlind: (left: string, right: string) => client.post<Row>(benchmarks + '/comparisons', { left_id: left, right_id: right }),
    voteBlind: (row: Row, choice: string) => client.post<Row>(benchmarks + '/comparisons/' + encodeURIComponent(row.id) + '/vote', { expected_version: row.version, choice }),
    importEvidence: (body: Record<string, unknown>) => client.post<Row>(benchmarks + '/evidence/import', body),
    invalidateEvidence: (row: Row) => client.post<Row>(benchmarks + '/evidence/' + encodeURIComponent(row.id) + '/invalidate', { expected_version: row.version }),
  };
}
export type BrokerApi = ReturnType<typeof modelBrokerClient>;
