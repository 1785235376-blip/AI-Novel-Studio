import { ApiError } from '../api';
import { graphTextResultStorage } from './studioGraphTextAssetContract';
import type { StudioGraphModelCapabilities, StudioGraphModelExecution, StudioGraphModelPreview, StudioGraphModelRuntime, StudioGraphOwner } from './studioGraphTypes';

/** Code-owned, versioned projections. Provider metadata never grants execution authority. */
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的模型执行信息不可用，请重新读取。' }); }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function string(value: unknown, max = 240, empty = false): string {
  if (typeof value !== 'string' || value.length > max || (!empty && !value.trim()) || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function code(value: unknown): string { const result = string(value, 120); if (!/^[A-Z][A-Z0-9_]{0,119}$/.test(result)) invalid(); return result; }
function boolean(value: unknown): boolean { if (typeof value !== 'boolean') invalid(); return value; }
function integer(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid(); return value;
}
function nodeId(value: unknown): string { const result = string(value, 64); if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(result)) invalid(); return result; }
function digest(value: unknown): string { const result = string(value, 64); if (!/^[a-f0-9]{64}$/.test(result)) invalid(); return result; }
function reasons(value: unknown): string[] { if (!Array.isArray(value) || value.length > 128) invalid(); return value.map(code); }
function route(value: unknown): NonNullable<StudioGraphModelPreview['route']> {
  const row = object(value);
  return { route_id: digest(row.route_id), provider_id: string(row.provider_id), model_id: string(row.model_id), synthetic: boolean(row.synthetic), verification: code(row.verification) };
}

export function graphModelCapabilities(value: unknown, owner: (value: Record<string, unknown>) => StudioGraphOwner): StudioGraphModelCapabilities {
  const row = object(value), ownership = owner(row), api = object(row.api_provider), limits = object(row.limits);
  if (row.schema_version !== 1 || row.contract !== 'creative-graph-model/1' || row.adapter_owner !== 'TextModelNode'
    || row.router_owner !== 'ModelBroker' || row.scheduler_owner !== 'JobManager+WorkflowRun' || row.local_only !== true
    || row.automatic_fallback !== false || row.quality_verification !== 'NOT_RUN' || api.status !== 'RESERVED'
    || api.execution_available !== false || api.reason !== 'API_PROVIDER_EXECUTION_NOT_ENABLED'
    || limits.model_nodes !== 1 || limits.max_output_tokens !== 2048 || limits.timeout_seconds !== 180) invalid();
  if (!Array.isArray(row.routes) || row.routes.length > 128) invalid();
  const routes = row.routes.map(value => { const source = object(value); return { ...route(source), display_name: string(source.display_name),
    available: boolean(source.available), context_window: source.context_window === null ? null : integer(source.context_window, 1, Number.MAX_SAFE_INTEGER), reasons: reasons(source.reasons) }; });
  if (new Set(routes.map(item => item.route_id)).size !== routes.length) invalid();
  if (routes.some(item => item.available && item.reasons.length)) invalid();
  return { ...ownership, schema_version: 1, contract: 'creative-graph-model/1', adapter_owner: 'TextModelNode', router_owner: 'ModelBroker',
    scheduler_owner: 'JobManager+WorkflowRun', local_only: true, automatic_fallback: false, quality_verification: 'NOT_RUN', routes,
    ...(row.result_storage === undefined ? {} : { result_storage: graphTextResultStorage(row.result_storage) }),
    api_provider: { status: 'RESERVED', execution_available: false, reason: 'API_PROVIDER_EXECUTION_NOT_ENABLED' },
    limits: { model_nodes: 1, max_output_tokens: 2048, timeout_seconds: 180 } };
}

export function graphModelRuntime(value: unknown, hidePrivate: boolean): StudioGraphModelRuntime {
  const row = object(value), node = nodeId(row.node_id);
  const statuses: StudioGraphModelRuntime['status'][] = ['PENDING', 'AWAITING_PREVIEW', 'PREVIEWED', 'ADMITTED', 'UNKNOWN', 'RESULT_REVIEW', 'TERMINAL'];
  if (row.schema_version !== 1 || row.contract !== 'creative-graph-model/1' || !statuses.includes(row.status as StudioGraphModelRuntime['status'])
    || row.quality_verification !== 'NOT_RUN' || row.automatic_retry !== false || row.applied !== false) invalid();
  let preview: StudioGraphModelPreview | null = null, execution: StudioGraphModelExecution | null = null;
  if (row.preview !== null) {
    const source = object(row.preview), limits = object(source.limits);
    if (source.node_id !== node || source.model_called !== false || source.quality_verification !== 'NOT_RUN'
      || limits.max_output_bytes !== 32000 || limits.timeout_seconds !== 180) invalid();
    preview = { preview_digest: digest(source.preview_digest), node_id: node, input_digest: digest(source.input_digest), prompt: string(source.prompt, 32000, true),
      route: source.route === null ? null : route(source.route), execution_available: boolean(source.execution_available), reasons: reasons(source.reasons),
      limits: { max_output_bytes: 32000, max_output_tokens: integer(limits.max_output_tokens, 1, 2048), timeout_seconds: 180 }, model_called: false, quality_verification: 'NOT_RUN' };
    if (preview.execution_available && (!preview.route || preview.reasons.length)) invalid();
    if (new TextEncoder().encode(preview.prompt).length > 32000) invalid();
  }
  if (row.execution !== null) {
    const source = object(row.execution);
    if (!['RECORDED', 'UNKNOWN_NO_AUTOMATIC_REPLAY'].includes(source.receipt_state as string) || source.quality_verification !== 'NOT_RUN') invalid();
    execution = { job_id: string(source.job_id), status: code(source.status), receipt_state: source.receipt_state as StudioGraphModelExecution['receipt_state'],
      model_called: boolean(source.model_called), synthetic: boolean(source.synthetic), usage_state: code(source.usage_state),
      failure_code: source.failure_code === null ? null : code(source.failure_code), quality_verification: 'NOT_RUN' };
    if (preview?.route && preview.route.synthetic !== execution.synthetic) invalid();
  }
  if (['PENDING', 'AWAITING_PREVIEW'].includes(row.status as string) && (preview || execution)) invalid();
  if (row.status === 'PREVIEWED' && (execution || !hidePrivate && !preview)) invalid();
  if (['ADMITTED', 'UNKNOWN', 'RESULT_REVIEW'].includes(row.status as string) && !execution) invalid();
  if (row.status === 'UNKNOWN' && execution?.receipt_state !== 'UNKNOWN_NO_AUTOMATIC_REPLAY') invalid();
  if (row.status === 'ADMITTED' && execution?.receipt_state !== 'RECORDED') invalid();
  if (row.status === 'RESULT_REVIEW' && !execution?.model_called) invalid();
  return { schema_version: 1, contract: 'creative-graph-model/1', node_id: node, status: row.status as StudioGraphModelRuntime['status'],
    preview: hidePrivate ? null : preview, execution, quality_verification: 'NOT_RUN', automatic_retry: false, applied: false };
}
