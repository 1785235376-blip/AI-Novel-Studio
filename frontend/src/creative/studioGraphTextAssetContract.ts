import { ApiError } from '../api';
import type { StudioGraphRun } from './studioGraphTypes';
import type { StudioGraphResultStorage, StudioGraphTextAssetOutput, StudioGraphTextAssetSource } from './studioGraphTextAssetTypes';
import { graphTextExecutionReceipt } from './studioGraphTextExecutionReceipt';
const contract = 'creative-graph-text-asset/1';
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的私有文字资产回执不可用，请重新读取当前运行。' }); }
function object(value: unknown): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(); return value as Record<string, unknown>; }
function keys(row: Record<string, unknown>, expected: string[]) { if (Object.keys(row).some(key => !expected.includes(key))) invalid(); }
function text(value: unknown, max = 240): string { if (typeof value !== 'string' || !value.trim() || value.length > max || /[\u0000-\u001f\u007f]/.test(value)) invalid(); return value; }
function integer(value: unknown, min = 1, max = Number.MAX_SAFE_INTEGER): number { if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid(); return value; }
function digest(value: unknown): string { const result = text(value, 64); if (!/^[a-f0-9]{64}$/.test(result)) invalid(); return result; }
function stamp(value: unknown): string { const result = text(value, 64); if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(result) || !Number.isFinite(Date.parse(result))) invalid(); return result; }
export function graphTextResultStorage(value: unknown): StudioGraphResultStorage {
  const row = object(value); keys(row, ['contract', 'available', 'owner', 'actor_private', 'automatic_model_retry']);
  if (row.contract !== contract || row.available !== true || row.owner !== 'AssetLibraryService' || row.actor_private !== true || row.automatic_model_retry !== false) invalid();
  return { contract, available: true, owner: 'AssetLibraryService', actor_private: true, automatic_model_retry: false };
}
export function graphTextAssetOutput(value: unknown, run: StudioGraphRun, graph?: { version: number; definition_digest: string }): StudioGraphTextAssetOutput {
  const row = object(value), boundary = { contract, actor_private: true as const, applied: false as const, quality_verification: 'NOT_RUN' as const, automatic_model_retry: false as const } as const;
  const common = ['contract', 'state', 'asset_id', 'version', 'actor_private', 'applied', 'quality_verification', 'automatic_model_retry'];
  if (row.contract !== contract || row.actor_private !== true || row.applied !== false || row.quality_verification !== 'NOT_RUN' || row.automatic_model_retry !== false || !run.model_runtime?.execution) invalid();
  if (['PENDING', 'INCOMPLETE', 'NO_ACCEPTED_RESULT'].includes(row.state as string)) {
    keys(row, [...common, 'reason']);
    if (row.asset_id !== null || row.version !== null || row.reason !== undefined && row.state !== 'INCOMPLETE') invalid();
    if (row.state === 'INCOMPLETE' && (!run.stale || run.review !== null || run.model_runtime.preview !== null || Object.values(run.node_states).some(node => node.output !== null))) invalid();
    if (row.state === 'NO_ACCEPTED_RESULT' && !['CANCELLED', 'FAILED'].includes(run.status)) invalid();
    let reason: string | undefined;
    if (row.state === 'INCOMPLETE') { reason = text(row.reason, 120); if (!/^[A-Z][A-Z0-9_]{0,119}$/.test(reason)) invalid(); }
    return { ...boundary, state: row.state as 'PENDING' | 'INCOMPLETE' | 'NO_ACCEPTED_RESULT', asset_id: null, version: null, ...(reason === undefined ? {} : { reason }) };
  }
  keys(row, [...common, 'sha256', 'size', 'kind', 'media_type', 'created_at', 'updated_at', 'provider_id', 'model_id', 'parameters', 'source', 'execution_receipt']);
  if (!['DRAFT', 'APPROVED', 'REJECTED'].includes(row.state as string) || run.stale || !run.model_called
    || !run.model_runtime.execution.model_called || run.model_runtime.execution.receipt_state !== 'RECORDED'
    || run.model_runtime.execution.status !== 'COMPLETED' || !['RESULT_REVIEW', 'TERMINAL'].includes(run.model_runtime.status)
    || row.kind !== 'text' || row.media_type !== 'text/plain') invalid();
  if (row.state === 'APPROVED' && (run.status !== 'SUCCEEDED' || !run.reviewed) || row.state === 'REJECTED' && run.status !== 'REJECTED'
    || row.state === 'DRAFT' && ['CANCELLED', 'FAILED', 'REJECTED'].includes(run.status)) invalid();
  const source = object(row.source), parameters = object(row.parameters);
  keys(source, ['schema_version', 'contract', 'graph_id', 'graph_version', 'graph_digest', 'run_id', 'source_run_version', 'model_node_id', 'job_id', 'input_digest', 'output_digest', 'preview_digest', 'produced_at']);
  keys(parameters, ['max_output_tokens', 'temperature', 'synthetic', 'quality_verification']);
  if (source.schema_version !== 1 || source.contract !== contract || source.graph_id !== run.graph_id || source.graph_version !== run.graph_version
    || source.run_id !== run.id || source.model_node_id !== run.model_runtime.node_id || source.job_id !== run.model_runtime.execution.job_id
    || parameters.temperature !== 0 || typeof parameters.synthetic !== 'boolean' || parameters.synthetic !== run.model_runtime.execution.synthetic || parameters.quality_verification !== 'NOT_RUN') invalid();
  const checkedSource: StudioGraphTextAssetSource = { schema_version: 1, contract, graph_id: run.graph_id, graph_version: run.graph_version,
    graph_digest: digest(source.graph_digest), run_id: run.id, source_run_version: integer(source.source_run_version, 1, run.version), model_node_id: run.model_runtime.node_id,
    job_id: run.model_runtime.execution.job_id, input_digest: digest(source.input_digest), output_digest: digest(source.output_digest), preview_digest: digest(source.preview_digest), produced_at: stamp(source.produced_at) };
  const sha256 = digest(row.sha256), size = integer(row.size, 1, 32000), created = stamp(row.created_at), updated = stamp(row.updated_at);
  const provider = text(row.provider_id), model = text(row.model_id), maxTokens = integer(parameters.max_output_tokens, 1, 2048), preview = run.model_runtime.preview;
  if (sha256 !== checkedSource.output_digest || Date.parse(updated) < Date.parse(created) || Date.parse(created) < Date.parse(checkedSource.produced_at)
    || graph?.version === run.graph_version && graph.definition_digest !== checkedSource.graph_digest) invalid();
  if (row.state !== 'REJECTED' && !preview) invalid();
  if (preview && (preview.preview_digest !== checkedSource.preview_digest || preview.input_digest !== checkedSource.input_digest
    || preview.route?.provider_id !== provider || preview.route.model_id !== model || preview.route.synthetic !== parameters.synthetic || preview.limits.max_output_tokens !== maxTokens)) invalid();
  const modelText = run.node_states[run.model_runtime.node_id]?.output?.draft?.text;
  if (modelText !== undefined && new TextEncoder().encode(modelText).length !== size) invalid();
  const receipt = Object.hasOwn(row, 'execution_receipt') ? graphTextExecutionReceipt(row.execution_receipt, {
    provider_id: provider, model_id: model, max_output_tokens: maxTokens, synthetic: parameters.synthetic, source: checkedSource,
  }, preview) : undefined;
  return { ...boundary, state: row.state as 'DRAFT' | 'APPROVED' | 'REJECTED', asset_id: text(row.asset_id), version: integer(row.version), sha256, size, kind: 'text', media_type: 'text/plain',
    created_at: created, updated_at: updated, provider_id: provider, model_id: model,
    parameters: { max_output_tokens: maxTokens, temperature: 0, synthetic: parameters.synthetic, quality_verification: 'NOT_RUN' }, source: checkedSource,
    ...(receipt === undefined ? {} : { execution_receipt: receipt }) };
}
