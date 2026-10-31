import type { ExperimentalClient } from './api';

export type SimulatorSource = { id: string; title: string; version: number };
export type SimulatorNode = SimulatorSource & { chapter_ids: string[] };
export type SimulatorCatalog = { chapters: SimulatorSource[]; characters: { id: string; name: string }[]; planning_nodes: SimulatorNode[]; scenes?: { id: string; label: string; chapter_id: string; position: number }[]; limits: { max_steps: number; max_branches: number; max_expansions: number }; model_configured: boolean; model_routes?: SimulatorModelRoute[] };
export type SimulatorContextInput = { chapter_id: string; expected_version: number; character_id: string; scene_id?: string | null; world_time: number | null; calendar: 'story' };
export type SimulatorKnowledge = { id: string; version: number; text: string; category: string };
export type SimulatorContext = Omit<SimulatorContextInput, 'expected_version'> & { context_digest: string; mind?: Record<string, { text: string; epistemic_status: string; evidence_status: string }[]>; knowledge: SimulatorKnowledge[]; goals: SimulatorKnowledge[]; graph_links?: {id: string; version: number; text: string}[] };
export type SimulatorEvent = { id: string; title: string; at: number; requires: string[]; adds: string[]; removes: string[]; requires_knowledge: string[]; resource_delta: Record<string, number>; foreshadowing_links: string[]; question: string };
export type SimulatorRouteInput = { id: string; title: string; motivation_hypothesis?: string; events: SimulatorEvent[] };
export type SimulatorInput = { chapter_ids: string[]; expected_versions: Record<string, number>; chapter_id: string; character_id: string; scene_id?: string | null; world_time: number | null; calendar: 'story'; node_id: string; expected_node_version: number; context_digest: string; assumptions: string[]; character_goal: string; motivation_hypothesis: string; knowledge_ids: string[]; resources: Record<string, number>; hard_constraints: { forbidden_facts: string[]; resource_caps: Record<string, number>; required_final_facts: string[] }; max_steps: number; max_branches: number; model_id: string | null; model_budget: 0; routes: SimulatorRouteInput[] };
export type SimulatorViolation = { code: string; message: string; event_id?: string };
export type SimulatorRuleEffects = { method: string; facts_added: string[]; facts_removed: string[]; resource_changes: Record<string, {before: number; after: number}>; time_before: number | null; time_after: number | null; interpretation: string };
export type SimulatorStep = { rule_effects?: SimulatorRuleEffects; event_id: string; title: string; at: number; applied: boolean; violations: SimulatorViolation[]; question: string; foreshadowing_links: string[] };
export type SimulatorRoute = { id: string; title: string; cursor: number; status: 'PENDING' | 'COMPLETED' | 'LIMIT_REACHED'; steps: SimulatorStep[]; violations: SimulatorViolation[]; unresolved_questions: string[]; motivation_hypothesis: string; character_goal: string; saved_proposal_id?: string };
export type SimulatorRun = { history_receipts?: {version: number; status: string; updated_at: string; expansions: number; request_digest: string; result_digest: string}[]; id: string; version: number; status: 'READY' | 'RUNNING' | 'COMPLETED' | 'CANCELLED'; stale: boolean; input?: SimulatorInput; created_at?: string; chapter_id?: string; source_version?: number; request_digest?: string; result_digest?: string; model_called?: boolean; model_budget?: 0; expansions?: number; limits?: { max_steps: number; max_branches: number; max_expansions: number }; routes?: SimulatorRoute[]; provenance?: { method: string; execution: 'DETERMINISTIC_MANUAL' | 'MODEL_CANDIDATE_MANUAL_SELECTION'; source_versions: Record<string, {version: number; digest: string}>; context_digest: string; input_digest: string }; limitations: string[]; model_preview?: SimulatorModelPreview | null; model_execution?: { job_id: string; status: string; receipt_state: string; usage_state: string; quality_verification: 'NOT_RUN'; failure_code?: string; accounting?: { status: string; actual_microusd: number | null; cost_state: string } }; model_candidates?: SimulatorModelCandidate[]; model_candidates_digest?: string; model_unavailable?: boolean; model_adopted_run_id?: string; model_adoption?: { run_id: string; candidate_id: string; evidence_ids: string[]; quality_verification: 'NOT_RUN' } };
export type SimulatorModelRoute = { route_id: string; provider_id: string; model_id: string; synthetic: boolean; available: boolean; reasons: string[] };
export type SimulatorModelPreview = { preview_digest: string; execution_available: boolean; source_strategy: string; max_output_bytes: number; timeout_seconds: number; quality_verification: 'NOT_RUN'; request: { prompt?: string; context?: unknown }; broker: { chosen: (SimulatorModelRoute & { price: { source: string; currency: string; reserve_microusd: number; as_of?: string; expires_at?: string } }) | null; candidates: { route_id: string; model_id: string; reasons: string[] }[] } };
export type SimulatorModelCandidate = { id: string; input: SimulatorRouteInput; rules: SimulatorRoute; evidence_ids: string[]; hypothesis: true; quality_verification: 'NOT_RUN' };
export type SimulatorSaved = { proposal_id: string; status: 'REVIEW'; run_id: string };
const base = '/story-simulator';
export function storySimulatorClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<SimulatorCatalog>(`${base}/catalog`, signal),
    context: (body: SimulatorContextInput) => client.post<SimulatorContext>(`${base}/context`, body),
    runs: (signal?: AbortSignal) => client.get<{ items: SimulatorRun[] }>(`${base}/runs`, signal),
    run: (id: string, signal?: AbortSignal) => client.get<SimulatorRun>(`${base}/runs/${encodeURIComponent(id)}`, signal),
    create: (body: SimulatorInput) => client.post<SimulatorRun>(`${base}/runs`, body),
    step: (row: SimulatorRun) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/step`, { expected_version: row.version }),
    cancel: (row: SimulatorRun) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/cancel`, { expected_version: row.version }),
    modelPreview: (row: SimulatorRun, routeId: string) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/model/preview`, { expected_version: row.version, route_id: routeId }),
    modelDispatch: (row: SimulatorRun) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/model/dispatch`, { expected_version: row.version, reviewed_preview_digest: row.model_preview?.preview_digest }),
    modelRefresh: (row: SimulatorRun) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/model/refresh`, { expected_version: row.version }),
    modelCancel: (row: SimulatorRun) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/model/cancel`, { expected_version: row.version }),
    modelSelect: (row: SimulatorRun, candidateId: string) => client.post<SimulatorRun>(`${base}/runs/${encodeURIComponent(row.id)}/model/select`, { expected_version: row.version, reviewed_preview_digest: row.model_preview?.preview_digest, reviewed_candidates_digest: row.model_candidates_digest, candidate_id: candidateId }),
    save: (row: SimulatorRun, routeId: string) => client.post<SimulatorSaved>(`${base}/runs/${encodeURIComponent(row.id)}/save`, { expected_version: row.version, route_id: routeId }),
  };
}
