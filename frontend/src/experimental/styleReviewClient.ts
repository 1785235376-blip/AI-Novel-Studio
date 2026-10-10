import { useLayoutEffect, useRef, useState } from 'react';
import type { ExperimentalClient } from './api';
import type { RoomMember, RoomTask, TaskFields } from './writerRoomClient';

export type StyleOperation = 'continue' | 'rewrite' | 'polish' | 'brainstorm' | 'review';
export const styleOperationLabels: Record<StyleOperation, string> = { continue: '续写', rewrite: '重写', polish: '润色', brainstorm: '脑暴', review: '审阅' };
export type ReviewChapter = { id: string; title: string; version: number; characters?: number };
export type StyleProfileInput = { title: string; instructions: string; rules: string[]; chapter_ids: string[]; character_ids: string[] };
export type StyleProfile = StyleProfileInput & { id: string; version: number; status: 'DRAFT' | 'APPROVED' | 'ARCHIVED'; stale?: boolean; privacy_level?: string };
export type StyleCatalog = { styles: StyleProfile[]; chapters: ReviewChapter[]; characters: { id: string; name: string }[]; operations: StyleOperation[] };
export type StyleSample = { chapter_id: string; expected_version: number; start: number; end: number | null };
export type StyleAnalysisInput = { style_id: string; expected_style_version: number; language: 'zh' | 'en'; samples: StyleSample[]; comparison?: { chapter_id: string; expected_version: number; language: 'zh' | 'en' }; operations: StyleOperation[] };
export type StyleSampleMetrics = StyleSample & { metrics: Record<string, unknown>; coordinate: 'RAW_MARKDOWN_UNICODE_CODEPOINT'; paragraphs: { paragraph: number; start: number; end: number; quote: string; partial_paragraph: boolean }[]; paragraphs_truncated: boolean; dialogue_spans: { start: number; end: number }[] };
export type StyleAnalysis = { id: string; version: number; style_id: string; style_version: number; language: 'zh' | 'en'; method_version: string; sample_metrics?: StyleSampleMetrics[]; metric_kind?: 'DETERMINISTIC_METRIC'; model_opinion_state?: 'NOT_CONFIGURED' | 'NOT_REQUESTED' | 'PREVIEWED' | 'AVAILABLE' | 'ABSTAINED' | 'UNKNOWN' | 'FAILED' | 'CANCELLED' | 'STALE'; model_preview?: StyleModelPreview | null; model_execution?: JudgeModelExecution | null; model_assessments?: StyleModelOpinion[]; unmeasured?: string[]; status: string; stale: boolean; metrics: Record<string, unknown>; samples: StyleSample[]; comparison: unknown; limitations: string[]; privacy_level: string };
export type StylePreview = { style_id: string; style_version: number; instructions: string; rules: string[]; operation: StyleOperation; character_id: string | null; privacy_level: string; context_injection: 'INSTRUCTIONS_ONLY'; rules_usage: 'REFERENCE_ONLY'; model_called: false; preview_digest: string };
export type JudgeRubric = { id: string; version: number; title: string; checks: string[]; limitations: string[] };
export type JudgeCatalog = { chapters: ReviewChapter[]; rubrics: JudgeRubric[]; adapters: unknown[] };
export type JudgeEvidence = { chapter_id: string; chapter_version: number; paragraph: number; start: number; end: number; quote: string };
export type JudgeFinding = { id: string; version: number; status: 'OPEN' | 'RESOLVED'; decision: 'PENDING' | 'REVIEWED' | 'ACCEPTED' | 'IGNORED' | 'INTENTIONAL'; intentional_reused?: boolean; code: string; category: string; severity: 'INFO' | 'WARNING'; explanation: string; suggestion: string; boundary: string; origin: 'DETERMINISTIC' | 'MODEL_ASSESSMENT'; evidence: JudgeEvidence[]; stale: boolean; revision?: { chapter_id: string; version: number } | null; model?: { provider_id: string; model_id: string; synthetic: boolean; identity: Record<string, unknown> }; independence?: string; quality_verification?: string; review_history?: { action: string; reason?: string; at?: string }[] };
export type JudgeRun = { id: string; version: number; status: string; stale: boolean; findings: JudgeFinding[]; abstentions: string[]; verification: string; model_called: boolean; chapter_ids?: string[]; created_at?: string; model_preview?: JudgeModelPreview | null; model_execution?: JudgeModelExecution | null };
export type JudgeModelRoute = { route_id: string; provider_id: string; model_id: string; display_name: string; synthetic: boolean; available: boolean; reasons: string[]; identity: Record<string, unknown> };
export type JudgeModelCatalog = { routes: JudgeModelRoute[]; rubric: { id: string; version: number; boundary: string }; max_output_bytes: number; timeout_seconds: number; boundary: string };
export type JudgeModelPreview = { previewed_at: string; budget: Record<string, unknown>; preview_digest: string; actor: string; scope: Record<string, unknown>; sources: Record<string, { version: number; digest: string }>; request: Record<string, unknown>; rubric: { id: string; version: number; boundary: string }; broker: { chosen: (JudgeModelRoute & { price: Record<string, unknown> }) | null; budget_version: number; candidates: JudgeModelRoute[]; decision_reason: string; }; excluded: string[]; max_output_bytes: number; timeout_seconds: number; execution_available: boolean; quality_verification: string };
export type StyleModelPreview = JudgeModelPreview & { style_profile: { id: string; version: number; title: string; instructions: string; rules: string[] }; samples: StyleSample[]; source_strategy: 'EXACT_SELECTED_STYLE_RANGES' };
export type StyleModelOpinion = { id: string; category: 'NARRATIVE_DISTANCE' | 'EMOTIONAL_TONE' | 'RHYTHM' | 'HUMOR' | 'IMAGERY'; interpretation: string; boundary: string; evidence: JudgeEvidence[]; origin: 'MODEL_DERIVED'; decision: 'PENDING' | 'REVIEWED' | 'IGNORED'; model: Pick<JudgeModelRoute, 'route_id' | 'provider_id' | 'model_id' | 'synthetic' | 'identity'>; quality_verification: string; independence: 'UNVERIFIED'; review_history: { action: string; reason: string; at: string }[] };
export type JudgeModelExecution = { job_id: string; reservation_id: string | null; status: string; receipt_state: string; model_called: boolean; usage_state: string; failure_code?: string | null; accounting?: Record<string, unknown> | null };
export type JudgeReviewInput = { expected_version: number; action: 'review' | 'accept' | 'ignore' | 'intentional' | 'reopen'; reason: string; revision_chapter_id?: string | null; revision_version?: number | null };
export type JudgeRevisionCatalog = { finding_id: string; finding_version: number; members: RoomMember[]; existing_task: RoomTask | null; task_authority: 'writer_room_v2'; manuscript_changed: false };
const segment = encodeURIComponent;
export function styleReviewClient(client: ExperimentalClient) {
  return {
    styleCatalog: (signal?: AbortSignal) => client.get<StyleCatalog>('/style-analysis/catalog', signal),
    createProfile: (body: StyleProfileInput) => client.post<StyleProfile>('/style-analysis/profiles', body),
    updateProfile: (id: string, version: number, body: StyleProfileInput) => client.put<StyleProfile>(`/style-analysis/profiles/${segment(id)}`, { ...body, expected_version: version }),
    transitionProfile: (row: StyleProfile, action: 'approve' | 'archive') => client.post<StyleProfile>(`/style-analysis/profiles/${segment(row.id)}/${action}`, { expected_version: row.version }),
    analyses: (signal?: AbortSignal) => client.get<{ items: StyleAnalysis[] }>('/style-analysis/analyses', signal),
    analyze: (body: StyleAnalysisInput) => client.post<StyleAnalysis>('/style-analysis/analyses', body),
    analysis: (id: string, signal?: AbortSignal) => client.get<StyleAnalysis>(`/style-analysis/analyses/${segment(id)}`, signal),
    styleModelCatalog: () => client.get<JudgeModelCatalog>('/style-analysis/model/catalog'),
    previewStyleModel: (row: StyleAnalysis, routeId: string) => client.post<StyleAnalysis>(`/style-analysis/analyses/${segment(row.id)}/model/preview`, { expected_version: row.version, route_id: routeId }),
    dispatchStyleModel: (row: StyleAnalysis) => client.post<StyleAnalysis>(`/style-analysis/analyses/${segment(row.id)}/model/dispatch`, { expected_version: row.version, reviewed_preview_digest: row.model_preview?.preview_digest }),
    refreshStyleModel: (row: StyleAnalysis) => client.post<StyleAnalysis>(`/style-analysis/analyses/${segment(row.id)}/model/refresh`, { expected_version: row.version }),
    cancelStyleModel: (row: StyleAnalysis) => client.post<StyleAnalysis>(`/style-analysis/analyses/${segment(row.id)}/model/cancel`, { expected_version: row.version }),
    reviewStyleOpinion: (row: StyleAnalysis, opinionId: string, action: 'review' | 'ignore' | 'reopen', reason: string) => client.post<StyleAnalysis>(`/style-analysis/analyses/${segment(row.id)}/opinions/${segment(opinionId)}/review`, { expected_version: row.version, action, reason }),
    previewStyle: (row: StyleProfile, operation: StyleOperation, characterId: string | null) => client.post<StylePreview>(`/style-analysis/profiles/${segment(row.id)}/preview`, { expected_version: row.version, operation, character_id: characterId }),
    judgeCatalog: (signal?: AbortSignal) => client.get<JudgeCatalog>('/narrative-judge/catalog', signal),
    runs: (signal?: AbortSignal) => client.get<{ items: JudgeRun[] }>('/narrative-judge/runs', signal),
    run: (id: string, signal?: AbortSignal) => client.get<JudgeRun>(`/narrative-judge/runs/${segment(id)}`, signal),
    startRun: (chapters: ReviewChapter[], rubricId: string) => client.post<JudgeRun>('/narrative-judge/runs', { chapter_ids: chapters.map(row => row.id), expected_versions: Object.fromEntries(chapters.map(row => [row.id, row.version])), rubric_id: rubricId }),
    judgeModelCatalog: () => client.get<JudgeModelCatalog>('/narrative-judge/model/catalog'),
    previewJudgeModel: (run: JudgeRun, routeId: string) => client.post<JudgeRun>(`/narrative-judge/runs/${segment(run.id)}/model/preview`, { expected_version: run.version, route_id: routeId }),
    dispatchJudgeModel: (run: JudgeRun) => client.post<JudgeRun>(`/narrative-judge/runs/${segment(run.id)}/model/dispatch`, { expected_version: run.version, reviewed_preview_digest: run.model_preview?.preview_digest }),
    refreshJudgeModel: (run: JudgeRun) => client.post<JudgeRun>(`/narrative-judge/runs/${segment(run.id)}/model/refresh`, { expected_version: run.version }),
    cancelJudgeModel: (run: JudgeRun) => client.post<JudgeRun>(`/narrative-judge/runs/${segment(run.id)}/model/cancel`, { expected_version: run.version }),
    revisionTaskCatalog: (id: string) => client.get<JudgeRevisionCatalog>(`/narrative-judge/findings/${segment(id)}/revision-task`),
    createRevisionTask: (id: string, version: number, fields: TaskFields) => client.post<{ task: RoomTask; task_authority: 'writer_room_v2'; manuscript_changed: false }>(`/narrative-judge/findings/${segment(id)}/revision-task`, { ...fields, expected_version: version }),
    reviewFinding: (id: string, body: JudgeReviewInput) => client.post<JudgeFinding>(`/narrative-judge/findings/${segment(id)}/review`, body),
  };
}
export type StyleReviewClient = ReturnType<typeof styleReviewClient>;

// The synchronous lock prevents duplicate writes before React paints disabled.
// The lifetime check also protects parent callbacks after a scope-keyed remount.
export function useReviewAction() {
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(), [notice, setNotice] = useState('');
  const running = useRef(false), alive = useRef(true), sequence = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; }; }, []);
  const run = async (operation: (isCurrent: () => boolean) => Promise<void>, message = '') => {
    if (running.current || !alive.current) return;
    running.current = true; setBusy(true); setError(undefined); setNotice('');
    const ticket = ++sequence.current;
    const isCurrent = () => alive.current && ticket === sequence.current;
    try { await operation(isCurrent); if (isCurrent()) setNotice(message); }
    catch (value) { if (isCurrent()) setError(value); }
    finally { running.current = false; if (isCurrent()) setBusy(false); }
  };
  return { busy, error, notice, run, clear: () => { setError(undefined); setNotice(''); } };
}
