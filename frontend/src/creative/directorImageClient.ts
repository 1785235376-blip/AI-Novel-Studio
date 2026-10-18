/** IMAGE V3 only. Reads never dispatch, and metadata never becomes review authority. */
import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';
import type { StudioAsset } from './studioClient';

export type ImageTarget = { document_id: string; version: number; digest: string; scene_id: string };
export type ImageAssetPin = { asset_id: string; version: number; sha256: string };
export type ImageRegistration = { provider_id: string; model_id: string; display_name: string };
export type ImageCapabilities = { enabled: boolean; registered_choices: ImageRegistration[] };
export type ImageStatus = { id: string; version: number; status: 'PREVIEW' | 'DISPATCHED' | 'PENDING_REVIEW' | 'ADOPTED'; job_id: string | null;
  job_status: string | null; can_cancel: boolean; target_document_id: string; target_scene_id: string;
  recovery_state?: 'EXECUTOR_UNAVAILABLE_NO_REPLAY'; adoption_receipt?: { request_id: string; target: ImageTarget; historical: true; committed: true } };
export type ImageAdvice = { observations: string[]; suggestions: string[]; uncertainty: string };
export type ImagePreviewInput = { asset: ImageAssetPin; target: ImageTarget; provider_id: string; model_id: string; instruction: string };
export type ImagePreview = { id: string; version: number; preview_digest: string; target: ImageTarget; asset: ImageAssetPin;
  provider_id: string; model_id: string; prompt: string; parameters: { max_output_tokens: number; temperature: number } };
export type ImagePending = { id: string; version: number; target: ImageTarget; terminal_digest: string; accounting_version: number; advice: ImageAdvice };
export type ImageReview = { proposal_id: string; proposal_version: number; target: ImageTarget; terminal_digest: string;
  accounting_digest: string; declared_microusd: number; advice: ImageAdvice };
export type ImageCostInput = { contract: 'DIRECTOR_IMAGE_COST_DECLARATION_V3'; request_id: string; expected_version: number;
  reviewed_terminal_digest: string; declared_microusd: number; evidence_note: string; confirmed_declaration: true };
export type ImageAdoptionInput = { contract: 'DIRECTOR_IMAGE_ADOPTION_INPUT_V1'; request_id: string; expected_version: number; target: ImageTarget;
  reviewed_terminal_digest: string; reviewed_accounting_digest: string; selected_suggestions: number[]; note: string; human_review_confirmed: true };
export type ImageAdoption = { proposal_id: string; target: ImageTarget; historical: boolean; committed: true };

function invalid(): never { throw new ApiError({ status: 200, code: 'DIRECTOR_IMAGE_RESPONSE_INVALID', message: '图像导演回执不完整或来源已变化。请明确读取原任务状态，不要重复提交。' }); }
function record(value: unknown): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(); return value as Record<string, unknown>; }
function closed(r: Record<string, unknown>, required: string[], optional: string[] = []) { if (required.some(k => !Object.hasOwn(r, k)) || Object.keys(r).some(k => !required.includes(k) && !optional.includes(k))) invalid(); }
function text(value: unknown, max = 240): string { if (typeof value !== 'string' || !value.trim() || value.length > max || /[\u0000\u007f]/.test(value)) invalid(); return value; }
function integer(value: unknown, min = 1, max = Number.MAX_SAFE_INTEGER): number { if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid(); return value; }
function hash(value: unknown): string { const s = text(value, 64); if (!/^[a-f0-9]{64}$/.test(s)) invalid(); return s; }
function target(value: unknown): ImageTarget { const r = record(value); closed(r, ['document_id', 'version', 'digest', 'scene_id']); return { document_id: text(r.document_id), version: integer(r.version), digest: hash(r.digest), scene_id: text(r.scene_id) }; }
function pin(value: unknown): ImageAssetPin { const r = record(value); closed(r, ['asset_id', 'version', 'sha256']); return { asset_id: text(r.asset_id), version: integer(r.version), sha256: hash(r.sha256) }; }
function same(a: ImageTarget, b: ImageTarget) { return a.document_id === b.document_id && a.version === b.version && a.digest === b.digest && a.scene_id === b.scene_id; }
function advice(value: unknown): ImageAdvice { const r = record(value); closed(r, ['contract', 'observations', 'suggestions', 'uncertainty']); if (r.contract !== 'DIRECTOR_IMAGE_ADVICE_V3') invalid();
  const rows = (v: unknown) => { if (!Array.isArray(v) || !v.length || v.length > 8) invalid(); return v.map(s => text(s, 2000)); };
  return { observations: rows(r.observations), suggestions: rows(r.suggestions), uncertainty: text(r.uncertainty, 2000) }; }
function status(value: unknown, id?: string): ImageStatus {
  const r = record(value); closed(r, ['id', 'version', 'status', 'job_id', 'job_status', 'can_cancel', 'automatic_retry', 'content_freshness', 'target_document_id', 'target_scene_id'], ['recovery_state', 'adoption_receipt']);
  if (id && r.id !== id || r.automatic_retry !== false || r.content_freshness !== 'NOT_CHECKED' || typeof r.can_cancel !== 'boolean'
    || !['PREVIEW', 'DISPATCHED', 'PENDING_REVIEW', 'ADOPTED'].includes(String(r.status))) invalid();
  const result: ImageStatus = { id: text(r.id), version: integer(r.version), status: r.status as ImageStatus['status'], job_id: r.job_id === null ? null : text(r.job_id),
    job_status: r.job_status === null ? null : text(r.job_status), can_cancel: r.can_cancel, target_document_id: text(r.target_document_id), target_scene_id: text(r.target_scene_id) };
  if (r.recovery_state !== undefined) { if (r.recovery_state !== 'EXECUTOR_UNAVAILABLE_NO_REPLAY') invalid(); result.recovery_state = r.recovery_state; }
  if (r.adoption_receipt !== undefined) { const a = record(r.adoption_receipt); closed(a, ['request_id', 'target', 'historical', 'committed']); if (a.historical !== true || a.committed !== true) invalid();
    result.adoption_receipt = { request_id: text(a.request_id), target: target(a.target), historical: true, committed: true }; }
  return result;
}

export function createDirectorImageClient(projectId: string, transport: StudioGraphTransport, context: Pick<CollaborationContext, 'scope' | 'actor'>,
  assets: (signal?: AbortSignal) => Promise<{ items: StudioAsset[] }>) {
  const project = text(projectId), owner = context.actor?.id, scope = context.scope ? { ...context.scope } : undefined;
  if (scope && scope.projectId !== project) invalid();
  const expectedScope = scope ? { mode: 'collaboration', novel_id: project, workspace_id: scope.workspaceId, storyline_id: scope.storylineId, branch_id: scope.branchId } : { mode: 'local', novel_id: project };
  const base = `/api/novels/${encodeURIComponent(project)}/experimental/creative/director-image-v3`;
  async function call(path: string, method: 'GET' | 'POST', body?: unknown, signal?: AbortSignal): Promise<unknown> {
    if (signal?.aborted) throw new DOMException('已取消读取。', 'AbortError');
    const value = await transport.json<unknown>(`${base}${path}`, method, body, signal);
    if (signal?.aborted) throw new DOMException('已取消读取。', 'AbortError'); return value;
  }
  const path = (id: string, suffix = '') => `/proposals/${encodeURIComponent(text(id))}${suffix}`;
  function source(value: unknown): ImageAssetPin {
    const r = record(value), s = record(r.scope);
    if (r.contract !== 'CREATIVE_DIRECTOR_IMAGE_SOURCE_V3' || r.source_kind !== 'IMAGE' || r.project_id !== project || owner && r.actor_id !== owner
      || Object.keys(s).length !== Object.keys(expectedScope).length || Object.entries(expectedScope).some(([k, v]) => s[k] !== v)
      || !['image/png', 'image/jpeg'].includes(String(r.media_type)) || r.orientation !== 'IDENTITY_ONLY' || r.transformation !== 'NONE_EXACT_ASSET_BYTES') invalid();
    integer(r.byte_count, 1, 4 * 1024 * 1024); const w = integer(r.width, 1, 4096), h = integer(r.height, 1, 4096); if (w * h > 4 * 1024 * 1024) invalid();
    return pin(r.asset);
  }
  return {
    assets,
    async capabilities(signal?: AbortSignal): Promise<ImageCapabilities> {
      const r = record(await call('/capabilities', 'GET', undefined, signal));
      closed(r, ['contract', 'enabled', 'registered_choices', 'local_only', 'automatic_retry', 'automatic_fallback', 'measurement_verified', 'observations_verified', 'recovery_available', 'vision_registration_required']);
      if (r.contract !== 'DIRECTOR_IMAGE_CAPABILITIES_V3' || typeof r.enabled !== 'boolean' || r.local_only !== true || r.automatic_retry !== false || r.automatic_fallback !== false
        || r.measurement_verified !== false || r.observations_verified !== false || r.recovery_available !== true || r.vision_registration_required !== true || !Array.isArray(r.registered_choices) || r.registered_choices.length > 100) invalid();
      return { enabled: r.enabled, registered_choices: r.registered_choices.map(value => { const c = record(value); closed(c, ['provider_id', 'model_id', 'display_name']); return { provider_id: text(c.provider_id), model_id: text(c.model_id), display_name: text(c.display_name, 1000) }; }) };
    },
    async list(signal?: AbortSignal): Promise<{ items: ImageStatus[]; truncated: boolean }> {
      const r = record(await call('/proposals', 'GET', undefined, signal)); closed(r, ['items', 'limit', 'truncated']);
      if (!Array.isArray(r.items) || r.items.length > integer(r.limit, 1, 50) || typeof r.truncated !== 'boolean') invalid();
      return { items: r.items.map(value => status(value)), truncated: r.truncated };
    },
    async status(id: string, signal?: AbortSignal) { return status(await call(path(id), 'GET', undefined, signal), id); },
    async preview(input: ImagePreviewInput, signal?: AbortSignal): Promise<ImagePreview> {
      const body = { asset: pin(input.asset), target: target(input.target), provider_id: text(input.provider_id), model_id: text(input.model_id), instruction: text(input.instruction, 2000) };
      if (new TextEncoder().encode(body.instruction).length > 8000) invalid();
      const r = record(await call('/preview', 'POST', body, signal)); closed(r, ['id', 'version', 'status', 'preview_digest', 'preview', 'model_called', 'measurement_verified', 'observations_verified']);
      if (r.status !== 'PREVIEW' || r.model_called !== false || r.measurement_verified !== false || r.observations_verified !== false) invalid();
      const p = record(r.preview); closed(p, ['source', 'target', 'provider_id', 'model_id', 'route_digest', 'prompt', 'parameters']);
      const asset = source(p.source), wanted = target(p.target), params = record(p.parameters); closed(params, ['max_output_tokens', 'temperature']);
      if (!same(wanted, body.target) || asset.asset_id !== body.asset.asset_id || asset.version !== body.asset.version || asset.sha256 !== body.asset.sha256
        || p.provider_id !== body.provider_id || p.model_id !== body.model_id || typeof params.temperature !== 'number' || !Number.isFinite(params.temperature) || params.temperature < 0 || params.temperature > 2) invalid();
      hash(p.route_digest);
      return { id: text(r.id), version: integer(r.version), preview_digest: hash(r.preview_digest), target: wanted, asset, provider_id: body.provider_id, model_id: body.model_id,
        prompt: text(p.prompt, 16000), parameters: { max_output_tokens: integer(params.max_output_tokens, 1, 2048), temperature: params.temperature } };
    },
    async dispatch(preview: ImagePreview, signal?: AbortSignal) {
      return status(await call(path(preview.id, '/dispatch'), 'POST', { expected_version: integer(preview.version), reviewed_preview_digest: hash(preview.preview_digest) }, signal), preview.id);
    },
    async cancel(current: ImageStatus, signal?: AbortSignal): Promise<void> {
      const r = record(await call(path(current.id, '/cancel'), 'POST', {}, signal)); closed(r, ['job_id', 'state', 'upstream_stopped']);
      if (r.job_id !== current.job_id || r.state !== 'CANCELLATION_REQUESTED' || r.upstream_stopped !== false) invalid();
    },
    async prepare(current: ImageStatus, expected: ImageTarget, signal?: AbortSignal): Promise<ImagePending> {
      const r = record(await call(path(current.id, '/prepare-review'), 'POST', { expected_version: current.version }, signal));
      closed(r, ['id', 'version', 'status', 'pending', 'accounting_version']);
      if (r.id !== current.id || r.status !== 'PENDING_REVIEW') invalid();
      const p = record(r.pending); if (p.contract !== 'DIRECTOR_IMAGE_PENDING_V3' || p.observations_verified !== false || p.quality_verification !== 'HUMAN_REVIEW_REQUIRED' || p.adoption_available !== false || p.accounting_status !== 'UNKNOWN_UPSTREAM') invalid();
      source(p.source); const wanted = target(p.target); if (!same(wanted, expected)) invalid();
      return { id: current.id, version: integer(r.version), target: wanted, terminal_digest: hash(p.terminal_digest), accounting_version: integer(r.accounting_version), advice: advice(p.advice) };
    },
    async declareCost(id: string, input: ImageCostInput, signal?: AbortSignal): Promise<void> {
      const body = { ...input, request_id: text(input.request_id, 160), expected_version: integer(input.expected_version), reviewed_terminal_digest: hash(input.reviewed_terminal_digest), declared_microusd: integer(input.declared_microusd, 0, 10 ** 12), evidence_note: text(input.evidence_note, 500) };
      if (input.contract !== 'DIRECTOR_IMAGE_COST_DECLARATION_V3' || input.confirmed_declaration !== true) invalid();
      const r = record(await call(path(id, '/declare-cost'), 'POST', body, signal)), proof = record(r.director_image_cost_declaration);
      if (r.status !== 'RECONCILED' || r.cost_state !== 'HUMAN_DECLARED_LOCAL_COST' || r.measurement_verified !== false || r.declared_microusd !== input.declared_microusd
        || proof.request_id !== input.request_id || proof.reviewed_terminal_digest !== input.reviewed_terminal_digest || r.version !== input.expected_version + 1) invalid();
    },
    async review(id: string, expected: ImageTarget, signal?: AbortSignal): Promise<ImageReview> {
      const r = record(await call(path(id, '/review'), 'POST', {}, signal));
      closed(r, ['contract', 'proposal_id', 'proposal_version', 'target', 'terminal_digest', 'accounting_digest', 'accounting', 'measurement_verified', 'advice', 'observations_verified', 'adoption_available', 'human_review_required']);
      const wanted = target(r.target), accounting = record(r.accounting);
      if (r.contract !== 'DIRECTOR_IMAGE_REVIEW_V1' || r.proposal_id !== id || !same(wanted, expected) || r.measurement_verified !== false || r.observations_verified !== false
        || r.adoption_available !== true || r.human_review_required !== true || accounting.cost_state !== 'HUMAN_DECLARED_LOCAL_COST' || accounting.measurement_verified !== false) invalid();
      return { proposal_id: id, proposal_version: integer(r.proposal_version), target: wanted, terminal_digest: hash(r.terminal_digest), accounting_digest: hash(r.accounting_digest),
        declared_microusd: integer(accounting.declared_microusd, 0, 10 ** 12), advice: advice(r.advice) };
    },
    async adopt(id: string, input: ImageAdoptionInput, signal?: AbortSignal): Promise<ImageAdoption> {
      const body = { ...input, request_id: text(input.request_id, 160), expected_version: integer(input.expected_version), target: target(input.target),
        reviewed_terminal_digest: hash(input.reviewed_terminal_digest), reviewed_accounting_digest: hash(input.reviewed_accounting_digest), note: text(input.note, 8000), selected_suggestions: [...input.selected_suggestions] };
      if (body.contract !== 'DIRECTOR_IMAGE_ADOPTION_INPUT_V1' || body.human_review_confirmed !== true || !body.selected_suggestions.length || body.selected_suggestions.length > 8
        || new Set(body.selected_suggestions).size !== body.selected_suggestions.length || body.selected_suggestions.some(n => !Number.isInteger(n) || n < 0 || n > 7)) invalid();
      const r = record(await call(path(id, '/adopt'), 'POST', body, signal)), wanted = target(r.target);
      if (r.contract !== 'DIRECTOR_IMAGE_ADOPTION_RECEIPT_V1' || r.proposal_id !== id || r.request_id !== input.request_id || r.committed !== true || typeof r.historical !== 'boolean'
        || r.measurement_verified !== false || !same(wanted, { ...input.target, version: input.target.version + 1, digest: wanted.digest })) invalid();
      return { proposal_id: id, target: wanted, historical: r.historical, committed: true };
    },
  };
}
export type DirectorImageClient = ReturnType<typeof createDirectorImageClient>;
