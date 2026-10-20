import type { Chapter } from '../api';
import type { ExperimentalClient } from './api';

export type RevisionSelection = { chapter_id: string; chapter_version: number; from_pos: number; to_pos: number; text: string };
export type RevisionBlock = { path: number[]; anchor_id: string; before: string; after: string; from_pos: number; to_pos: number; lock_state: 'UNLOCKED' | 'LOCKED' | 'STALE'; status: 'PENDING' | 'ACCEPTED' | 'REJECTED'; diff: { kind: string; before: string; after: string }[]; diff_method: string };
export type SelectionReceipt = { selection: RevisionSelection; selection_digest: string; blocks: RevisionBlock[]; model_called: false; coordinate_contract: string };
export type RevisionProposal = { id: string; version: number; status: string; stale?: boolean; source: { chapter_id: string; version: number }; blocks?: RevisionBlock[]; origin: string; goal: string; explanations?: { anchor_id: string; kind: string; explanation: string; before_quote: string; after_quote: string; source: string }[]; generation?: { id: string; execution_mode: string }; accepted_chapter_version?: number };
export type ReviewInput = { expected_version: number; accept_ids: string[]; reject_ids: string[]; preview_digest?: string };
export type RevisionPreview = { preview_digest: string; checkpoint_version: number; creates_new_current_revision: boolean; pending_blocks: number; accept_ids: string[]; reject_ids: string[] };
export type RevisionCatalog = { document_digest?: string; chapters: { id: string; title: string; version: number }[]; blocks: { path: number[]; from_pos: number; to_pos: number; text: string; lock_state: string; supported: boolean }[]; branch_sources_available: boolean };
export type VersionCompareInput = { chapter_id: string; current_version: number; before_version: number; after_version: number };
export type SemanticChange = { kind: string; explanation: string; before_quote: string; before_start: number; after_quote: string; after_start: number; source: 'AUTHOR_NOTE' | 'IMPORTED_MODEL_ASSESSMENT'; model_identity: string | null; interpretation?: string; provenance_verification?: string; evidence_verification?: string };
export type VersionComparePreview = { comparison: VersionCompareInput; preview_digest: string; before_text: string; after_text: string; diff: {kind: string; before: string; after: string}[]; diff_method: string; model_called: false; semantic_execution: string };
export type ComparisonModelPreview = { preview_digest: string; execution_available: boolean; quality_verification: string; request: unknown; sources: unknown; broker: {chosen: {route_id: string; provider_id: string; model_id: string} | null}; budget: unknown; max_output_bytes: number; timeout_seconds: number; excluded: string[] };
export type ComparisonExecution = {job_id: string; status: string; receipt_state: string; model_called: boolean; usage_state: string; failure_code?: string; accounting?: unknown};
export type ComparisonModelAssessment = {id: string; kind: string; explanation: string; before_version: number; after_version: number; before_quote: string; before_start: number; after_quote: string; after_start: number; decision: string; source: 'EXECUTED_MODEL_ASSESSMENT'; model: {provider_id: string; model_id: string; synthetic: boolean}; quality_verification: string};
export type ComparisonModelCatalog = {routes: {route_id: string; display_name: string; provider_id: string; model_id: string; synthetic: boolean; available: boolean; reasons: string[]}[]};
export type VersionComparison = VersionComparePreview & { model_preview?: ComparisonModelPreview | null; model_execution?: ComparisonExecution | null; model_assessments?: ComparisonModelAssessment[]; model_unavailable?: boolean; id: string; version: number; status: string; title: string; stale: boolean; changes?: SemanticChange[]; history?: { version: number; status: string; title: string }[] };
export function revisionIntelligenceClient(client: ExperimentalClient) {
  const base = '/revisions';
  return {
    comparisonModelCatalog: () => client.get<ComparisonModelCatalog>(`${base}/comparisons-model/catalog`),
    comparisonModelPreview: (row: VersionComparison, routeId: string) => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/model/preview`, {expected_version: row.version, route_id: routeId}),
    comparisonModelDispatch: (row: VersionComparison) => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/model/dispatch`, {expected_version: row.version, reviewed_preview_digest: row.model_preview?.preview_digest}),
    comparisonModelRefresh: (row: VersionComparison) => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/model/refresh`, {expected_version: row.version}),
    comparisonModelCancel: (row: VersionComparison) => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/model/cancel`, {expected_version: row.version}),
    comparisonModelReview: (row: VersionComparison, opinionId: string, action: 'accept' | 'ignore' | 'reopen') => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/model/opinions/${encodeURIComponent(opinionId)}/${action}`, {expected_version: row.version}),
    originalVersions: (chapterId: string, signal?: AbortSignal) => client.get<{current_version: number; items: {version: number; current: boolean; timestamp?: string}[]}>(`${base}/original-versions?chapter_id=${encodeURIComponent(chapterId)}`, signal),
    compareVersions: (value: VersionCompareInput) => client.post<VersionComparePreview>(`${base}/comparisons/preview`, value),
    comparisons: (signal?: AbortSignal) => client.get<{items: VersionComparison[]}>(`${base}/comparisons`, signal),
    comparison: (id: string) => client.get<VersionComparison>(`${base}/comparisons/${encodeURIComponent(id)}`),
    saveComparison: (value: VersionComparePreview, title: string, changes: SemanticChange[]) => client.post<VersionComparison>(`${base}/comparisons`, {comparison: value.comparison, preview_digest: value.preview_digest, title, changes}),
    editComparison: (row: VersionComparison, title: string, changes: SemanticChange[]) => client.put<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}`, {expected_version: row.version, title, changes}),
    reviewComparison: (row: VersionComparison, action: 'acknowledge' | 'archive' | 'reopen') => client.post<VersionComparison>(`${base}/comparisons/${encodeURIComponent(row.id)}/review`, {expected_version: row.version, action}),
    catalog: (chapterId?: string, signal?: AbortSignal) => client.get<RevisionCatalog>(`${base}/catalog${chapterId ? '?chapter_id=' + encodeURIComponent(chapterId) : ''}`, signal),
    selection: (selection: RevisionSelection) => client.post<SelectionReceipt>(`${base}/selection`, selection),
    create: (selection: SelectionReceipt, replacements: { anchor_id: string; text: string }[], goal: string, jobId?: string) => client.post<RevisionProposal>(`${base}/proposals`, { selection: selection.selection, selection_digest: selection.selection_digest, replacements, goal, ...(jobId ? { job_id: jobId } : {}) }),
    proposals: (signal?: AbortSignal) => client.get<{ items: RevisionProposal[] }>(`${base}/proposals`, signal),
    preview: (proposalId: string, value: ReviewInput) => client.post<RevisionPreview>(`${base}/proposals/${encodeURIComponent(proposalId)}/preview`, value),
    apply: (proposalId: string, value: ReviewInput) => client.post<{ proposal: RevisionProposal; chapter: Chapter | null }>(`${base}/proposals/${encodeURIComponent(proposalId)}/apply`, value),
    rebase: (proposal: RevisionProposal, chapterVersion: number) => client.post<RevisionProposal>(`${base}/proposals/${encodeURIComponent(proposal.id)}/rebase`, { expected_version: proposal.version, chapter_version: chapterVersion }),
    locks: (selection: SelectionReceipt, action: 'lock' | 'unlock') => client.post<Chapter>(`${base}/locks`, { selection: selection.selection, selection_digest: selection.selection_digest, action }),
    unlockBlock: (chapter: Chapter, path: number[], documentDigest: string) => client.post<Chapter>(`${base}/locks/unlock`, { chapter_id: chapter.id, chapter_version: chapter.version, path, document_digest: documentDigest }),
    milestones: (signal?: AbortSignal) => client.get<{ items: { id: string; title: string; goal: string; chapter_id: string; chapter_version: number }[] }>(`${base}/milestones`, signal),
    milestone: (chapter: Chapter, title: string, goal: string) => client.post(`${base}/milestones`, { chapter_id: chapter.id, chapter_version: chapter.version, title, goal }),
  };
}
