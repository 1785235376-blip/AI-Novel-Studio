import type { Chapter } from '../api';
import type { ExperimentalClient } from './api';

export type RevisionSelection = { chapter_id: string; chapter_version: number; from_pos: number; to_pos: number; text: string };
export type RevisionBlock = { path: number[]; anchor_id: string; before: string; after: string; from_pos: number; to_pos: number; lock_state: 'UNLOCKED' | 'LOCKED' | 'STALE'; status: 'PENDING' | 'ACCEPTED' | 'REJECTED'; diff: { kind: string; before: string; after: string }[]; diff_method: string };
export type SelectionReceipt = { selection: RevisionSelection; selection_digest: string; blocks: RevisionBlock[]; model_called: false; coordinate_contract: string };
export type RevisionProposal = { id: string; version: number; status: string; stale?: boolean; source: { chapter_id: string; version: number }; blocks?: RevisionBlock[]; origin: string; goal: string; explanations?: { anchor_id: string; kind: string; explanation: string; before_quote: string; after_quote: string; source: string }[]; generation?: { id: string; execution_mode: string }; accepted_chapter_version?: number };
export type ReviewInput = { expected_version: number; accept_ids: string[]; reject_ids: string[]; preview_digest?: string };
export type RevisionPreview = { preview_digest: string; checkpoint_version: number; creates_new_current_revision: boolean; pending_blocks: number; accept_ids: string[]; reject_ids: string[] };
export type RevisionCatalog = { document_digest?: string; chapters: { id: string; title: string; version: number }[]; blocks: { path: number[]; from_pos: number; to_pos: number; text: string; lock_state: string; supported: boolean }[]; branch_sources_available: boolean };
export function revisionIntelligenceClient(client: ExperimentalClient) {
  const base = '/revisions';
  return {
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
