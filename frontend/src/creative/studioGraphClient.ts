import { ApiError, type CollaborationContext } from '../api';
import type {
  StudioGraphAction, StudioGraphActionInput, StudioGraphCatalogDefinition, StudioGraphDefinition,
  StudioGraphDefinitionId, StudioGraphDraft, StudioGraphNode, StudioGraphOutput, StudioGraphParameters,
  StudioGraphParameterSchema, StudioGraphPort, StudioGraphPosition, StudioGraphPreflight,
  StudioGraphPreflightInput, StudioGraphCreateInput, StudioGraphSaveInput, StudioGraphRunCreateInput,
  StudioGraphRecord, StudioGraphReferenceState, StudioGraphRun, StudioGraphRunStatus, StudioGraphCatalog,
  StudioGraphScope, StudioGraphOwner, StudioGraphNodeState, StudioGraphNodeStatus,
  StudioGraphModelCapabilities, StudioGraphModelPreviewInput, StudioGraphModelDispatchInput, StudioGraphModelRefreshInput,
  StudioGraphAssetRef, StudioGraphMediaCandidate, StudioGraphMediaRuntime, StudioGraphMediaPreviewInput,
  StudioGraphMediaDispatchInput, StudioGraphMediaJobInput, StudioGraphMediaReviewInput,
  StudioGraphMediaPreview, StudioGraphMediaJob, StudioGraphMediaExecution,
} from './studioGraphTypes';
import type { MediaOperation, ProductionJob, ProductionPreview, RecordedMediaCommand, RecordedProductionSource, ProductionRecipe } from './studioProductionClient';
import { graphModelCapabilities, graphModelRuntime } from './studioGraphModelContract';
import { graphTextAssetOutput } from './studioGraphTextAssetContract';
import { createStudioProviderClient, type StudioProviderClient } from './studioProviderClient';

/** Inject the existing Studio transport; graph operations never look up credentials. */
export type StudioGraphTransport = {
  json<T>(url: string, method?: string, body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T>;
  blob?(url: string): Promise<Blob>;
};

const localDefinitionIds: readonly StudioGraphDefinitionId[] = ['text_input', 'text_reference', 'draft_prepare', 'manual_transform', 'director_note', 'human_review', 'asset_reference'];
const modelDefinitionIds: readonly StudioGraphDefinitionId[] = [...localDefinitionIds, 'text_generate'];
const mediaDefinitionIds: readonly StudioGraphDefinitionId[] = ['media_generate', 'media_review'];
const definitionIds: readonly StudioGraphDefinitionId[] = [...modelDefinitionIds, ...mediaDefinitionIds];
const statuses: readonly StudioGraphRunStatus[] = ['QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'PAUSED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'];
const nodeStatuses: readonly StudioGraphNodeStatus[] = ['PENDING', 'WAITING_APPROVAL', 'QUEUED', 'WORKING', 'SUCCEEDED', 'FAILED', 'SKIPPED', 'REJECTED'];
const actions: readonly StudioGraphAction[] = ['execute', 'approve', 'reject', 'cancel', 'pause', 'resume'];
const portKinds = ['TEXT', 'DIRECTOR_NOTES', 'DRAFT', 'ASSET_REF', 'MEDIA_CANDIDATE'] as const;
const parameterKeys: Record<StudioGraphDefinitionId, readonly string[]> = {
  text_input: ['text'], text_reference: [], draft_prepare: [], manual_transform: ['result'],
  director_note: ['note'], human_review: [], asset_reference: ['asset_id', 'version', 'digest', 'kind'],
  text_generate: ['instruction', 'max_output_tokens'],
  media_generate: ['operation_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'allow_cloud', 'license_note'], media_review: [],
};
const ports: Record<StudioGraphDefinitionId, { inputs: Record<string, string>; outputs: Record<string, string> }> = {
  text_input: { inputs: {}, outputs: { text: 'TEXT' } },
  text_reference: { inputs: { text: 'TEXT' }, outputs: { text: 'TEXT' } },
  draft_prepare: { inputs: { text: 'TEXT', direction: 'DIRECTOR_NOTES' }, outputs: { draft: 'DRAFT' } },
  manual_transform: { inputs: { text: 'TEXT', direction: 'DIRECTOR_NOTES' }, outputs: { draft: 'DRAFT' } },
  director_note: { inputs: {}, outputs: { direction: 'DIRECTOR_NOTES' } },
  human_review: { inputs: { draft: 'DRAFT' }, outputs: {} },
  asset_reference: { inputs: {}, outputs: { asset: 'ASSET_REF' } },
  text_generate: { inputs: { text: 'TEXT', direction: 'DIRECTOR_NOTES' }, outputs: { draft: 'DRAFT' } },
  media_generate: { inputs: { text: 'TEXT', source: 'ASSET_REF' }, outputs: { candidate: 'MEDIA_CANDIDATE' } },
  media_review: { inputs: { candidate: 'MEDIA_CANDIDATE' }, outputs: { asset: 'ASSET_REF' } },
};
const mediaOperations: readonly MediaOperation[] = ['m5.image.t2i', 'm5.image.i2i', 'm7.video.t2v', 'm7.video.i2v', 'm7.video.v2v',
  'm8.audio.speech', 'm8.audio.music', 'm8.audio.effects', 'm8.audio.trim'];
const mediaParameterKeys = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'];
const parametersForOperation: Record<MediaOperation, readonly string[]> = {
  'm5.image.t2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'],
  'm5.image.i2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'],
  'm7.video.t2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.i2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.v2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm8.audio.speech': ['voice_id', 'speech_rate'], 'm8.audio.music': ['duration_seconds', 'seed'],
  'm8.audio.effects': ['duration_seconds', 'seed'], 'm8.audio.trim': ['in_ms', 'out_ms'],
};

function invalid(input = false): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_GRAPH_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '节点图输入不完整，请核对定义、连接与版本。' : '服务返回的节点图数据不可用，请重新读取。' });
}
function mismatch(): never {
  throw new ApiError({ status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH', message: '返回内容与当前项目、分支或记录不一致，请重新读取。' });
}
function record(value: unknown, input = false): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(input);
  return value as Record<string, unknown>;
}
function text(value: unknown, maximum: number, input = false, empty = false): string {
  if (typeof value !== 'string' || value.length > maximum || (!empty && !value.trim())) invalid(input);
  return value;
}
function id(value: unknown, input = false): string {
  const result = text(value, 64, input);
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(result)) invalid(input);
  return result;
}
function resourceId(value: unknown, input = false): string {
  const result = text(value, 240, input);
  if (/[\u0000-\u001f\u007f]/.test(result)) invalid(input);
  return result;
}
function number(value: unknown, minimum: number, maximum: number, input = false): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || value > maximum) invalid(input);
  return value;
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER, input = false): number {
  const result = number(value, minimum, maximum, input);
  if (!Number.isSafeInteger(result)) invalid(input);
  return result;
}
function bool(value: unknown, input = false): boolean {
  if (typeof value !== 'boolean') invalid(input);
  return value;
}
function digest(value: unknown, input = false): string {
  const result = text(value, 64, input);
  if (!/^[a-f0-9]{64}$/.test(result)) invalid(input);
  return result;
}
function code(value: unknown): string {
  const result = text(value, 120);
  if (!/^[A-Z][A-Z0-9_]{0,119}$/.test(result)) invalid();
  return result;
}
function deadline(value: unknown): string {
  const result = text(value, 64);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(result)
    || !Number.isFinite(Date.parse(result))) invalid();
  return result;
}
function list(value: unknown, maximum: number, input = false): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalid(input);
  return value;
}
function uniqueIds(value: unknown, input = false): string[] {
  const result = list(value, 24, input).map(item => id(item, input));
  if (new Set(result).size !== result.length) invalid(input);
  return result;
}
function definitionId(value: unknown, input = false): StudioGraphDefinitionId {
  if (!definitionIds.includes(value as StudioGraphDefinitionId)) invalid(input);
  return value as StudioGraphDefinitionId;
}
function position(value: unknown, input = false): StudioGraphPosition {
  const row = record(value, input);
  return { x: number(row.x, -100_000, 100_000, input), y: number(row.y, -100_000, 100_000, input) };
}
function mediaOperation(value: unknown, input = false): MediaOperation {
  if (!mediaOperations.includes(value as MediaOperation)) invalid(input); return value as MediaOperation;
}
function mediaParameterValues(value: unknown, operation: MediaOperation, input = false): NonNullable<StudioGraphParameters['parameters']> {
  const row = record(value, input), result: NonNullable<StudioGraphParameters['parameters']> = {};
  if (Object.keys(row).some(key => !mediaParameterKeys.includes(key))) invalid(input);
  for (const [key, value] of Object.entries(row)) {
    if (value === null) { result[key] = null; continue; }
    if (!parametersForOperation[operation].includes(key)) invalid(input);
    if (key === 'negative_prompt') result[key] = text(value, 8000, input, true);
    else if (key === 'voice_id') result[key] = resourceId(value, input);
    else if (key === 'size' || key === 'quality') {
      const options = key === 'size' ? ['auto', '1024x1024', '1536x1024', '1024x1536'] : ['auto', 'low', 'medium', 'high', 'standard', 'hd'];
      if (!options.includes(value as string)) invalid(input); result[key] = value as string;
    } else if (key === 'speech_rate') result[key] = number(value, 0.5, 2, input);
    else {
      const ranges: Record<string, [number, number]> = { width: [64, 2048], height: [64, 2048], steps: [1, 150], seed: [0, 2147483647],
        duration_seconds: [1, 600], frame_rate: [1, 60], in_ms: [0, 600000], out_ms: [1, 600000] };
      const range = ranges[key]; if (!range) invalid(input); result[key] = integer(value, range[0], range[1], input);
      if (operation.startsWith('m5.') && ['width', 'height'].includes(key) && Number(result[key]) % 8 !== 0) invalid(input);
    }
  }
  if ((result.width != null) !== (result.height != null)) invalid(input);
  if (operation === 'm8.audio.trim' && (typeof result.in_ms !== 'number' || typeof result.out_ms !== 'number' || result.out_ms <= result.in_ms || result.out_ms - result.in_ms > 120000)) invalid(input);
  return result;
}
function parameters(value: unknown, kind: StudioGraphDefinitionId, input = false, unavailable = false): StudioGraphParameters {
  const row = record(value, input);
  // Redacted references never expose identifiers even if a malformed response includes them.
  if (unavailable && kind === 'asset_reference') return {};
  if (kind === 'text_input') return { text: text(row.text, 8_000, input, true) };
  if (kind === 'manual_transform') return { result: text(row.result, 8_000, input, true) };
  if (kind === 'director_note') return { note: text(row.note, 4_000, input, true) };
  if (kind === 'text_generate') return { instruction: text(row.instruction, 4_000, input, true), max_output_tokens: integer(row.max_output_tokens, 1, 2_048, input) };
  if (kind === 'asset_reference') {
    if (!['image', 'video', 'audio'].includes(row.kind as string)) invalid(input);
    return { asset_id: resourceId(row.asset_id, input), version: integer(row.version, 1, Number.MAX_SAFE_INTEGER, input),
      digest: digest(row.digest, input), kind: row.kind as 'image' | 'video' | 'audio' };
  }
  if (kind === 'media_generate') {
    if (Object.keys(row).some(key => !parameterKeys[kind].includes(key))) invalid(input);
    const operation = mediaOperation(row.operation_id, input), trim = operation === 'm8.audio.trim';
    const provider = row.provider_id == null ? null : resourceId(row.provider_id, input), model = row.model_id == null ? null : resourceId(row.model_id, input);
    const prompt = text(row.prompt ?? '', 16000, input, true), allowCloud = bool(row.allow_cloud ?? false, input);
    if (trim ? provider !== null || model !== null || prompt !== '' || allowCloud : provider === null || model === null) invalid(input);
    return { operation_id: operation, provider_id: provider, model_id: model, prompt,
      parameters: mediaParameterValues(row.parameters ?? {}, operation, input), allow_cloud: allowCloud, license_note: text(row.license_note ?? '', 2000, input, true) };
  }
  return {};
}
function definition(value: unknown, input = false, unavailable = new Set<string>()): StudioGraphDefinition {
  const row = record(value, input);
  if (row.schema_version !== 1 && row.schema_version !== 2 && row.schema_version !== 3) invalid(input);
  const nodes: StudioGraphNode[] = list(row.nodes, row.schema_version === 3 ? 24 : 16, input).map(item => {
    const node = record(item, input), nodeId = id(node.id, input), kind = definitionId(node.definition_id, input);
    if (kind === 'text_generate' && row.schema_version === 1 || mediaDefinitionIds.includes(kind) && row.schema_version !== 3) invalid(input);
    if (node.definition_version !== 1) invalid(input);
    return { id: nodeId, definition_id: kind, definition_version: 1, enabled: bool(node.enabled, input),
      position: position(node.position, input), parameters: parameters(node.parameters, kind, input, unavailable.has(nodeId)) };
  });
  const nodeMap = new Map(nodes.map(node => [node.id, node]));
  if (nodeMap.size !== nodes.length) invalid(input);
  const targets = new Set<string>(), edgeIds = new Set<string>();
  const edges = list(row.edges, 40, input).map(item => {
    const edge = record(item, input);
    const result = { id: id(edge.id, input), source_node_id: id(edge.source_node_id, input), source_port: id(edge.source_port, input),
      target_node_id: id(edge.target_node_id, input), target_port: id(edge.target_port, input) };
    const source = nodeMap.get(result.source_node_id), target = nodeMap.get(result.target_node_id);
    if (!source || !target || edgeIds.has(result.id)) invalid(input);
    const sourcePorts = ports[source.definition_id].outputs, targetPorts = ports[target.definition_id].inputs;
    if (!Object.hasOwn(sourcePorts, result.source_port) || !Object.hasOwn(targetPorts, result.target_port)) invalid(input);
    const outputType = sourcePorts[result.source_port], inputType = targetPorts[result.target_port];
    if (!outputType || !inputType || outputType !== inputType) invalid(input);
    const targetKey = `${result.target_node_id}:${result.target_port}`;
    if (targets.has(targetKey)) invalid(input);
    targets.add(targetKey); edgeIds.add(result.id);
    return result;
  });
  // Reject cycles before sending, without executing or dynamically importing any node.
  const active = new Set<string>(), done = new Set<string>();
  function visit(nodeId: string): void {
    if (active.has(nodeId)) invalid(input);
    if (done.has(nodeId)) return;
    active.add(nodeId);
    edges.filter(edge => edge.source_node_id === nodeId).forEach(edge => visit(edge.target_node_id));
    active.delete(nodeId); done.add(nodeId);
  }
  nodes.forEach(node => visit(node.id));
  const viewport = record(row.viewport, input);
  const result: StudioGraphDefinition = { schema_version: row.schema_version, title: text(row.title, 160, input), nodes, edges,
    viewport: { ...position(viewport, input), zoom: number(viewport.zoom, 0.35, 2.5, input) } };
  if (new TextEncoder().encode(JSON.stringify(result)).length > 96_000) invalid(input);
  return result;
}

function schema(value: unknown, kind: StudioGraphDefinitionId): StudioGraphParameterSchema {
  const row = record(value), properties = record(row.properties);
  if (row.type !== 'object' || row.additionalProperties !== false) invalid();
  if (kind === 'media_generate') {
    if (JSON.stringify(row).length > 100000 || Object.keys(properties).length !== parameterKeys[kind].length
      || Object.keys(properties).some(key => !parameterKeys[kind].includes(key))) invalid();
    const operation = record(properties.operation_id);
    if (operation.type !== 'string' || !Array.isArray(operation.enum) || operation.enum.length !== mediaOperations.length
      || operation.enum.some(item => !mediaOperations.includes(item as MediaOperation))) invalid();
    // This is a bounded display projection. The executable parameter validator above is code-owned.
    return { type: 'object', additionalProperties: false, properties: {
      operation_id: { type: 'string', enum: [...mediaOperations] }, provider_id: { type: 'string', maxLength: 240 },
      model_id: { type: 'string', maxLength: 240 }, prompt: { type: 'string', maxLength: 16000, default: '' },
      parameters: { type: 'object', default: {} }, allow_cloud: { type: 'boolean', default: false }, license_note: { type: 'string', maxLength: 2000, default: '' },
    }, required: ['operation_id'] };
  }
  const result: StudioGraphParameterSchema = { type: 'object', additionalProperties: false, properties: {} };
  for (const key of parameterKeys[kind]) {
    const field = record(properties[key]);
    if (field.type !== 'string' && field.type !== 'integer') invalid();
    const safe: StudioGraphParameterSchema['properties'][string] = { type: field.type };
    if (field.title !== undefined) safe.title = text(field.title, 160);
    if (field.default !== undefined) safe.default = field.type === 'integer' ? integer(field.default, 1, 2_048) : text(field.default, 8_000, false, true);
    if (field.minLength !== undefined) safe.minLength = integer(field.minLength, 0, 8_000);
    if (field.maxLength !== undefined) safe.maxLength = integer(field.maxLength, 0, 8_000);
    if (field.minimum !== undefined) safe.minimum = integer(field.minimum);
    if (field.maximum !== undefined) safe.maximum = integer(field.maximum);
    if (field.pattern !== undefined) safe.pattern = text(field.pattern, 240);
    if (field.enum !== undefined) safe.enum = list(field.enum, 8).map(item => text(item, 64));
    result.properties[key] = safe;
  }
  if (row.title !== undefined) result.title = text(row.title, 160);
  if (row.required !== undefined) {
    result.required = list(row.required, 4).map(item => {
      const key = text(item, 64);
      if (!parameterKeys[kind].includes(key)) invalid();
      return key;
    });
  }
  return result;
}
function catalogDefinition(value: unknown, mediaEnabled = false): StudioGraphCatalogDefinition {
  const row = record(value), kind = definitionId(row.id);
  const executable = mediaEnabled || kind !== 'asset_reference';
  if (row.version !== 1 || row.model_called !== false || row.executable !== executable) invalid();
  function checkedPorts(value: unknown, side: 'inputs' | 'outputs'): StudioGraphPort[] {
    const expected = ports[kind][side];
    const result = list(value, 2).map(item => {
      const port = record(item), portId = id(port.id), required = bool(port.required);
      if (!portKinds.includes(port.type as StudioGraphPort['type']) || expected[portId] !== port.type || port.multiple !== false) invalid();
      if (required !== (side === 'inputs' && portId !== 'direction' && kind !== 'media_generate')) invalid();
      return { id: portId, type: port.type as StudioGraphPort['type'], required, multiple: false as const };
    });
    if (new Set(result.map(port => port.id)).size !== Object.keys(expected).length || result.length !== Object.keys(expected).length) invalid();
    return result;
  }
  if ((kind === 'asset_reference' || kind === 'media_generate') && row.default_parameters !== null) invalid();
  return { id: kind, version: 1, inputs: checkedPorts(row.inputs, 'inputs'), outputs: checkedPorts(row.outputs, 'outputs'),
    parameters_schema: schema(row.parameters_schema, kind),
    default_parameters: kind === 'asset_reference' || kind === 'media_generate' ? null : parameters(row.default_parameters, kind),
    executable, model_called: false, blockers: list(row.blockers, 16).map(code) };
}

function draft(value: unknown, allowModel = false): StudioGraphDraft {
  const row = record(value);
  if (row.origin !== 'USER_SUPPLIED' && row.origin !== 'MANUAL' && !(allowModel && row.origin === 'MODEL_PROPOSAL')) invalid();
  const result: StudioGraphDraft = { text: text(row.text, 8_000, false, true), origin: row.origin };
  if (row.origin === 'MODEL_PROPOSAL' && row.plan !== undefined) invalid();
  if (row.plan !== undefined) result.plan = list(row.plan, 1_000).map(item => {
    const beat = record(item);
    return { sequence: integer(beat.sequence, 1, 1_000), beat: text(beat.beat, 8_000, false, true) };
  });
  if (row.direction !== undefined) result.direction = { note: text(record(row.direction).note, 4_000, false, true) };
  return result;
}
function output(value: unknown, allowModel = false): StudioGraphOutput | null {
  if (value === null) return null;
  const row = record(value), result: StudioGraphOutput = {};
  if (row.text !== undefined) result.text = text(row.text, 8_000, false, true);
  if (row.direction !== undefined) result.direction = { note: text(record(row.direction).note, 4_000, false, true) };
  if (row.draft !== undefined) result.draft = draft(row.draft, allowModel);
  if (row.asset !== undefined) result.asset = assetReference(row.asset);
  if (row.candidate !== undefined) {
    const candidate = record(row.candidate);
    if (!['image', 'video', 'audio'].includes(candidate.owner as string) || Object.keys(candidate).some(key => !['owner', 'job_id', 'job_version', 'request_digest', 'asset'].includes(key))) invalid();
    result.candidate = { owner: candidate.owner as StudioGraphMediaCandidate['owner'], job_id: resourceId(candidate.job_id),
      job_version: integer(candidate.job_version, 1), request_digest: digest(candidate.request_digest), asset: assetReference(candidate.asset) };
  }
  if (new TextEncoder().encode(JSON.stringify(result)).length > 64_000) invalid();
  return result;
}
function assetReference(value: unknown): StudioGraphAssetRef {
  const row = record(value);
  if (!['image', 'video', 'audio'].includes(row.kind as string) || Object.keys(row).some(key => !['asset_id', 'version', 'digest', 'kind'].includes(key))) invalid();
  return { asset_id: resourceId(row.asset_id), version: integer(row.version, 1), digest: digest(row.digest), kind: row.kind as StudioGraphAssetRef['kind'] };
}
const mediaJobStatuses: readonly ProductionJob['status'][] = ['QUEUED', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY',
  'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED', 'UNKNOWN', 'FAILED', 'CANCELLED'];
function closed(row: Record<string, unknown>, keys: readonly string[]): void { if (Object.keys(row).some(key => !keys.includes(key))) invalid(); }
function mediaSource(value: unknown): RecordedProductionSource {
  const row = record(value); closed(row, ['id', 'kind', 'version', 'digest', 'asset_kind', 'reference_only']);
  if (row.reference_only !== undefined && row.reference_only !== true) invalid();
  const base = { id: resourceId(row.id), version: integer(row.version, 1), digest: digest(row.digest),
    ...(row.reference_only === true ? { reference_only: true as const } : {}) };
  if (row.kind === 'CREATIVE_DOCUMENT' && row.asset_kind === undefined) return { ...base, kind: 'CREATIVE_DOCUMENT' };
  if (row.kind !== 'ASSET' || !['image', 'video', 'audio'].includes(row.asset_kind as string)) invalid();
  return { ...base, kind: 'ASSET', asset_kind: row.asset_kind as 'image' | 'video' | 'audio' };
}
function recordedMediaCommand(value: unknown): RecordedMediaCommand {
  const row = record(value); closed(row, ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note']);
  const operation = mediaOperation(row.operation_id), resolved = mediaParameterValues(row.parameters, operation);
  const requestId = text(row.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) invalid();
  const sourceSnapshots = list(row.source_snapshots, 8).map(mediaSource);
  if (sourceSnapshots.some(source => source.kind !== 'ASSET')) invalid();
  return { operation_id: operation, request_id: requestId, provider_id: row.provider_id == null ? null : resourceId(row.provider_id),
    model_id: row.model_id == null ? null : resourceId(row.model_id), prompt: text(row.prompt, 16000, false, true),
    parameters: Object.fromEntries(Object.entries(resolved).filter((item): item is [string, string | number] => item[1] !== null)),
    source_snapshots: sourceSnapshots, allow_cloud: bool(row.allow_cloud), license_note: text(row.license_note, 2000, false, true) };
}
function productionRecipe(value: unknown, operation: string): ProductionRecipe {
  const row = record(value); closed(row, ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'workflow', 'defaults', 'denoising_strength', 'output_profile', 'timeline']);
  if (row.contract !== 'studio-execution-recipe/1' || row.operation_id !== operation || row.automatic_fallback !== false
    || !['ORIGINAL_HTTP_PROVIDER', 'COMFYUI_BUILTIN_IMAGE', 'AUTOMATIC1111_IMAGE', 'LOCAL_FFMPEG'].includes(row.adapter as string)
    || JSON.stringify(row).length > 131072) invalid();
  digest(row.recipe_digest);
  return row as ProductionRecipe;
}
function productionPreview(value: unknown, projectId: string, branchId: string | null): ProductionPreview {
  const row = record(value); closed(row, ['contract', 'novel_id', 'branch_id', 'request_id', 'operation_id', 'preview_digest', 'request_digest', 'command', 'provider',
    'execution_recipe', 'sources', 'product_acceptance', 'execution_available', 'automatic_dispatch', 'output_policy']);
  if (row.novel_id !== projectId || (row.branch_id ?? null) !== branchId) mismatch();
  const command = recordedMediaCommand(row.command), operation = mediaOperation(row.operation_id);
  if (row.contract !== 'studio-production-preview/1' || row.request_id !== command.request_id || operation !== command.operation_id
    || row.product_acceptance !== 'LOCAL_REQUIRED' || row.execution_available !== true || row.automatic_dispatch !== false
    || row.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW') invalid();
  let provider: ProductionPreview['provider'] = null;
  if (row.provider !== null) {
    const p = record(row.provider); closed(p, ['provider_id', 'model_id', 'local', 'route_digest']);
    provider = { provider_id: resourceId(p.provider_id), model_id: resourceId(p.model_id), local: bool(p.local), route_digest: digest(p.route_digest) };
    if (provider.provider_id !== command.provider_id || provider.model_id !== command.model_id) invalid();
  }
  if ((operation === 'm8.audio.trim') !== (provider === null)) invalid();
  const measuredSources = list(row.sources, 8);
  if (measuredSources.length !== command.source_snapshots.length) invalid();
  measuredSources.forEach((value, index) => { const evidence = record(value); closed(evidence, ['snapshot', 'measured']); const snapshot = mediaSource(evidence.snapshot);
    const expected = command.source_snapshots[index]; if (['id', 'kind', 'version', 'digest', 'asset_kind'].some(key =>
      (snapshot as Record<string, unknown>)[key] !== (expected as Record<string, unknown>)[key])) invalid(); });
  // Project a checked command instead of retaining unknown response keys or nullable parameters.
  return { contract: 'studio-production-preview/1', novel_id: projectId, branch_id: branchId, operation_id: operation, request_id: command.request_id,
    command: command as ProductionPreview['command'], provider, preview_digest: digest(row.preview_digest), request_digest: digest(row.request_digest),
    execution_recipe: productionRecipe(row.execution_recipe, operation), product_acceptance: 'LOCAL_REQUIRED', execution_available: true,
    automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
}
function mediaJob(value: unknown): StudioGraphMediaJob {
  const row = record(value); closed(row, ['id', 'version', 'status', 'request_digest', 'receipt_digest', 'output_candidate', 'approved_asset_version', 'error_code',
    'needs_reconciliation', 'execution_state', 'cancellation_mode', 'remote_compute_may_continue']);
  if (!mediaJobStatuses.includes(row.status as ProductionJob['status'])) invalid();
  let candidate: ProductionJob['output_candidate'] = null;
  if (row.output_candidate !== null) {
    const c = record(row.output_candidate); closed(c, ['id', 'version', 'digest', 'kind']);
    if (!['image', 'video', 'audio'].includes(c.kind as string)) invalid();
    candidate = { id: resourceId(c.id), version: integer(c.version, 1), digest: digest(c.digest), kind: c.kind as 'image' | 'video' | 'audio' };
  }
  return { id: resourceId(row.id), version: integer(row.version, 1), status: row.status as ProductionJob['status'], request_digest: digest(row.request_digest),
    receipt_digest: row.receipt_digest == null ? null : digest(row.receipt_digest), output_candidate: candidate,
    approved_asset_version: row.approved_asset_version == null ? null : integer(row.approved_asset_version, 1),
    ...(row.error_code === undefined ? {} : { error_code: row.error_code === null ? null : code(row.error_code) }),
    ...(row.needs_reconciliation == null ? {} : { needs_reconciliation: bool(row.needs_reconciliation) }),
    ...(row.execution_state == null ? {} : { execution_state: code(row.execution_state) }),
    ...(row.cancellation_mode == null ? {} : { cancellation_mode: code(row.cancellation_mode) }), remote_compute_may_continue: bool(row.remote_compute_may_continue) };
}
function graphMediaRuntime(value: unknown, projectId: string, branchId: string | null, hidePrivate: boolean): StudioGraphMediaRuntime {
  const row = record(value); closed(row, ['schema_version', 'contract', 'nodes', 'product_acceptance', 'automatic_retry', 'automatic_poll', 'applied']);
  if (row.schema_version !== 1 || row.contract !== 'creative-graph-media/1' || row.product_acceptance !== 'LOCAL_REQUIRED'
    || row.automatic_retry !== false || row.automatic_poll !== false || row.applied !== false) invalid();
  const executionStatuses = [...mediaJobStatuses, 'ADMISSION_RESERVED', 'ADMISSION_UNKNOWN', 'JOB_NOT_FOUND'];
  const nodes = list(row.nodes, 4).map(value => {
    const source = record(value); closed(source, ['node_id', 'status', 'preview', 'execution']);
    const nodeId = id(source.node_id), status = code(source.status);
    if (![...executionStatuses, 'PENDING', 'AWAITING_PREVIEW', 'STALE'].includes(status)) invalid();
    let preview: StudioGraphMediaPreview | null = null, execution: StudioGraphMediaExecution | null = null;
    if (source.preview !== null) {
      const p = record(source.preview); closed(p, ['node_id', 'input_digest', 'preview_digest', 'command', 'production_preview']);
      if (p.node_id !== nodeId) invalid();
      const command = recordedMediaCommand(p.command), production = productionPreview(p.production_preview, projectId, branchId), captured = production.command;
      if (command.operation_id !== captured.operation_id || command.request_id !== captured.request_id || command.prompt !== captured.prompt
        || command.provider_id !== captured.provider_id || command.model_id !== captured.model_id || command.allow_cloud !== captured.allow_cloud || command.license_note !== captured.license_note
        || JSON.stringify(command.source_snapshots) !== JSON.stringify(captured.source_snapshots)
        || Object.entries(command.parameters).some(([key, value]) => captured.parameters[key] !== value)) invalid();
      preview = { node_id: nodeId, input_digest: digest(p.input_digest), preview_digest: digest(p.preview_digest), command, production_preview: production };
    }
    if (source.execution !== null) {
      const e = record(source.execution); closed(e, ['node_id', 'owner', 'job_id', 'status', 'receipt_state', 'send_reserved', 'job', 'review_state']);
      if (e.node_id !== nodeId || !['image', 'video', 'audio'].includes(e.owner as string) || !executionStatuses.includes(e.status as ProductionJob['status'])
        || !['RECORDED', 'UNKNOWN_NO_AUTOMATIC_REPLAY'].includes(e.receipt_state as string) || !['NONE', 'REVIEW_RESERVED', 'APPROVED'].includes(e.review_state as string)) invalid();
      const jobId = e.job_id === null ? null : resourceId(e.job_id), job = e.job === null ? null : mediaJob(e.job);
      if (job && job.id !== jobId || job && preview && job.request_digest !== preview.production_preview.request_digest) invalid();
      const expectedOwner = preview?.command.operation_id.startsWith('m5.') ? 'image' : preview?.command.operation_id.startsWith('m7.') ? 'video' : 'audio';
      if (preview && e.owner !== expectedOwner) invalid();
      execution = { node_id: nodeId, owner: e.owner as StudioGraphMediaExecution['owner'], job_id: jobId, status: code(e.status),
        receipt_state: e.receipt_state as StudioGraphMediaExecution['receipt_state'], send_reserved: bool(e.send_reserved),
        job: hidePrivate ? null : job, review_state: e.review_state as StudioGraphMediaExecution['review_state'] };
    }
    if (!execution && !['PENDING', 'AWAITING_PREVIEW', 'STALE'].includes(status)) invalid();
    return { node_id: nodeId, status, preview: hidePrivate ? null : preview, execution };
  });
  if (new Set(nodes.map(node => node.node_id)).size !== nodes.length) invalid();
  return { schema_version: 1, contract: 'creative-graph-media/1', nodes, product_acceptance: 'LOCAL_REQUIRED', automatic_retry: false, automatic_poll: false, applied: false };
}
function runStatus(value: unknown): StudioGraphRunStatus {
  if (!statuses.includes(value as StudioGraphRunStatus)) invalid();
  return value as StudioGraphRunStatus;
}

function catalog(value: unknown): StudioGraphCatalog {
  const row = record(value), limits = record(row.limits), capabilities = record(row.capabilities);
  const expectedLimits: StudioGraphCatalog['limits'] = { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 };
  const expectedCapabilities: StudioGraphCatalog['capabilities'] = {
    local_execution: true, chapter_required: false, model_execution: false, external_reference_execution: false,
    external_reference_detach: false, binary_cache: false, parallel_execution: false, automatic_retry: false,
    actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY',
  };
  const modelEnabled = capabilities.model_execution === true;
  const mediaEnabled = capabilities.media_execution === true;
  if (modelEnabled) {
    if (capabilities.model_execution_contract !== 'creative-graph-model/1') invalid();
    expectedCapabilities.model_execution = true;
    expectedCapabilities.model_execution_contract = 'creative-graph-model/1';
  } else if (capabilities.model_execution_contract !== undefined) invalid();
  if (mediaEnabled) {
    if (capabilities.media_execution_contract !== 'creative-graph-media/1') invalid();
    expectedCapabilities.media_execution = true; expectedCapabilities.media_execution_contract = 'creative-graph-media/1';
    expectedCapabilities.external_reference_execution = true;
  } else if (capabilities.media_execution_contract !== undefined) invalid();
  if (Object.entries(expectedLimits).some(([key, value]) => limits[key] !== value)
    || Object.entries(expectedCapabilities).some(([key, value]) => capabilities[key] !== value)) invalid();
  const definitions = list(row.definitions, definitionIds.length).map(item => catalogDefinition(item, mediaEnabled));
  const expectedDefinitions = [...(modelEnabled ? modelDefinitionIds : localDefinitionIds), ...(mediaEnabled ? mediaDefinitionIds : [])];
  if (definitions.length !== expectedDefinitions.length || new Set(definitions.map(item => item.id)).size !== definitions.length
    || definitions.some(item => !expectedDefinitions.includes(item.id))) invalid();
  let mediaLimits: StudioGraphCatalog['media_limits'];
  if (mediaEnabled) {
    const value = record(row.media_limits); if (value.nodes !== 24 || value.generators !== 4 || value.history !== 80) invalid();
    mediaLimits = { nodes: 24, generators: 4, history: 80 };
  } else if (row.media_limits !== undefined) invalid();
  return { definitions, limits: expectedLimits, capabilities: expectedCapabilities, ...(mediaLimits ? { media_limits: mediaLimits } : {}) };
}

export function createStudioGraphClient(projectId: string, context: Pick<CollaborationContext, 'scope'>, transport: StudioGraphTransport) {
  const capturedScope = context.scope ? { ...context.scope } : undefined;
  const originalTransport = transport;
  const admitted = () => { if (capturedScope && capturedScope.projectId !== projectId) mismatch(); };
  transport = {
    json<T>(url: string, method?: string, body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T> {
      admitted(); return originalTransport.json<T>(url, method, body, signal, idempotencyKey);
    },
    ...(originalTransport.blob ? { blob: (url: string) => { admitted(); return originalTransport.blob!(url); } } : {}),
  };
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
  const graphUrl = (value: unknown) => `${base}/graphs/${encodeURIComponent(resourceId(value, true))}`;
  const runUrl = (value: unknown) => `${base}/graph-runs/${encodeURIComponent(resourceId(value, true))}`;
  const observedGraphs = new Map<string, { version: number; can_edit: boolean; enabledIds: string[]; definition_digest: string }>();
  const observedRuns = new Map<string, string>();

  function owner(row: Record<string, unknown>): StudioGraphOwner {
    if (row.project_id !== projectId) mismatch();
    const source = record(row.scope);
    if (source.novel_id !== projectId || source.mode !== (capturedScope ? 'collaboration' : 'local')) mismatch();
    let scope: StudioGraphScope;
    if (capturedScope) {
      if (source.workspace_id !== capturedScope.workspaceId || source.storyline_id !== capturedScope.storylineId
        || source.branch_id !== capturedScope.branchId || capturedScope.projectId !== projectId) mismatch();
      scope = { mode: 'collaboration', novel_id: projectId, workspace_id: capturedScope.workspaceId,
        storyline_id: capturedScope.storylineId, branch_id: capturedScope.branchId };
    } else {
      if (source.workspace_id != null || source.storyline_id != null || source.branch_id != null) mismatch();
      scope = { mode: 'local', novel_id: projectId };
    }
    return { project_id: projectId, scope };
  }
  function checkedGraph(value: unknown, expectedId?: string): StudioGraphRecord {
    const row = record(value), ownership = owner(row), graphId = resourceId(row.id);
    if (expectedId !== undefined && expectedId !== graphId) mismatch();
    const referenceStates: StudioGraphReferenceState[] = list(row.reference_states, 24).map(item => {
      const state = record(item);
      if (!['CURRENT', 'STALE', 'UNAVAILABLE'].includes(state.state as string)) invalid();
      return { node_id: id(state.node_id), state: state.state as StudioGraphReferenceState['state'] };
    });
    if (new Set(referenceStates.map(item => item.node_id)).size !== referenceStates.length) invalid();
    const unavailable = new Set(referenceStates.filter(item => item.state === 'UNAVAILABLE').map(item => item.node_id));
    const checkedDefinition = definition(row.definition, false, unavailable);
    const assetNodes = checkedDefinition.nodes.filter(node => node.definition_id === 'asset_reference');
    if (assetNodes.length !== referenceStates.length || referenceStates.some(item => !assetNodes.some(node => node.id === item.node_id))) invalid();
    const canEdit = bool(row.can_edit);
    // Even a misconfigured server cannot turn an incomplete public projection into a writable graph.
    const result: StudioGraphRecord = { ...ownership, id: graphId, version: integer(row.version, 1), definition: checkedDefinition,
      definition_digest: digest(row.definition_digest), execution_digest: digest(row.execution_digest),
      created_at: text(row.created_at, 64), updated_at: text(row.updated_at, 64), can_edit: canEdit && unavailable.size === 0,
      reference_states: referenceStates };
    return result;
  }
  function rememberGraph(value: StudioGraphRecord): StudioGraphRecord {
    const previous = observedGraphs.get(value.id);
    if (!previous || previous.version <= value.version) observedGraphs.set(value.id, {
      version: value.version, can_edit: value.can_edit, enabledIds: value.definition.nodes.filter(node => node.enabled).map(node => node.id),
      definition_digest: value.definition_digest,
    });
    return value;
  }
  function checkedPreflight(value: unknown, graphId: string, input: StudioGraphPreflightInput): StudioGraphPreflight {
    const row = record(value), ownership = owner(row);
    if (row.graph_id !== graphId) mismatch();
    if (row.valid !== true || row.model_called !== false || row.external_calls !== 0) invalid();
    const expectedVersion = integer(row.expected_version, 1), targetIds = uniqueIds(row.target_node_ids);
    const observed = observedGraphs.get(graphId);
    const expectedTargets = input.target_node_ids.length ? input.target_node_ids
      : observed?.version === input.expected_version ? observed.enabledIds : undefined;
    if (expectedVersion !== input.expected_version || (expectedTargets && (targetIds.length !== expectedTargets.length
      || targetIds.some(target => !expectedTargets.includes(target))))) invalid();
    const issues = list(row.issues, 128).map(item => {
      const issue = record(item);
      return { code: code(issue.code), ...(issue.node_id === undefined ? {} : { node_id: id(issue.node_id) }) };
    });
    const executionOrder = uniqueIds(row.execution_order), closure = uniqueIds(row.selected_closure);
    const definitionDigest = digest(row.definition_digest), executable = bool(row.executable);
    if (executable !== (issues.length === 0) || executionOrder.length !== closure.length
      || executionOrder.some((nodeId, index) => nodeId !== closure[index]) || targetIds.some(nodeId => !closure.includes(nodeId))
      || (observed?.version === expectedVersion && observed.definition_digest !== definitionDigest)) invalid();
    return { ...ownership, graph_id: graphId, valid: true, executable, issues,
      execution_order: executionOrder, selected_closure: closure,
      definition_digest: definitionDigest, preflight_digest: digest(row.preflight_digest),
      expected_version: expectedVersion, target_node_ids: targetIds, model_called: false, external_calls: 0 };
  }
  function checkedRun(value: unknown, expectedId?: string, expectedGraphId?: string): StudioGraphRun {
    const row = record(value), ownership = owner(row), runId = resourceId(row.id), graphId = resourceId(row.graph_id);
    if ((expectedId !== undefined && expectedId !== runId) || (expectedGraphId !== undefined && expectedGraphId !== graphId)) mismatch();
    if (row.external_calls !== 0 || row.applied !== false || row.timeout_seconds !== 3600) invalid();
    const stale = bool(row.stale), status = runStatus(row.status), hideOutputs = stale || ['CANCELLED', 'REJECTED', 'FAILED'].includes(status);
    const model = row.model_runtime === undefined ? undefined : graphModelRuntime(row.model_runtime, hideOutputs);
    const media = row.media_runtime === undefined ? undefined : graphMediaRuntime(row.media_runtime, projectId, capturedScope?.branchId ?? null,
      hideOutputs);
    const modelCalled = bool(row.model_called);
    if (model ? modelCalled !== (model.execution?.model_called ?? false) : modelCalled) invalid();
    const modelOutput = modelCalled && !!model && ['RESULT_REVIEW', 'TERMINAL'].includes(model.status);
    const rawStates = record(row.node_states), stateIds = Object.keys(rawStates);
    if (stateIds.length > 24) invalid();
    const nodeStates = Object.fromEntries(stateIds.map(nodeId => {
      const state = record(rawStates[nodeId]);
      if (!nodeStatuses.includes(state.status as StudioGraphNodeStatus)) invalid();
      const nodeState: StudioGraphNodeState = { status: state.status as StudioGraphNodeStatus,
        output: hideOutputs ? null : output(state.output, modelOutput), error: state.error === null ? null : { code: code(record(state.error).code) } };
      return [id(nodeId), nodeState];
    }));
    const currentNodeId = row.current_node_id === null ? null : id(row.current_node_id);
    if (currentNodeId !== null && !Object.hasOwn(nodeStates, currentNodeId)) invalid();
    if (model && !Object.hasOwn(nodeStates, model.node_id)) invalid();
    if (media?.nodes.some(node => !Object.hasOwn(nodeStates, node.node_id))) invalid();
    let review: StudioGraphRun['review'] = null;
    if (!hideOutputs && row.review !== null) {
      const source = record(row.review), nodeId = id(source.node_id);
      if (!Object.hasOwn(nodeStates, nodeId)) invalid();
      review = { node_id: nodeId, output_digest: digest(source.output_digest), draft: draft(source.draft, modelOutput) };
    }
    const cache = record(row.cache);
    if (cache.mode !== 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY') invalid();
    const result: StudioGraphRun = { ...ownership, id: runId, version: integer(row.version, 1), graph_id: graphId, graph_version: integer(row.graph_version, 1),
      status, current_node_id: currentNodeId, node_states: nodeStates, review,
      cache: { hits: integer(cache.hits, 0, 24), misses: integer(cache.misses, 0, 24), mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' },
      created_at: text(row.created_at, 64), updated_at: text(row.updated_at, 64), model_called: modelCalled, external_calls: 0,
      ...(model ? { model_runtime: model } : {}),
      ...(media ? { media_runtime: media } : {}),
      applied: false, stale, reviewed: bool(row.reviewed), timeout_seconds: 3600, deadline_at: deadline(row.deadline_at) };
    if (row.asset_output !== undefined) result.asset_output = graphTextAssetOutput(row.asset_output, result, observedGraphs.get(graphId));
    if (observedRuns.has(runId) && observedRuns.get(runId) !== graphId) mismatch();
    observedRuns.set(runId, graphId);
    return result;
  }
  function checkedModelRun(value: unknown, runId: string): StudioGraphRun {
    const result = checkedRun(value, runId, observedRuns.get(runId));
    if (!result.model_runtime) invalid();
    return result;
  }
  function checkedMediaRun(value: unknown, runId: string, nodeId: string): StudioGraphRun {
    const result = checkedRun(value, runId, observedRuns.get(runId));
    if (!result.media_runtime || !Object.hasOwn(result.node_states, nodeId)) invalid(); return result;
  }
  function mediaInput(value: unknown): StudioGraphMediaPreviewInput {
    const row = record(value, true);
    return { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true), node_id: id(row.node_id, true) };
  }
  function mediaJobInput(value: unknown): StudioGraphMediaJobInput {
    const row = record(value, true); return { ...mediaInput(row), expected_job_version: integer(row.expected_job_version, 1, Number.MAX_SAFE_INTEGER, true),
      expected_request_digest: digest(row.expected_request_digest, true) };
  }
  function mediaJobAction(runId: string, action: 'execute' | 'refresh' | 'reconcile', value: StudioGraphMediaJobInput): Promise<StudioGraphRun> {
    const payload = mediaJobInput(value);
    return transport.json(`${runUrl(runId)}/media/${action}`, 'POST', payload).then(value => {
      const result = checkedMediaRun(value, runId, payload.node_id), job = result.media_runtime!.nodes.find(item => item.node_id === payload.node_id)?.execution?.job;
      if (!job || job.request_digest !== payload.expected_request_digest) invalid(); return result;
    });
  }

  return {
    ...createStudioProviderClient(base, transport, owner),
    catalog: (signal?: AbortSignal): Promise<StudioGraphCatalog> => transport.json(`${base}/graphs/catalog`, 'GET', undefined, signal).then(catalog),
    modelCapabilities: (signal?: AbortSignal): Promise<StudioGraphModelCapabilities> => transport.json(`${base}/graphs/model-capabilities`, 'GET', undefined, signal).then(value => graphModelCapabilities(value, owner)),
    list: (signal?: AbortSignal): Promise<{ items: StudioGraphRecord[] }> => transport.json(`${base}/graphs`, 'GET', undefined, signal).then(value => {
      const items = list(record(value).items, 25).map(item => checkedGraph(item));
      if (new Set(items.map(item => item.id)).size !== items.length) invalid();
      return { items: items.map(rememberGraph) };
    }),
    create: (value: StudioGraphCreateInput): Promise<StudioGraphRecord> => {
      const row = record(value, true);
      if (row.expected_version !== 0) invalid(true);
      const payload: StudioGraphCreateInput = { request_id: id(row.request_id, true), expected_version: 0, definition: definition(row.definition, true) };
      return transport.json(`${base}/graphs`, 'POST', payload, undefined, payload.request_id).then(value => rememberGraph(checkedGraph(value)));
    },
    get: (graphId: string, signal?: AbortSignal): Promise<StudioGraphRecord> => transport.json(graphUrl(graphId), 'GET', undefined, signal)
      .then(value => rememberGraph(checkedGraph(value, graphId))),
    save: (graphId: string, value: StudioGraphSaveInput): Promise<StudioGraphRecord> => {
      const url = graphUrl(graphId), row = record(value, true);
      if (observedGraphs.get(graphId)?.can_edit === false) {
        throw new ApiError({ status: 403, code: 'STUDIO_GRAPH_REDACTED_SAVE_BLOCKED', message: '当前节点图包含不可编辑或不可见内容，不能覆盖保存。请重新读取并核对访问权限。' });
      }
      const payload: StudioGraphSaveInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true), definition: definition(row.definition, true) };
      return transport.json(url, 'PUT', payload).then(value => rememberGraph(checkedGraph(value, graphId)));
    },
    preflight: (graphId: string, value: StudioGraphPreflightInput, signal?: AbortSignal): Promise<StudioGraphPreflight> => {
      const url = graphUrl(graphId), row = record(value, true);
      const payload: StudioGraphPreflightInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true), target_node_ids: uniqueIds(row.target_node_ids, true) };
      return transport.json(`${url}/preflight`, 'POST', payload, signal).then(value => checkedPreflight(value, graphId, payload));
    },
    runs: (graphId: string, signal?: AbortSignal): Promise<{ items: StudioGraphRun[] }> => transport.json(`${graphUrl(graphId)}/runs`, 'GET', undefined, signal).then(value => {
      const items = list(record(value).items, 100).map(item => checkedRun(item, undefined, graphId));
      if (new Set(items.map(item => item.id)).size !== items.length) invalid();
      return { items };
    }),
    createRun: (graphId: string, value: StudioGraphRunCreateInput): Promise<StudioGraphRun> => {
      const url = graphUrl(graphId), row = record(value, true);
      const payload: StudioGraphRunCreateInput = { expected_graph_version: integer(row.expected_graph_version, 1, Number.MAX_SAFE_INTEGER, true),
        reviewed_preflight_digest: digest(row.reviewed_preflight_digest, true), target_node_ids: uniqueIds(row.target_node_ids, true), request_id: id(row.request_id, true) };
      return transport.json(`${url}/runs`, 'POST', payload, undefined, payload.request_id).then(value => checkedRun(value, undefined, graphId));
    },
    getRun: (runId: string, signal?: AbortSignal): Promise<StudioGraphRun> => transport.json(runUrl(runId), 'GET', undefined, signal).then(value => checkedRun(value, runId)),
    previewModel: (runId: string, value: StudioGraphModelPreviewInput): Promise<StudioGraphRun> => {
      const url = runUrl(runId), row = record(value, true);
      const payload: StudioGraphModelPreviewInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true),
        route_id: digest(row.route_id, true), allow_synthetic: bool(row.allow_synthetic, true) };
      return transport.json(`${url}/model/preview`, 'POST', payload).then(value => {
        const result = checkedModelRun(value, runId), preview = result.model_runtime!.preview;
        if (!preview || preview.route && (preview.route.route_id !== payload.route_id || preview.route.synthetic && !payload.allow_synthetic)) invalid();
        return result;
      });
    },
    dispatchModel: (runId: string, value: StudioGraphModelDispatchInput): Promise<StudioGraphRun> => {
      const url = runUrl(runId), row = record(value, true);
      const payload: StudioGraphModelDispatchInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true),
        reviewed_preview_digest: digest(row.reviewed_preview_digest, true), ...(row.archive_result === undefined ? {} : { archive_result: row.archive_result === true ? true as const : invalid(true) }) };
      return transport.json(`${url}/model/dispatch`, 'POST', payload).then(value => {
        const result = checkedModelRun(value, runId);
        if (!result.model_runtime!.execution || payload.archive_result && !result.asset_output) invalid();
        return result;
      });
    },
    refreshModel: (runId: string, value: StudioGraphModelRefreshInput): Promise<StudioGraphRun> => {
      const url = runUrl(runId), row = record(value, true);
      const payload: StudioGraphModelRefreshInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true) };
      return transport.json(`${url}/model/refresh`, 'POST', payload).then(value => {
        const result = checkedModelRun(value, runId);
        if (!result.model_runtime!.execution) invalid();
        return result;
      });
    },
    previewMedia: (runId: string, value: StudioGraphMediaPreviewInput): Promise<StudioGraphRun> => {
      const payload = mediaInput(value);
      return transport.json(`${runUrl(runId)}/media/preview`, 'POST', payload).then(value => {
        const result = checkedMediaRun(value, runId, payload.node_id);
        if (!result.media_runtime!.nodes.find(item => item.node_id === payload.node_id)?.preview) invalid(); return result;
      });
    },
    dispatchMedia: (runId: string, value: StudioGraphMediaDispatchInput): Promise<StudioGraphRun> => {
      const row = record(value, true), payload: StudioGraphMediaDispatchInput = { ...mediaInput(row), reviewed_preview_digest: digest(row.reviewed_preview_digest, true) };
      return transport.json(`${runUrl(runId)}/media/dispatch`, 'POST', payload).then(value => {
        const result = checkedMediaRun(value, runId, payload.node_id);
        if (!result.media_runtime!.nodes.find(item => item.node_id === payload.node_id)?.execution) invalid(); return result;
      });
    },
    executeMedia: (runId: string, value: StudioGraphMediaJobInput) => mediaJobAction(runId, 'execute', value),
    refreshMedia: (runId: string, value: StudioGraphMediaPreviewInput | StudioGraphMediaJobInput): Promise<StudioGraphRun> => {
      if ('expected_job_version' in value) return mediaJobAction(runId, 'refresh', value);
      const payload = mediaInput(value);
      return transport.json(`${runUrl(runId)}/media/refresh`, 'POST', payload).then(value => checkedMediaRun(value, runId, payload.node_id));
    },
    reconcileMedia: (runId: string, value: StudioGraphMediaJobInput) => mediaJobAction(runId, 'reconcile', value),
    reviewMedia: (runId: string, value: StudioGraphMediaReviewInput): Promise<StudioGraphRun> => {
      const row = record(value, true), payload: StudioGraphMediaReviewInput = { ...mediaJobInput(row), reviewed_output_digest: digest(row.reviewed_output_digest, true) };
      return transport.json(`${runUrl(runId)}/media/review`, 'POST', payload).then(value => {
        const result = checkedMediaRun(value, runId, payload.node_id);
        const approved = result.node_states[payload.node_id]?.output?.asset;
        if (approved ? approved.digest !== payload.reviewed_output_digest
          : !result.media_runtime!.nodes.some(item => item.execution?.job?.request_digest === payload.expected_request_digest)) invalid(); return result;
      });
    },
    mediaCandidate: (runId: string, nodeId: string): Promise<Blob> => {
      if (!transport.blob) throw new ApiError({ status: 400, code: 'STUDIO_GRAPH_MEDIA_TRANSPORT_REQUIRED', message: '当前入口不支持可信媒体下载，请使用完整 Studio 工作区。' });
      return transport.blob(`${runUrl(runId)}/media/candidate/${encodeURIComponent(id(nodeId, true))}`);
    },
    action: (runId: string, action: StudioGraphAction, value: StudioGraphActionInput): Promise<StudioGraphRun> => {
      const url = runUrl(runId), row = record(value, true);
      if (!actions.includes(action)) invalid(true);
      const payload: StudioGraphActionInput = { expected_version: integer(row.expected_version, 1, Number.MAX_SAFE_INTEGER, true),
        note: text(row.note === undefined ? '' : row.note, 1_000, true, true),
        ...(row.node_id === undefined ? {} : { node_id: id(row.node_id, true) }),
        ...(row.reviewed_output_digest === undefined ? {} : { reviewed_output_digest: digest(row.reviewed_output_digest, true) }) };
      if ((action === 'approve' || action === 'reject') && (!payload.node_id || !payload.reviewed_output_digest)) invalid(true);
      if (action !== 'approve' && action !== 'reject' && (payload.node_id !== undefined || payload.reviewed_output_digest !== undefined)) invalid(true);
      return transport.json(`${url}/${action}`, 'POST', payload).then(value => checkedRun(value, runId));
    },
  };
}

// Older embedded clients can omit the advisory extension; execution stays unchanged.
type StudioGraphMediaClient = Pick<ReturnType<typeof createStudioGraphClient>, 'previewMedia' | 'dispatchMedia' | 'executeMedia' | 'refreshMedia' | 'reconcileMedia' | 'reviewMedia' | 'mediaCandidate'>;
export type StudioGraphClient = Omit<ReturnType<typeof createStudioGraphClient>, keyof StudioProviderClient | keyof StudioGraphMediaClient>
  & Partial<StudioProviderClient> & Partial<StudioGraphMediaClient>;
