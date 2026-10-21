import { checkedCanvasAudioTaskEnvelope } from '../canvasAudioTaskEnvelope';
import type { CanvasAudioTrimTaskBinding } from '../canvasAudioTrimTask';
import { checkedCanvasReturnBinding, sameCanvasReturn } from '../studioCanvasReturnBinding';
import type { MediaCommand, ProductionJob, ProductionSource } from '../studioProductionClient';

export type FailedCanvasAudioOrigin = {
  owner: 'audio'; job_id: string; job_version: number; request_id: string;
  request_digest: string; receipt_digest: string | null;
};
type PreservedTemplateReference = {
  contract: 'studio-canvas-audio-template/1'; graph_id: string; graph_version: number;
  definition_digest: string; execution_digest: string; node_id: string; parameters: { in_ms: number; out_ms: number };
};
export type DerivedCanvasAudioCommand = MediaCommand & { derived_from: FailedCanvasAudioOrigin; template_ref?: PreservedTemplateReference };
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const id = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const requestId = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v);
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const version = (v: unknown) => typeof v === 'number' && Number.isSafeInteger(v) && v > 0;
const keys = (v: object, allowed: string[]) => Reflect.ownKeys(v).every(k => typeof k === 'string' && allowed.includes(k));
const canonical = (v: unknown): string => JSON.stringify(v, (_k, x) => record(x)
  ? Object.fromEntries(Object.entries(x).sort(([a], [b]) => a.localeCompare(b))) : x);
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
function invalid(): never { throw new Error('仅能从原位置仍有效的 FAILED 本地音频截取记录派生新草稿；请重新读取原任务。'); }
function source(value: unknown, recorded = false): ProductionSource {
  if (!record(value) || !keys(value, ['id', 'kind', 'version', 'digest', 'asset_kind', ...(recorded ? ['reference_only'] : [])])
    || !id(value.id) || value.kind !== 'ASSET' || value.asset_kind !== 'audio' || !version(value.version) || !hex(value.digest)
    || Object.hasOwn(value, 'reference_only') && value.reference_only !== true) invalid();
  return { id: value.id, kind: 'ASSET', asset_kind: 'audio', version: value.version as number, digest: value.digest };
}

function checkedPriorOrigin(value: unknown): FailedCanvasAudioOrigin {
  if (!record(value) || !keys(value, ['owner', 'job_id', 'job_version', 'request_id', 'request_digest', 'receipt_digest'])
    || value.owner !== 'audio' || !id(value.job_id) || !version(value.job_version) || !requestId(value.request_id)
    || !hex(value.request_digest) || value.receipt_digest !== null && !hex(value.receipt_digest)) invalid();
  return { owner: 'audio', job_id: value.job_id, job_version: value.job_version as number,
    request_id: value.request_id, request_digest: value.request_digest, receipt_digest: value.receipt_digest };
}
function checkedTemplate(value: unknown): PreservedTemplateReference {
  if (!record(value) || !keys(value, ['contract', 'graph_id', 'graph_version', 'definition_digest', 'execution_digest', 'node_id', 'parameters'])
    || value.contract !== 'studio-canvas-audio-template/1' || !id(value.graph_id) || !version(value.graph_version)
    || !hex(value.definition_digest) || !hex(value.execution_digest) || !id(value.node_id)
    || !record(value.parameters) || !keys(value.parameters, ['in_ms', 'out_ms']) || !checkedCanvasAudioTaskEnvelope(value.parameters)) invalid();
  return { contract: 'studio-canvas-audio-template/1', graph_id: value.graph_id, graph_version: value.graph_version as number,
    definition_digest: value.definition_digest, execution_digest: value.execution_digest, node_id: value.node_id,
    parameters: { in_ms: value.parameters.in_ms as number, out_ms: value.parameters.out_ms as number } };
}

/** Pure draft derivation. It never replays the old request or admits/executes a Job. */
export function deriveFailedCanvasAudioCommand(job: ProductionJob, task: CanvasAudioTrimTaskBinding,
  newRequestId: string): DerivedCanvasAudioCommand {
  if (!task.isCurrent() || !requestId(newRequestId) || newRequestId === job.request_id
    || job.contract !== 'studio-production-job/1' || job.owner !== 'audio' || job.operation_id !== 'm8.audio.trim'
    || job.status !== 'FAILED' || job.provider !== null || !id(job.id) || !version(job.version)
    || !requestId(job.request_id) || !hex(job.request_digest) || job.receipt_digest !== null && !hex(job.receipt_digest)
    || job.automatic_replay !== false || job.remote_compute_may_continue !== false || job.needs_reconciliation === true
    || job.product_acceptance !== 'LOCAL_REQUIRED' || job.output_candidate !== null || job.approved_asset_version !== null
    || job.timeline_snapshot !== null || Object.hasOwn(job, 'canvas_video')) invalid();
  const command = job.command;
  if (!record(command) || !keys(command, ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters',
    'source_snapshots', 'allow_cloud', 'license_note', 'canvas_return', 'derived_from', 'template_ref'])
    || command.operation_id !== 'm8.audio.trim' || command.request_id !== job.request_id || command.provider_id != null
    || command.model_id != null || command.prompt !== '' || command.allow_cloud !== false
    || typeof command.license_note !== 'string' || command.license_note.length > 2000
    || !Array.isArray(command.source_snapshots) || command.source_snapshots.length !== 1
    || !Array.isArray(job.sources) || job.sources.length !== 1 || !task.returnBinding) invalid();
  const recorded = command as unknown as Record<string, unknown>;
  if (Object.hasOwn(command, 'derived_from')) {
    const previous = checkedPriorOrigin(recorded.derived_from);
    if (previous.job_id === job.id || previous.request_id === job.request_id) invalid();
  }
  const template = Object.hasOwn(command, 'template_ref') ? checkedTemplate(recorded.template_ref) : undefined;
  const parameters = checkedCanvasAudioTaskEnvelope(command.parameters, true);
  const pin = source(task.source), recordedSource = source(command.source_snapshots[0], true);
  const binding = checkedCanvasReturnBinding(task.returnBinding);
  if (!parameters || !same(pin, recordedSource) || !same(pin, source(job.sources[0], true))
    || !same(pin, binding.source) || binding.project_id !== job.novel_id
    || (binding.scope.mode === 'collaboration' ? binding.scope.branch_id : null) !== job.branch_id
    || !sameCanvasReturn({ ...command, canvas_return: binding }, command)) invalid();
  const recipe = job.execution_recipe;
  if (!record(recipe) || !keys(recipe, ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'output_profile'])
    || recipe.contract !== 'studio-execution-recipe/1' || recipe.operation_id !== command.operation_id
    || recipe.adapter !== 'LOCAL_FFMPEG' || recipe.automatic_fallback !== false || !hex(recipe.recipe_digest)
    || recipe.output_profile !== 'PCM_S16LE_WAV_48000_STEREO' || !same(recipe.parameters, parameters)) invalid();
  if (!task.isCurrent()) invalid();
  return { operation_id: 'm8.audio.trim', request_id: newRequestId, provider_id: null, model_id: null, prompt: '',
    parameters: { ...parameters }, source_snapshots: [pin], allow_cloud: false, license_note: command.license_note,
    canvas_return: binding, ...(template ? { template_ref: template } : {}), derived_from: { owner: 'audio', job_id: job.id, job_version: job.version,
      request_id: job.request_id, request_digest: job.request_digest, receipt_digest: job.receipt_digest } };
}
