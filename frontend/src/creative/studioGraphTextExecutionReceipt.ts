import { ApiError } from '../api';
import type { StudioGraphModelPreview } from './studioGraphTypes';
import type { StudioGraphTextAssetSource, StudioGraphTextExecutionReceipt } from './studioGraphTextAssetTypes';

const contract = 'creative-graph-text-execution/1';
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的文字执行回执不可用，请重新读取当前运行。' }); }
function exact(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== keys.length || keys.some(key => !Object.hasOwn(row, key))) invalid();
  return row;
}
function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 240 || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) invalid();
  return value;
}
function promptText(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 32000
    || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) invalid();
  // TextEncoder replaces unpaired surrogates; those are not an exact UTF-8 prompt.
  for (let index = 0; index < value.length; index++) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++index);
      if (!(next >= 0xdc00 && next <= 0xdfff)) invalid();
    } else if (unit >= 0xdc00 && unit <= 0xdfff) invalid();
  }
  if (new TextEncoder().encode(value).length > 32000) invalid();
  return value;
}
function utcStamp(value: unknown): string {
  const result = text(value);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(result)
    || !Number.isFinite(Date.parse(result)) || new Date(result).toISOString().slice(0, 19) !== result.slice(0, 19)) invalid();
  return result;
}

/** Data-only synchronous validation. The server verifies SHA-256 and persisted execution evidence;
 * the browser's existing digest helper is async, so digest strings here are not cryptographic proof. */
export function graphTextExecutionReceipt(value: unknown, asset: {
  provider_id: string; model_id: string; max_output_tokens: number; synthetic: boolean; source: StudioGraphTextAssetSource;
}, preview: StudioGraphModelPreview | null): StudioGraphTextExecutionReceipt {
  const row = exact(value, ['schema_version', 'contract', 'prompt', 'prompt_sha256', 'provider_id', 'model_id', 'route_id', 'route_fingerprint',
    'model_evidence', 'parameters', 'execution_mode', 'request_digest', 'workflow', 'terminal', 'quality_verification']);
  const evidence = exact(row.model_evidence, ['kind', 'model_fingerprint', 'runtime_fingerprint', 'runtime_version']);
  const parameters = exact(row.parameters, ['temperature', 'max_output_tokens', 'stop_sequences']);
  const workflow = exact(row.workflow, Object.keys(asset.source));
  const terminal = exact(row.terminal, ['status', 'settlement_id', 'settled_at']);
  if (row.schema_version !== 1 || row.contract !== contract || row.quality_verification !== 'NOT_RUN'
    || row.provider_id !== asset.provider_id || row.model_id !== asset.model_id
    || parameters.temperature !== 0 || parameters.max_output_tokens !== asset.max_output_tokens
    || !Number.isSafeInteger(parameters.max_output_tokens) || (parameters.max_output_tokens as number) < 1 || (parameters.max_output_tokens as number) > 2048
    || !Array.isArray(parameters.stop_sequences) || parameters.stop_sequences.length !== 0
    || Object.entries(asset.source).some(([key, expected]) => workflow[key] !== expected)
    || terminal.status !== 'COMPLETED' || terminal.settled_at !== asset.source.produced_at) invalid();
  if (asset.synthetic ? row.execution_mode !== 'mock_standin' || evidence.kind !== 'SYNTHETIC_PROTOCOL'
    || evidence.model_fingerprint !== 'synthetic-protocol-v1' || evidence.runtime_fingerprint !== null
    : row.execution_mode !== 'real' || evidence.kind !== 'MODEL_CENTER_METADATA') invalid();
  const prompt = promptText(row.prompt), routeId = digest(row.route_id);
  if (preview && (prompt !== preview.prompt || routeId !== preview.route?.route_id)) invalid();
  return {
    schema_version: 1, contract, prompt, prompt_sha256: digest(row.prompt_sha256), provider_id: text(row.provider_id), model_id: text(row.model_id),
    route_id: routeId, route_fingerprint: digest(row.route_fingerprint),
    model_evidence: { kind: asset.synthetic ? 'SYNTHETIC_PROTOCOL' : 'MODEL_CENTER_METADATA',
      model_fingerprint: asset.synthetic ? 'synthetic-protocol-v1' : digest(evidence.model_fingerprint),
      runtime_fingerprint: asset.synthetic ? null : digest(evidence.runtime_fingerprint),
      runtime_version: evidence.runtime_version === null ? null : text(evidence.runtime_version) },
    parameters: { temperature: 0, max_output_tokens: asset.max_output_tokens, stop_sequences: [] },
    execution_mode: asset.synthetic ? 'mock_standin' : 'real', request_digest: digest(row.request_digest), workflow: { ...asset.source },
    terminal: { status: 'COMPLETED', settlement_id: text(terminal.settlement_id), settled_at: utcStamp(terminal.settled_at) }, quality_verification: 'NOT_RUN',
  };
}
