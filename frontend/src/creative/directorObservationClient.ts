/** Candidate-only read transport. No caller is mounted in the application yet. */
import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';

export type DirectorAdoptionReceipt = {
  contract: 'CREATIVE_DIRECTOR_ADOPTED_DRAFT_V1'; proposal_id: string;
  reviewed_version: number; approved_version: number; reviewed_by: string;
  review_action_digest: string; candidate_output_digest: string; reviewed_output_digest: string;
  source_document_id: string; source_version: number; source_digest: string;
  job_id: string; request_digest: string; terminal_evidence_digest: string;
  document: { document_id: string; version: number; digest: string; mode: 'DIRECTOR'; status: 'DRAFT' };
};
const phases = ['PREVIEW', 'ADMITTED', 'RUNNING', 'SETTLING', 'COMPLETED', 'FAILED', 'CANCELLED', 'UNKNOWN', 'PENDING_REVIEW', 'ADOPTED_DRAFT'] as const;
const settlements = ['NOT_APPLICABLE', 'RESERVED', 'DISPATCHED', 'RELEASED', 'SETTLED', 'UNKNOWN_UPSTREAM'] as const;
export type DirectorStatusReceipt = {
  contract: 'CREATIVE_DIRECTOR_STATUS_V1'; proposal_id: string; version: number;
  phase: typeof phases[number]; job_id: string | null; request_digest: string | null;
  reviewed_preview_digest: string; cancellation_requested: boolean; cancellation_confirmed: boolean;
  dispatch_state: 'NOT_DISPATCHED' | 'DISPATCHED'; settlement_state: typeof settlements[number];
  upstream_cancellation_guaranteed: false; terminal_evidence_digest: string | null;
  adoption: DirectorAdoptionReceipt | null; automatic_retry: false;
};
function invalid(scope = false): never {
  throw new ApiError({ status: scope ? 403 : 200,
    code: scope ? 'DIRECTOR_OBSERVATION_SCOPE_MISMATCH' : 'DIRECTOR_OBSERVATION_RESPONSE_INVALID',
    message: scope ? '项目或分支已变化，请重新打开导演工作台。' : '导演任务回执不完整，请重新读取；不会自动重试生成或审核。' });
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function closed(row: Record<string, unknown>, names: readonly string[]) {
  if (Object.keys(row).length !== names.length || names.some(name => !Object.hasOwn(row, name))) invalid();
}
function id(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 240 || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function hash(value: unknown): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) invalid(); return value;
}
function version(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1) invalid(); return value;
}
function bool(value: unknown): boolean { if (typeof value !== 'boolean') invalid(); return value; }
function choice<T extends string>(value: unknown, values: readonly T[]): T {
  if (typeof value !== 'string' || !values.includes(value as T)) invalid(); return value as T;
}
function adoption(value: unknown, proposal: string): DirectorAdoptionReceipt {
  const r = record(value);
  closed(r, ['contract', 'proposal_id', 'reviewed_version', 'approved_version', 'reviewed_by', 'review_action_digest',
    'candidate_output_digest', 'reviewed_output_digest', 'source_document_id', 'source_version', 'source_digest',
    'job_id', 'request_digest', 'terminal_evidence_digest', 'document']);
  if (r.contract !== 'CREATIVE_DIRECTOR_ADOPTED_DRAFT_V1' || id(r.proposal_id) !== proposal) invalid();
  const reviewed = version(r.reviewed_version), approved = version(r.approved_version);
  if (approved !== reviewed + 1) invalid();
  const d = record(r.document); closed(d, ['document_id', 'version', 'digest', 'mode', 'status']);
  if (d.mode !== 'DIRECTOR' || d.status !== 'DRAFT') invalid();
  return { contract: r.contract, proposal_id: proposal, reviewed_version: reviewed, approved_version: approved,
    reviewed_by: id(r.reviewed_by), review_action_digest: hash(r.review_action_digest),
    candidate_output_digest: hash(r.candidate_output_digest), reviewed_output_digest: hash(r.reviewed_output_digest),
    source_document_id: id(r.source_document_id), source_version: version(r.source_version), source_digest: hash(r.source_digest),
    job_id: id(r.job_id), request_digest: hash(r.request_digest), terminal_evidence_digest: hash(r.terminal_evidence_digest),
    document: { document_id: id(d.document_id), version: version(d.version), digest: hash(d.digest), mode: d.mode, status: d.status } };
}
function status(value: unknown, proposal: string): DirectorStatusReceipt {
  const r = record(value);
  closed(r, ['contract', 'proposal_id', 'version', 'phase', 'job_id', 'request_digest', 'reviewed_preview_digest',
    'cancellation_requested', 'cancellation_confirmed', 'dispatch_state', 'settlement_state',
    'upstream_cancellation_guaranteed', 'terminal_evidence_digest', 'adoption', 'automatic_retry']);
  if (r.contract !== 'CREATIVE_DIRECTOR_STATUS_V1' || id(r.proposal_id) !== proposal
    || r.automatic_retry !== false || r.upstream_cancellation_guaranteed !== false) invalid();
  const result: DirectorStatusReceipt = { contract: r.contract, proposal_id: proposal, version: version(r.version),
    phase: choice(r.phase, phases), job_id: r.job_id === null ? null : id(r.job_id),
    request_digest: r.request_digest === null ? null : hash(r.request_digest), reviewed_preview_digest: hash(r.reviewed_preview_digest),
    cancellation_requested: bool(r.cancellation_requested), cancellation_confirmed: bool(r.cancellation_confirmed),
    dispatch_state: choice(r.dispatch_state, ['NOT_DISPATCHED', 'DISPATCHED']), settlement_state: choice(r.settlement_state, settlements),
    upstream_cancellation_guaranteed: false, terminal_evidence_digest: r.terminal_evidence_digest === null ? null : hash(r.terminal_evidence_digest),
    adoption: r.adoption === null ? null : adoption(r.adoption, proposal), automatic_retry: false };
  if (result.phase === 'PREVIEW') {
    if (result.job_id !== null || result.request_digest !== null || result.terminal_evidence_digest !== null
      || result.adoption !== null || result.cancellation_requested || result.cancellation_confirmed
      || result.dispatch_state !== 'NOT_DISPATCHED' || result.settlement_state !== 'NOT_APPLICABLE') invalid();
  } else if (result.job_id === null || result.request_digest === null || result.settlement_state === 'NOT_APPLICABLE') invalid();
  if ((result.phase === 'ADOPTED_DRAFT') !== (result.adoption !== null)) invalid();
  if (result.adoption && (result.adoption.approved_version !== result.version || result.adoption.job_id !== result.job_id
    || result.adoption.request_digest !== result.request_digest || result.adoption.terminal_evidence_digest !== result.terminal_evidence_digest)) invalid();
  if (['COMPLETED', 'PENDING_REVIEW', 'ADOPTED_DRAFT'].includes(result.phase) && result.terminal_evidence_digest === null) invalid();
  if (result.cancellation_confirmed && (result.phase !== 'CANCELLED'
    || !((result.settlement_state === 'RELEASED' && result.dispatch_state === 'NOT_DISPATCHED')
      || (result.settlement_state === 'SETTLED' && result.dispatch_state === 'DISPATCHED')))) invalid();
  return result;
}

/** Captures scope; inject the existing credential-bearing transport, never discover one. */
export function createDirectorObservationClient(projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'], modelPath: 'model-v1' | 'model-v2' = 'model-v1') {
  if(modelPath!=='model-v1'&&modelPath!=='model-v2') invalid();
  const project = id(projectId), captured = scope ? { ...scope } : undefined;
  if (captured && captured.projectId !== project) invalid(true);
  const expected: Record<string, string> = captured ? { mode: 'collaboration', novel_id: project,
    workspace_id: id(captured.workspaceId), storyline_id: id(captured.storylineId), branch_id: id(captured.branchId) }
    : { mode: 'local', novel_id: project };
  const base = `/api/novels/${encodeURIComponent(project)}/experimental/creative/director-proposals`;
  function envelope(value: unknown, kind: string): unknown {
    const r = record(value); closed(r, ['contract', 'project_id', 'scope', 'kind', 'receipt']);
    if (r.contract !== 'DIRECTOR_OBSERVATION_V1' || r.kind !== kind) invalid();
    const owner = record(r.scope);
    if (r.project_id !== project || Object.keys(owner).length !== Object.keys(expected).length
      || Object.entries(expected).some(([key, value]) => owner[key] !== value)) invalid(true);
    return r.receipt;
  }
  return {
    async readStatus(proposalId: string, signal?: AbortSignal): Promise<DirectorStatusReceipt> {
      const proposal = id(proposalId);
      const raw = await transport.json<unknown>(`${base}/${encodeURIComponent(proposal)}/${modelPath}/status`, 'GET', undefined, signal);
      if (signal?.aborted) throw new DOMException('The read was cancelled.', 'AbortError');
      return status(envelope(raw, 'status'), proposal);
    },
    async readAdoptedDraft(proposalId: string, signal?: AbortSignal): Promise<DirectorAdoptionReceipt> {
      const proposal = id(proposalId);
      const raw = await transport.json<unknown>(`${base}/${encodeURIComponent(proposal)}/${modelPath}/adopted-draft`, 'GET', undefined, signal);
      if (signal?.aborted) throw new DOMException('The read was cancelled.', 'AbortError');
      return adoption(envelope(raw, 'adopted-draft'), proposal);
    },
  };
}

// Shared strict passive decoders for the separately explicit action transport.
export { adoption as checkedDirectorAdoptionReceipt, status as checkedDirectorStatusReceipt };
