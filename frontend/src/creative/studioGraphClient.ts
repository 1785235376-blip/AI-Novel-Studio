import { checkedStoryboardShot, checkedStoryboardReceipt } from './studioStoryboardContract';
import { checkedVideoReference, checkedVideoRecipe, storyboardShotFields, sameVideoReference } from './studioVideoRuntimeContract';
import { videoGraphDefinitions } from './graphDraft';
import { checkedPlanningSnapshot, checkedPlanningDocument, checkedPlanningProjection, productionGraphDefinitions, type PlanningDocument, type PlanningSnapshot } from './studioProductionGraphContract';
import { createDirectorWorkspaceClient } from '../director/directorWorkspaceClient';
import { ApiError, type CollaborationContext } from '../api';
import { GRAPH_VIDEO_OPERATIONS, GRAPH_IMAGE_OPERATIONS, GRAPH_MEDIA_OPERATIONS } from './studioGraphTypes';
import { checkedImageUpscaleProof, checkedImageReferenceMetadata, checkedImageRecipeCommand, checkedImageRecipeFields, checkedImageRuntimeInputs, sameImageRuntimeInputs } from './studioImageRuntimeContract';
import type {
  RecordedGraphMediaCommand, GraphImageOperation, GraphMediaOperation, StudioGraphAction, StudioGraphActionInput, StudioGraphCatalogDefinition, StudioGraphDefinition,
  StudioGraphDefinitionId, StudioGraphDraft, StudioGraphNode, StudioGraphOutput, StudioGraphParameters,
  StudioGraphParameterSchema, StudioGraphPort, StudioGraphPosition, StudioGraphPreflight,
  StudioGraphPreflightInput, StudioGraphCreateInput, StudioGraphSaveInput, StudioGraphRunCreateInput,
  StudioGraphRecord, StudioGraphReferenceState, StudioGraphRun, StudioGraphRunStatus, StudioGraphCatalog,
  StudioGraphScope, StudioGraphOwner, StudioGraphNodeState, StudioGraphNodeStatus,
  StudioGraphModelCapabilities, StudioGraphModelPreviewInput, StudioGraphModelDispatchInput, StudioGraphModelRefreshInput,
  StudioGraphAssetRef, StudioGraphMediaCandidate, StudioGraphMediaRuntime, StudioGraphMediaPreviewInput,
  StudioGraphMediaDispatchInput, StudioGraphMediaJobInput, StudioGraphMediaReviewInput,
  StudioGraphMediaPreview, StudioGraphMediaJob, StudioGraphMediaExecution,
  GraphTimelineProductionPreview,
} from './studioGraphTypes';
import type { ProductionJob, ProductionPreview, RecordedProductionSource, ProductionRecipe } from './studioProductionClient';
import { graphModelCapabilities, graphModelRuntime } from './studioGraphModelContract';
import { graphTextAssetOutput } from './studioGraphTextAssetContract';
import { createStudioProviderClient, type StudioProviderClient } from './studioProviderClient';
import { checkedGraphTimelineParameters, checkedGraphTimelineSnapshot, graphTimelineId, graphTimelinePorts, type GraphTimelineCommand } from './studioGraphTimelineContract';
import { checkedTimelineExportProfile, timelineExportKey } from './studioTimelineExportTypes';
import { checkedTimeline, timelineSources, type StudioTimelineRow } from './studioTimelineTypes';

/** Inject the existing Studio transport; graph operations never look up credentials. */
export type StudioGraphTransport = {
  json<T>(url: string, method?: string, body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T>;
  blob?(url: string): Promise<Blob>;
};

const localDefinitionIds: readonly StudioGraphDefinitionId[] = ['text_input', 'text_reference', 'draft_prepare', 'manual_transform', 'director_note', 'human_review', 'asset_reference'];
const modelDefinitionIds: readonly StudioGraphDefinitionId[] = [...localDefinitionIds, 'text_generate'];
const mediaDefinitionIds: readonly StudioGraphDefinitionId[] = ['media_generate', 'media_review'];
const imageDefinitionIds: readonly StudioGraphDefinitionId[] = ['image_reference', 'image_prompt', 'image_generate'];
const imageSchemaDefinitionIds: readonly StudioGraphDefinitionId[] = ['text_input', 'text_reference', 'asset_reference', ...imageDefinitionIds, ...productionGraphDefinitions, 'media_review'];
const definitionIds: readonly StudioGraphDefinitionId[] = [...modelDefinitionIds, ...mediaDefinitionIds, 'timeline_export', ...imageDefinitionIds, ...productionGraphDefinitions, 'storyboard_shot', 'video_generate'];
const statuses: readonly StudioGraphRunStatus[] = ['QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'PAUSED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'];
const nodeStatuses: readonly StudioGraphNodeStatus[] = ['PENDING', 'WAITING_APPROVAL', 'QUEUED', 'WORKING', 'SUCCEEDED', 'FAILED', 'SKIPPED', 'REJECTED'];
const actions: readonly StudioGraphAction[] = ['execute', 'approve', 'reject', 'cancel', 'pause', 'resume'];
const portKinds = ['TEXT', 'DIRECTOR_NOTES', 'DRAFT', 'ASSET_REF', 'MEDIA_CANDIDATE', 'IMAGE_REFERENCES', 'IMAGE_PROMPT', 'DIRECTOR_PLAN', 'STORYBOARD_DATA', 'STORYBOARD_SHOT', 'VIDEO_CANDIDATE'] as const;
const parameterKeys: Record<StudioGraphDefinitionId, readonly string[]> = {
  text_input: ['text'], text_reference: [], draft_prepare: [], manual_transform: ['result'],
  director_note: ['note'], human_review: [], asset_reference: ['asset_id', 'version', 'digest', 'kind'],
  text_generate: ['instruction', 'max_output_tokens'],
  media_generate: ['operation_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'allow_cloud', 'license_note'], media_review: [],
  timeline_export: ['timeline_snapshot', 'edit_operations', 'source_bindings', 'export_profile'],
  image_reference: ['bindings'], image_prompt: ['prompt'],
  image_style: ['style', 'atmosphere', 'color_palette'], image_upscale: ['operation_id', 'provider_id', 'model_id', 'parameters', 'allow_cloud', 'license_note'],
  storyboard_shot: ['shot_id', 'shot_version', 'shot_digest'], video_generate: ['operation_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'allow_cloud', 'license_note', 'reference_purpose', 'bind_shot'],
  director_plan: ['document_snapshot'], storyboard_plan: ['document_snapshot'], storyboard_prompt: ['shot_id'],
  image_generate: ['operation_id', 'provider_id', 'model_id', 'parameters', 'allow_cloud', 'license_note'],
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
  timeline_export: { inputs: Object.fromEntries(graphTimelinePorts.map(port => [port, 'ASSET_REF'])), outputs: { candidate: 'MEDIA_CANDIDATE' } },
  storyboard_shot: { inputs: { storyboard: 'STORYBOARD_DATA' }, outputs: { shot: 'STORYBOARD_SHOT' } },
  video_generate: { inputs: { text: 'TEXT', shot: 'STORYBOARD_SHOT', source: 'ASSET_REF', reference: 'ASSET_REF' }, outputs: { candidate: 'VIDEO_CANDIDATE' } },
  image_style: { inputs: { prompt: 'IMAGE_PROMPT' }, outputs: { prompt: 'IMAGE_PROMPT' } },
  image_upscale: { inputs: { source: 'ASSET_REF' }, outputs: { candidate: 'MEDIA_CANDIDATE' } },
  director_plan: { inputs: {}, outputs: { direction: 'DIRECTOR_PLAN' } },
  storyboard_plan: { inputs: { direction: 'DIRECTOR_PLAN' }, outputs: { storyboard: 'STORYBOARD_DATA' } },
  storyboard_prompt: { inputs: { storyboard: 'STORYBOARD_DATA' }, outputs: { prompt: 'IMAGE_PROMPT' } },
  image_reference: { inputs: Object.fromEntries(Array.from({ length: 5 }, (_, index) => [`source_${index + 1}`, 'ASSET_REF'])), outputs: { references: 'IMAGE_REFERENCES' } },
  image_prompt: { inputs: { text: 'TEXT', references: 'IMAGE_REFERENCES' }, outputs: { prompt: 'IMAGE_PROMPT' } },
  image_generate: { inputs: { prompt: 'IMAGE_PROMPT', source: 'ASSET_REF', mask: 'ASSET_REF' }, outputs: { candidate: 'MEDIA_CANDIDATE' } },
};
function nodePorts(kind: StudioGraphDefinitionId, mediaSchema: boolean, videoSchema = false): { inputs: Record<string, string>; outputs: Record<string, string> } {
  if (videoSchema && kind === 'media_review') return { inputs: { candidate: 'VIDEO_CANDIDATE' }, outputs: { asset: 'ASSET_REF' } };
  if (videoSchema && kind === 'timeline_export') return { inputs: ports.timeline_export.inputs, outputs: { candidate: 'VIDEO_CANDIDATE' } };
  if (mediaSchema && kind === 'human_review') return { inputs: { draft: 'DRAFT' }, outputs: { reviewed_draft: 'DRAFT' } };
  if (mediaSchema && kind === 'media_generate') return { inputs: { text: 'TEXT', draft: 'DRAFT', source: 'ASSET_REF' }, outputs: { candidate: 'MEDIA_CANDIDATE' } };
  return ports[kind];
}
const mediaOperations: readonly GraphMediaOperation[] = GRAPH_MEDIA_OPERATIONS;
const mediaParameterKeys = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'];
const parametersForOperation: Record<GraphMediaOperation, readonly string[]> = {
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
function mediaOperation(value: unknown, input = false, image = false): GraphMediaOperation | GraphImageOperation | 'm5.image.upscale' {
  if (!(image ? [...mediaOperations, ...GRAPH_IMAGE_OPERATIONS, 'm5.image.upscale'] : mediaOperations).includes(value as GraphMediaOperation)) invalid(input);
  return value as GraphMediaOperation | GraphImageOperation | 'm5.image.upscale';
}
function mediaParameterValues(value: unknown, operation: GraphMediaOperation | GraphImageOperation | 'm5.image.upscale', input = false, image = false): NonNullable<StudioGraphParameters['parameters']> {
  const row = record(value, input), result: NonNullable<StudioGraphParameters['parameters']> = {};
  if (operation === 'm5.image.upscale') {
    if (!image || Object.keys(row).length !== 1 || row.scale !== 2 && row.scale !== 4) invalid(input);
    return { scale: row.scale };
  }
  if (Object.keys(row).some(key => !mediaParameterKeys.includes(key) && !(image && key === 'denoising_strength'))) invalid(input);
  for (const [key, value] of Object.entries(row)) {
    if (value === null) { result[key] = null; continue; }
    if (image && key === 'denoising_strength') {
      if (!['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].includes(operation)) invalid(input);
      result[key] = number(value, Number.MIN_VALUE, 1, input); continue;
    }
    if (!(['m5.image.inpaint', 'm5.image.reference'].includes(operation) ? parametersForOperation['m5.image.i2i'] : parametersForOperation[operation as GraphMediaOperation]).includes(key)) invalid(input);
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
  if (unavailable && ['asset_reference', 'director_plan', 'storyboard_plan'].includes(kind)) return {};
  if ([...imageDefinitionIds, ...productionGraphDefinitions].includes(kind) && Object.keys(row).some(key => !parameterKeys[kind].includes(key))) invalid(input);
  if (kind === 'director_plan' || kind === 'storyboard_plan') return { document_snapshot: checkedPlanningSnapshot(row.document_snapshot, input) };
  if (kind === 'storyboard_shot') { if (Object.keys(row).some(key => !parameterKeys[kind].includes(key))) invalid(input); return { shot_id: resourceId(row.shot_id, input), shot_version: integer(row.shot_version, 1, Number.MAX_SAFE_INTEGER, input), shot_digest: digest(row.shot_digest, input) }; }
  if (kind === 'video_generate') {
    if (Object.keys(row).some(key => !parameterKeys[kind].includes(key)) || !GRAPH_VIDEO_OPERATIONS.includes(row.operation_id as typeof GRAPH_VIDEO_OPERATIONS[number])) invalid(input);
    const operation = row.operation_id as typeof GRAPH_VIDEO_OPERATIONS[number];
    if (row.bind_shot !== undefined && row.bind_shot !== true) invalid(input);
    if (row.reference_purpose !== undefined && !['style', 'action', 'camera'].includes(String(row.reference_purpose))) invalid(input);
    return { operation_id: operation, provider_id: resourceId(row.provider_id, input), model_id: resourceId(row.model_id, input), prompt: text(row.prompt ?? '', 16000, input, true), parameters: mediaParameterValues(row.parameters ?? {}, operation, input), allow_cloud: bool(row.allow_cloud ?? false, input), license_note: text(row.license_note ?? '', 2000, input, true), ...(row.reference_purpose === undefined ? {} : { reference_purpose: row.reference_purpose as 'style' | 'action' | 'camera' }), ...(row.bind_shot === true ? { bind_shot: true as const } : {}) };
  }
  if (kind === 'storyboard_prompt') return { shot_id: resourceId(row.shot_id, input) };
  if (kind === 'image_style') return { style: text(row.style ?? '', 2000, input, true), atmosphere: text(row.atmosphere ?? '', 1000, input, true), color_palette: text(row.color_palette ?? '', 1000, input, true) };
  if (kind === 'image_upscale') {
    if (row.operation_id !== 'm5.image.upscale' || row.allow_cloud !== false) invalid(input);
    return { operation_id: 'm5.image.upscale', provider_id: resourceId(row.provider_id, input), model_id: resourceId(row.model_id, input),
      parameters: mediaParameterValues(row.parameters, 'm5.image.upscale', input, true), allow_cloud: false, license_note: text(row.license_note ?? '', 2000, input, true) };
  }
  if (kind === 'image_prompt') return { prompt: text(row.prompt ?? '', 8000, input, true) };
  if (kind === 'image_reference') {
    const bindings = list(row.bindings ?? [], 5, input).map(value => {
      const binding = record(value, input); if (Object.keys(binding).some(key => !['port', 'weight', 'purpose', 'source_note'].includes(key)) || !Object.hasOwn(binding, 'port') || !Object.hasOwn(binding, 'weight')
        || typeof binding.port !== 'string' || !/^source_[1-5]$/.test(binding.port)) invalid(input);
      const weight = number(binding.weight, Number.MIN_VALUE, 1, input);
      return { port: binding.port as NonNullable<StudioGraphParameters['bindings']>[number]['port'], weight, ...checkedImageReferenceMetadata(binding, input) };
    });
    if (new Set(bindings.map(binding => binding.port)).size !== bindings.length) invalid(input);
    return { bindings };
  }
  if (kind === 'image_generate') {
    const operation = mediaOperation(row.operation_id, input, true);
    if (!GRAPH_IMAGE_OPERATIONS.includes(operation as GraphImageOperation)) invalid(input);
    return { operation_id: operation, provider_id: resourceId(row.provider_id, input), model_id: resourceId(row.model_id, input),
      parameters: mediaParameterValues(row.parameters ?? {}, operation, input, true), allow_cloud: bool(row.allow_cloud ?? false, input),
      license_note: text(row.license_note ?? '', 2000, input, true) };
  }
  if (kind === 'timeline_export') { try { return checkedGraphTimelineParameters(row); } catch { return invalid(input); } }
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
  if (row.schema_version !== 1 && row.schema_version !== 2 && row.schema_version !== 3 && row.schema_version !== 4 && row.schema_version !== 5) invalid(input);
  const nodes: StudioGraphNode[] = list(row.nodes, row.schema_version >= 3 ? 24 : 16, input).map(item => {
    const node = record(item, input), nodeId = id(node.id, input), kind = definitionId(node.definition_id, input);
    if (row.schema_version === 5 ? !videoGraphDefinitions.includes(kind as typeof videoGraphDefinitions[number]) : row.schema_version === 4 ? !imageSchemaDefinitionIds.includes(kind) || ['storyboard_shot', 'video_generate'].includes(kind)
      : [...imageDefinitionIds, ...productionGraphDefinitions, 'storyboard_shot', 'video_generate'].includes(kind) || kind === 'text_generate' && row.schema_version === 1 || [...mediaDefinitionIds, 'timeline_export'].includes(kind) && row.schema_version !== 3) invalid(input);
    if (node.definition_version !== 1) invalid(input);
    return { id: nodeId, definition_id: kind, definition_version: 1, enabled: bool(node.enabled, input),
      position: position(node.position, input), parameters: parameters(node.parameters, kind, input, unavailable.has(nodeId)) };
  });
  if (row.schema_version === 4 && nodes.some(node => node.definition_id === 'asset_reference' && node.parameters.kind !== undefined && node.parameters.kind !== 'image')) invalid(input);
  const nodeMap = new Map(nodes.map(node => [node.id, node]));
  if (nodeMap.size !== nodes.length) invalid(input);
  const targets = new Set<string>(), edgeIds = new Set<string>();
  const edges = list(row.edges, 40, input).map(item => {
    const edge = record(item, input);
    const result = { id: id(edge.id, input), source_node_id: id(edge.source_node_id, input), source_port: id(edge.source_port, input),
      target_node_id: id(edge.target_node_id, input), target_port: id(edge.target_port, input) };
    const source = nodeMap.get(result.source_node_id), target = nodeMap.get(result.target_node_id);
    if (!source || !target || edgeIds.has(result.id)) invalid(input);
    const sourcePorts = nodePorts(source.definition_id, row.schema_version === 3, row.schema_version === 5).outputs, targetPorts = nodePorts(target.definition_id, row.schema_version === 3, row.schema_version === 5).inputs;
    if (!Object.hasOwn(sourcePorts, result.source_port) || !Object.hasOwn(targetPorts, result.target_port)) invalid(input);
    const outputType = sourcePorts[result.source_port], inputType = targetPorts[result.target_port];
    if (!outputType || !inputType || outputType !== inputType) invalid(input);
    const targetKey = `${result.target_node_id}:${result.target_port}`;
    if (targets.has(targetKey)) invalid(input);
    targets.add(targetKey); edgeIds.add(result.id);
    return result;
  });
  if (row.schema_version === 5 && nodes.filter(node => ['video_generate', 'timeline_export'].includes(node.definition_id)).length > 4) invalid(input);
  if (row.schema_version === 4) {
    if (nodes.filter(node => ['image_generate', 'image_upscale'].includes(node.definition_id)).length > 4) invalid(input);
    for (const node of nodes) {
      const incoming = edges.filter(edge => edge.target_node_id === node.id);
      if (node.definition_id === 'image_reference' && incoming.some(edge => !node.parameters.bindings?.some(binding => binding.port === edge.target_port))) invalid(input);
      if (['image_generate', 'image_upscale'].includes(node.definition_id) && edges.some(edge => edge.source_node_id === node.id
        && (nodeMap.get(edge.target_node_id)?.definition_id !== 'media_review' || edge.target_port !== 'candidate'))) invalid(input);
    }
  }
  if (row.schema_version === 3) {
    if (nodes.filter(node => ['media_generate', 'timeline_export'].includes(node.definition_id)).length > 4) invalid(input);
    for (const node of nodes.filter(item => item.definition_id === 'timeline_export')) {
      const connected = edges.filter(edge => edge.target_node_id === node.id);
      const bindings = node.parameters.source_bindings || [];
      if (connected.length !== bindings.length || bindings.some(binding => !connected.some(edge => edge.target_port === binding.port))) invalid(input);
    }
    for (const node of nodes.filter(item => item.definition_id === 'media_generate')) {
      const draftEdge = edges.find(edge => edge.target_node_id === node.id && edge.target_port === 'draft');
      if (!draftEdge) continue;
      if (edges.some(edge => edge.target_node_id === node.id && edge.target_port === 'text')) invalid(input);
      const review = nodeMap.get(draftEdge.source_node_id), modelEdge = edges.find(edge => edge.target_node_id === review?.id && edge.target_port === 'draft');
      if (review?.definition_id !== 'human_review' || draftEdge.source_port !== 'reviewed_draft' || !modelEdge
        || modelEdge.source_port !== 'draft' || nodeMap.get(modelEdge.source_node_id)?.definition_id !== 'text_generate') invalid(input);
    }
  }
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
  if (row.presentation !== undefined) {
    const presentation = record(row.presentation, input);
    if (!Object.keys(presentation).length || Object.keys(presentation).some(key => !['comment', 'groups', 'view', 'notes'].includes(key))) invalid(input);
    result.presentation = {};
    if (presentation.notes !== undefined) {
      if (!Array.isArray(presentation.notes) || !presentation.notes.length || presentation.notes.length > 1024) invalid(input);
      const ids = new Set<string>();
      result.presentation.notes = presentation.notes.map(value => {
        const note = record(value, input), point = record(note.position, input);
        if (Object.keys(note).length !== 3 || Object.keys(note).some(key => !['id', 'text', 'position'].includes(key))
          || Object.keys(point).length !== 2 || Object.keys(point).some(key => !['x', 'y'].includes(key))) invalid(input);
        const id = text(note.id, 64, input), content = text(note.text, 512, input, true);
        if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}(?![\s\S])/.test(id) || ids.has(id) || Array.from(content).length > 256) invalid(input);
        ids.add(id); return { id, text: content, position: position(point, input) };
      });
      if (result.presentation.notes.reduce((sum, note) => sum + Array.from(note.text).length, 0) > 12000) invalid(input);
    }
    if (presentation.comment !== undefined) {
      const comment = text(presentation.comment, 4000, input, true);
      if (Array.from(comment).length > 2000) invalid(input);
      result.presentation.comment = comment;
    }
    if (presentation.view !== undefined) {
      const view = record(presentation.view, input);
      if (Object.keys(view).length !== 4 || Object.keys(view).some(key => !['show_grid', 'snap', 'grid_step', 'show_minimap'].includes(key))
        || typeof view.show_grid !== 'boolean' || typeof view.snap !== 'boolean' || typeof view.show_minimap !== 'boolean'
        || typeof view.grid_step !== 'number' || ![8, 16, 24, 32].includes(view.grid_step)) invalid(input);
      result.presentation.view = { show_grid: view.show_grid as boolean, snap: view.snap as boolean,
        grid_step: view.grid_step as 8 | 16 | 24 | 32, show_minimap: view.show_minimap as boolean };
    }
    if (presentation.groups !== undefined) {
      if (!Array.isArray(presentation.groups) || !presentation.groups.length || presentation.groups.length > 24) invalid(input);
      const ids = new Set<string>(), members = new Set<string>();
      result.presentation.groups = presentation.groups.map(value => {
        const group = record(value, input);
        if (Object.keys(group).some(key => !['id', 'name', 'node_ids', 'parent_id'].includes(key))) invalid(input);
        const groupId = text(group.id, 64, input), name = text(group.name, 160, input);
        if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(groupId) || ids.has(groupId) || Array.from(name).length > 80) invalid(input);
        ids.add(groupId);
        if (!Array.isArray(group.node_ids) || !group.node_ids.length || group.node_ids.length > 24) invalid(input);
        const node_ids = group.node_ids.map(value => {
          const member = text(value, 64, input);
          if (!nodeMap.has(member) || members.has(member)) invalid(input);
          members.add(member); return member;
        });
        const parent_id = group.parent_id === undefined ? undefined : text(group.parent_id, 64, input);
        return { id: groupId, name, node_ids, ...(parent_id === undefined ? {} : { parent_id }) };
      });
      for (const group of result.presentation.groups) {
        if (group.parent_id !== undefined) {
          const parent = result.presentation.groups.find(item => item.id === group.parent_id);
          if (!parent || parent.id === group.id || parent.parent_id !== undefined) invalid(input);
        }
      }
    }
  }
  if (new TextEncoder().encode(JSON.stringify(result)).length > 96_000) invalid(input);
  return result;
}

function schema(value: unknown, kind: StudioGraphDefinitionId): StudioGraphParameterSchema {
  const row = record(value), properties = record(row.properties);
  if (row.type !== 'object' || row.additionalProperties !== false) invalid();
  if (kind === 'timeline_export') {
    if (JSON.stringify(row).length > 128000 || Object.keys(properties).length !== 4 || Object.keys(properties).some(key => !parameterKeys[kind].includes(key))) invalid();
    return { type: 'object', additionalProperties: false, properties: { timeline_snapshot: { type: 'object' }, edit_operations: { type: 'array' },
      source_bindings: { type: 'array' }, export_profile: { type: 'object' } }, required: ['timeline_snapshot', 'export_profile'] };
  }
  if (kind === 'storyboard_shot') { if (Object.keys(properties).length !== 3 || parameterKeys[kind].some(key => !Object.hasOwn(properties, key))) invalid(); return { type: 'object', additionalProperties: false, properties: { shot_id: { type: 'string', maxLength: 240 }, shot_version: { type: 'integer', minimum: 1 }, shot_digest: { type: 'string' } }, required: ['shot_id', 'shot_version', 'shot_digest'] }; }
  if (kind === 'video_generate') {
    if (JSON.stringify(row).length > 100000 || ![8, 9].includes(Object.keys(properties).length) || Object.keys(properties).some(key => !parameterKeys[kind].includes(key)) || parameterKeys[kind].filter(key => key !== 'bind_shot').some(key => !Object.hasOwn(properties, key))) invalid();
    if (properties.bind_shot !== undefined) {
      const binding = record(properties.bind_shot), variants = list(binding.anyOf, 2).map(value => record(value));
      if (variants.length !== 2 || !variants.some(value => Object.keys(value).length === 2 && value.type === 'boolean' && value.const === true) || !variants.some(value => Object.keys(value).length === 1 && value.type === 'null') || binding.default !== null) invalid();
    }
    return { type: 'object', additionalProperties: false, properties: { operation_id: { type: 'string', enum: [...GRAPH_VIDEO_OPERATIONS] }, provider_id: { type: 'string', maxLength: 240 }, model_id: { type: 'string', maxLength: 240 }, prompt: { type: 'string', maxLength: 16000 }, parameters: { type: 'object' }, allow_cloud: { type: 'boolean' }, license_note: { type: 'string', maxLength: 2000 }, reference_purpose: { type: 'string', enum: ['style', 'action', 'camera'] }, ...(properties.bind_shot === undefined ? {} : { bind_shot: { type: 'boolean', const: true } }) }, required: ['operation_id'] };
  }
  if (productionGraphDefinitions.includes(kind as typeof productionGraphDefinitions[number])) {
    if (JSON.stringify(row).length > 100000 || Object.keys(properties).length !== parameterKeys[kind].length || Object.keys(properties).some(key => !parameterKeys[kind].includes(key))) invalid();
    if (kind === 'director_plan' || kind === 'storyboard_plan') return { type: 'object', additionalProperties: false, properties: { document_snapshot: { type: 'object' } }, required: ['document_snapshot'] };
    if (kind === 'storyboard_prompt') return { type: 'object', additionalProperties: false, properties: { shot_id: { type: 'string', maxLength: 240 } }, required: ['shot_id'] };
    if (kind === 'image_style') return { type: 'object', additionalProperties: false, properties: { style: { type: 'string', maxLength: 2000 }, atmosphere: { type: 'string', maxLength: 1000 }, color_palette: { type: 'string', maxLength: 1000 } } };
    return { type: 'object', additionalProperties: false, properties: { operation_id: { type: 'string', enum: ['m5.image.upscale'] }, provider_id: { type: 'string', maxLength: 240 }, model_id: { type: 'string', maxLength: 240 }, parameters: { type: 'object' }, allow_cloud: { type: 'boolean', default: false }, license_note: { type: 'string', maxLength: 2000 } }, required: ['operation_id', 'provider_id', 'model_id', 'parameters'] };
  }
  if (imageDefinitionIds.includes(kind)) {
    if (JSON.stringify(row).length > 100000 || Object.keys(properties).length !== parameterKeys[kind].length
      || Object.keys(properties).some(key => !parameterKeys[kind].includes(key))) invalid();
    if (kind === 'image_reference') return { type: 'object', additionalProperties: false, properties: { bindings: { type: 'array' } } };
    if (kind === 'image_prompt') return { type: 'object', additionalProperties: false, properties: { prompt: { type: 'string', maxLength: 8000, default: '' } } };
    const operation = record(properties.operation_id);
    if (operation.type !== 'string' || !Array.isArray(operation.enum) || operation.enum.length !== GRAPH_IMAGE_OPERATIONS.length
      || operation.enum.some(item => !GRAPH_IMAGE_OPERATIONS.includes(item as GraphImageOperation))) invalid();
    return { type: 'object', additionalProperties: false, properties: {
      operation_id: { type: 'string', enum: [...GRAPH_IMAGE_OPERATIONS] }, provider_id: { type: 'string', maxLength: 240 }, model_id: { type: 'string', maxLength: 240 },
      parameters: { type: 'object', default: {} }, allow_cloud: { type: 'boolean', default: false }, license_note: { type: 'string', maxLength: 2000, default: '' },
    }, required: ['operation_id', 'provider_id', 'model_id'] };
  }
  if (kind === 'media_generate') {
    if (JSON.stringify(row).length > 100000 || Object.keys(properties).length !== parameterKeys[kind].length
      || Object.keys(properties).some(key => !parameterKeys[kind].includes(key))) invalid();
    const operation = record(properties.operation_id);
    if (operation.type !== 'string' || !Array.isArray(operation.enum) || operation.enum.length !== mediaOperations.length
      || operation.enum.some(item => !mediaOperations.includes(item as GraphMediaOperation))) invalid();
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
function catalogDefinition(value: unknown, mediaEnabled = false, videoSchema = false): StudioGraphCatalogDefinition {
  const row = record(value), kind = definitionId(row.id);
  const executable = mediaEnabled || kind !== 'asset_reference';
  if (row.version !== 1 || row.model_called !== false || row.executable !== executable) invalid();
  function checkedPorts(value: unknown, side: 'inputs' | 'outputs'): StudioGraphPort[] {
    const expected = nodePorts(kind, mediaEnabled, videoSchema)[side];
    const result = list(value, kind === 'timeline_export' ? 8 : kind === 'video_generate' ? 4 : kind === 'image_reference' ? 5 : 3).map(item => {
      const port = record(item), portId = id(port.id), required = bool(port.required);
      if (!portKinds.includes(port.type as StudioGraphPort['type']) || expected[portId] !== port.type || port.multiple !== false) invalid();
      const expectedRequired = side === 'inputs' && (['image_generate', 'image_style'].includes(kind) ? portId === 'prompt'
        : ['image_reference', 'image_prompt'].includes(kind) ? false : portId !== 'direction' && kind !== 'media_generate' && kind !== 'timeline_export' && kind !== 'video_generate');
      if (required !== expectedRequired) invalid();
      return { id: portId, type: port.type as StudioGraphPort['type'], required, multiple: false as const };
    });
    if (new Set(result.map(port => port.id)).size !== Object.keys(expected).length || result.length !== Object.keys(expected).length) invalid();
    return result;
  }
  if (['asset_reference', 'media_generate', 'timeline_export', 'image_generate', 'image_upscale', 'director_plan', 'storyboard_plan', 'storyboard_prompt', 'storyboard_shot', 'video_generate'].includes(kind) && row.default_parameters !== null) invalid();
  return { id: kind, version: 1, inputs: checkedPorts(row.inputs, 'inputs'), outputs: checkedPorts(row.outputs, 'outputs'),
    parameters_schema: schema(row.parameters_schema, kind),
    default_parameters: ['asset_reference', 'media_generate', 'timeline_export', 'image_generate', 'image_upscale', 'director_plan', 'storyboard_plan', 'storyboard_prompt', 'storyboard_shot', 'video_generate'].includes(kind) ? null : parameters(row.default_parameters, kind),
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
function output(value: unknown, allowModel = false, allowReviewed = false, imageKind?: StudioGraphDefinitionId): StudioGraphOutput | null {
  if (value === null) return null;
  const row = record(value), result: StudioGraphOutput = {};
  if (imageKind === 'image_reference') closed(row, ['references']);
  if (['image_prompt', 'image_style', 'storyboard_prompt'].includes(imageKind || '')) closed(row, ['prompt']);
  if (imageKind === 'director_plan') closed(row, ['direction']);
  if (imageKind === 'storyboard_plan') closed(row, ['storyboard']);
  if (imageKind === 'storyboard_shot') { closed(row, ['shot']); const shot = record(row.shot); closed(shot, ['document_snapshot', 'shot_id', 'shot_version', 'shot_digest', 'shot', 'image_asset', 'approved']); if (typeof shot.approved !== 'boolean') invalid(); result.shot = { ...checkedStoryboardShot({ shot_id: shot.shot_id, shot_version: shot.shot_version, shot_digest: shot.shot_digest, shot: shot.shot, image_asset: shot.image_asset }), document_snapshot: checkedPlanningSnapshot(shot.document_snapshot), approved: shot.approved }; }
  if (row.text !== undefined) result.text = text(row.text, 8_000, false, true);
  if (row.direction !== undefined) result.direction = imageKind === 'director_plan' ? checkedPlanningProjection(row.direction, 'DIRECTOR') : { note: text(record(row.direction).note, 4_000, false, true) };
  if (row.storyboard !== undefined) { if (imageKind !== 'storyboard_plan') invalid(); result.storyboard = checkedPlanningProjection(row.storyboard, 'STORYBOARD'); }
  if (row.draft !== undefined) result.draft = draft(row.draft, allowModel);
  if (row.reviewed_draft !== undefined) { if (!allowReviewed) invalid(); result.reviewed_draft = draft(row.reviewed_draft, allowModel); }
  if (row.asset !== undefined) result.asset = assetReference(row.asset);
  const imageReferences = (value: unknown) => {
    const seen = new Set<string>();
    return list(value, 5).map(value => {
      const reference = record(value); closed(reference, ['asset', 'weight', 'purpose', 'source_note']);
      const asset = assetReference(reference.asset), weight = number(reference.weight, Number.MIN_VALUE, 1);
      if (asset.kind !== 'image' || seen.has(asset.asset_id)) invalid(); seen.add(asset.asset_id);
      return { asset: { ...asset, kind: 'image' as const }, weight, ...checkedImageReferenceMetadata(reference) };
    });
  };
  if (row.references !== undefined) {
    if (imageKind !== 'image_reference') invalid(); result.references = imageReferences(row.references);
  }
  if (row.prompt !== undefined) {
    if (!['image_prompt', 'image_style', 'storyboard_prompt'].includes(imageKind || '')) invalid(); const prompt = record(row.prompt); closed(prompt, ['prompt', 'references', 'document_sources']);
    const documentSources = prompt.document_sources === undefined ? undefined : list(prompt.document_sources, 2).map(mediaSource);
    if (documentSources?.some(source => source.kind !== 'CREATIVE_DOCUMENT') || documentSources && new Set(documentSources.map(source => source.id)).size !== documentSources.length) invalid();
    result.prompt = { prompt: text(prompt.prompt, 16000, false, true), references: imageReferences(prompt.references), ...(documentSources ? { document_sources: documentSources } : {}) };
  }
  if (row.candidate !== undefined) {
    const candidate = record(row.candidate);
    if (!['image', 'video', 'audio', 'timeline'].includes(candidate.owner as string) || Object.keys(candidate).some(key => !['owner', 'job_id', 'job_version', 'request_digest', 'asset'].includes(key))) invalid();
    result.candidate = { owner: candidate.owner as StudioGraphMediaCandidate['owner'], job_id: resourceId(candidate.job_id),
      job_version: integer(candidate.job_version, 1), request_digest: digest(candidate.request_digest), asset: assetReference(candidate.asset) };
    if (result.candidate.owner === 'timeline' && result.candidate.asset.kind !== 'video') invalid();
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
  if (row.kind === 'CREATIVE_DOCUMENT' && row.asset_kind == null) return { ...base, kind: 'CREATIVE_DOCUMENT' };
  if (row.kind !== 'ASSET' || !['image', 'video', 'audio'].includes(row.asset_kind as string)) invalid();
  return { ...base, kind: 'ASSET', asset_kind: row.asset_kind as 'image' | 'video' | 'audio' };
}
function recordedMediaCommand(value: unknown): RecordedGraphMediaCommand {
  const row = record(value); closed(row, ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'image_source', 'image_references', 'mask_source', 'video_reference', 'storyboard_shot']);
  const operation = mediaOperation(row.operation_id, false, true), resolved = mediaParameterValues(row.parameters, operation, false,
    operation === 'm5.image.upscale' || row.image_source !== undefined || row.image_references !== undefined || row.mask_source !== undefined || operation === 'm5.image.reference' || operation === 'm5.image.inpaint');
  if (operation === 'm5.image.upscale' && (row.prompt !== '' || row.allow_cloud !== false)) invalid();
  const requestId = text(row.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) invalid();
  const sourceSnapshots = list(row.source_snapshots, 8).map(mediaSource);
  if (sourceSnapshots.some(source => source.kind !== 'ASSET') && !GRAPH_IMAGE_OPERATIONS.includes(operation as GraphImageOperation) && !GRAPH_VIDEO_OPERATIONS.includes(operation as typeof GRAPH_VIDEO_OPERATIONS[number])) invalid();
  return { operation_id: operation, request_id: requestId, provider_id: row.provider_id == null ? null : resourceId(row.provider_id),
    model_id: row.model_id == null ? null : resourceId(row.model_id), prompt: text(row.prompt, 16000, false, true),
    parameters: Object.fromEntries(Object.entries(resolved).filter((item): item is [string, string | number] => item[1] !== null)),
    source_snapshots: sourceSnapshots, allow_cloud: bool(row.allow_cloud), license_note: text(row.license_note, 2000, false, true),
    ...checkedImageRuntimeInputs(row, sourceSnapshots, operation), ...checkedVideoReference(row.video_reference, sourceSnapshots, operation), ...storyboardShotFields(row.storyboard_shot, sourceSnapshots, operation) };
}
function productionRecipe(value: unknown, operation: string): ProductionRecipe {
  const row = record(value); closed(row, ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'workflow', 'defaults', 'denoising_strength', 'output_profile', 'timeline',
    'image_recipe_id', 'reference_weights', 'reference_semantics', 'mask_semantics', 'video_recipe_id', 'timing', 'structural_only', 'inference_verified', 'reference_video_execution', ...(operation === 'm5.image.upscale' ? ['source_dimensions', 'target_dimensions'] : []),
    ...(operation === 'm9.timeline.multitrack' ? ['export_profile'] : [])]);
  if (row.contract !== 'studio-execution-recipe/1' || row.operation_id !== operation || row.automatic_fallback !== false
    || !['ORIGINAL_HTTP_PROVIDER', 'COMFYUI_BUILTIN_IMAGE', 'AUTOMATIC1111_IMAGE', 'LOCAL_FFMPEG', 'COMFYUI_BUILTIN_VIDEO'].includes(row.adapter as string)
    || JSON.stringify(row).length > 131072) invalid();
  digest(row.recipe_digest);
  checkedImageRecipeFields(row, operation); checkedVideoRecipe(row, operation);
  return row as ProductionRecipe;
}
function graphTimelineCommand(value: unknown): GraphTimelineCommand {
  const row = record(value); closed(row, ['operation_id', 'request_id', 'timeline_snapshot', 'edit_operations', 'source_bindings', 'export_profile']);
  if (row.operation_id !== 'm9.timeline.multitrack') invalid();
  const requestId = text(row.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) invalid();
  const bindings = list(row.source_bindings, 8).map(value => { const binding = record(value); closed(binding, ['port', 'clip_id', 'asset']);
    return { port: binding.port, clip_id: binding.clip_id, asset: assetReference(binding.asset) }; });
  let checked; try { checked = checkedGraphTimelineParameters({ timeline_snapshot: row.timeline_snapshot, edit_operations: row.edit_operations,
    source_bindings: bindings.map(({ port, clip_id }) => ({ port, clip_id })), export_profile: row.export_profile }); } catch { return invalid(); }
  return { ...checked, operation_id: 'm9.timeline.multitrack', request_id: requestId,
    source_bindings: checked.source_bindings.map((binding, index) => ({ ...binding, asset: bindings[index].asset })) };
}
function timelineProductionPreview(value: unknown, projectId: string, branchId: string | null): GraphTimelineProductionPreview {
  const row = record(value); closed(row, ['contract', 'novel_id', 'branch_id', 'request_id', 'operation_id', 'preview_digest', 'request_digest', 'command', 'provider',
    'execution_recipe', 'sources', 'product_acceptance', 'execution_available', 'automatic_dispatch', 'output_policy',
    'timeline_snapshot', 'source_timeline_snapshot', 'timeline_edit_proof', 'export_profile']);
  if (row.novel_id !== projectId || (row.branch_id ?? null) !== branchId) mismatch();
  const command = graphTimelineCommand(row.command);
  if (row.contract !== 'studio-production-preview/1' || row.request_id !== command.request_id || row.operation_id !== command.operation_id || row.provider !== null
    || row.product_acceptance !== 'LOCAL_REQUIRED' || row.execution_available !== true || row.automatic_dispatch !== false || row.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW') invalid();
  const recipe = productionRecipe(row.execution_recipe, command.operation_id);
  closed(recipe, ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'output_profile', 'timeline', 'export_profile']);
  if (recipe.adapter !== 'LOCAL_FFMPEG') invalid();
  let timeline, finalSnapshot, baseSnapshot;
  try { timeline = checkedTimeline(recipe.timeline); finalSnapshot = checkedGraphTimelineSnapshot(row.timeline_snapshot); baseSnapshot = checkedGraphTimelineSnapshot(row.source_timeline_snapshot);
    if (timelineExportKey(checkedTimelineExportProfile(recipe.export_profile)) !== timelineExportKey(command.export_profile)
      || timelineExportKey(checkedTimelineExportProfile(row.export_profile)) !== timelineExportKey(command.export_profile)) invalid(); } catch { return invalid(); }
  const edited = command.edit_operations.length + command.source_bindings.length > 0;
  if (recipe.output_profile !== command.export_profile.preset || JSON.stringify(baseSnapshot) !== JSON.stringify(command.timeline_snapshot)
    || finalSnapshot.id !== baseSnapshot.id || finalSnapshot.version !== baseSnapshot.version + (edited ? 1 : 0)) invalid();
  let proof: GraphTimelineProductionPreview['timeline_edit_proof'] = null;
  if (edited) { const rawProof = record(row.timeline_edit_proof); closed(rawProof, ['request_id', 'request_digest', 'input_version', 'input_digest', 'output_digest']);
    if (rawProof.request_id !== command.request_id || rawProof.input_version !== baseSnapshot.version || rawProof.input_digest !== baseSnapshot.digest || rawProof.output_digest !== finalSnapshot.digest) invalid();
    proof = { request_id: command.request_id, request_digest: digest(rawProof.request_digest), input_version: baseSnapshot.version, input_digest: baseSnapshot.digest, output_digest: finalSnapshot.digest };
  } else if (row.timeline_edit_proof !== null || finalSnapshot.digest !== baseSnapshot.digest) invalid();
  const expectedSources = timelineSources(timeline), sources = list(row.sources, 30).map(value => {
    const source = record(value); closed(source, ['snapshot', 'measured']); const snapshot = mediaSource(source.snapshot);
    if (source.measured !== null || snapshot.kind !== 'ASSET' || snapshot.reference_only !== undefined) invalid(); return { snapshot, measured: null };
  });
  if (sources.length !== expectedSources.length || sources.some((item, index) => (['id', 'kind', 'asset_kind', 'version', 'digest'] as const).some(key =>
    item.snapshot[key] !== expectedSources[index][key]))) invalid();
  return { contract: 'studio-production-preview/1', novel_id: projectId, branch_id: branchId, operation_id: command.operation_id, request_id: command.request_id,
    command, provider: null, preview_digest: digest(row.preview_digest), request_digest: digest(row.request_digest), execution_recipe: recipe,
    sources: sources as GraphTimelineProductionPreview['sources'], timeline_snapshot: finalSnapshot, source_timeline_snapshot: baseSnapshot,
    timeline_edit_proof: proof, export_profile: command.export_profile, product_acceptance: 'LOCAL_REQUIRED', execution_available: true,
    automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
}
function productionPreview(value: unknown, projectId: string, branchId: string | null): ProductionPreview {
  const row = record(value); closed(row, ['contract', 'novel_id', 'branch_id', 'request_id', 'operation_id', 'preview_digest', 'request_digest', 'command', 'provider',
    'execution_recipe', 'sources', 'product_acceptance', 'execution_available', 'automatic_dispatch', 'output_policy']);
  if (row.novel_id !== projectId || (row.branch_id ?? null) !== branchId) mismatch();
  const command = recordedMediaCommand(row.command), operation = mediaOperation(row.operation_id, false, true);
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
  const executionRecipe = productionRecipe(row.execution_recipe, operation); checkedImageRecipeCommand(executionRecipe, command);
  return { contract: 'studio-production-preview/1', novel_id: projectId, branch_id: branchId, operation_id: operation, request_id: command.request_id,
    command: command as ProductionPreview['command'], provider, preview_digest: digest(row.preview_digest), request_digest: digest(row.request_digest),
    execution_recipe: executionRecipe, product_acceptance: 'LOCAL_REQUIRED', execution_available: true,
    automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
}
function mediaJob(value: unknown, command?: RecordedGraphMediaCommand | GraphTimelineCommand): StudioGraphMediaJob {
  const row = record(value); closed(row, ['id', 'version', 'status', 'request_digest', 'receipt_digest', 'output_candidate', 'approved_asset_version', 'error_code',
    'needs_reconciliation', 'execution_state', 'cancellation_mode', 'remote_compute_may_continue', ...(command?.operation_id === 'm5.image.upscale' ? ['processing_proof'] : [])]);
  if (!mediaJobStatuses.includes(row.status as ProductionJob['status'])) invalid();
  let candidate: ProductionJob['output_candidate'] = null;
  if (row.output_candidate !== null) {
    const c = record(row.output_candidate); closed(c, ['id', 'version', 'digest', 'kind']);
    if (!['image', 'video', 'audio'].includes(c.kind as string)) invalid();
    candidate = { id: resourceId(c.id), version: integer(c.version, 1), digest: digest(c.digest), kind: c.kind as 'image' | 'video' | 'audio' };
  }
  const proof = command?.operation_id === 'm5.image.upscale' && row.processing_proof != null ? checkedImageUpscaleProof(row.processing_proof, command, candidate) : undefined;
  if (command?.operation_id === 'm5.image.upscale' && candidate && !proof) invalid();
  return { ...(proof ? { processing_proof: proof } : {}), id: resourceId(row.id), version: integer(row.version, 1), status: row.status as ProductionJob['status'], request_digest: digest(row.request_digest),
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
      const timeline = record(p.command).operation_id === 'm9.timeline.multitrack';
      const command = timeline ? graphTimelineCommand(p.command) : recordedMediaCommand(p.command);
      const production = timeline ? timelineProductionPreview(p.production_preview, projectId, branchId) : productionPreview(p.production_preview, projectId, branchId), captured = production.command;
      if (timeline) { if (JSON.stringify(command) !== JSON.stringify(captured)) invalid(); }
      else {
        if (command.operation_id === 'm9.timeline.multitrack' || captured.operation_id === 'm9.timeline.multitrack') invalid();
        if (command.operation_id !== captured.operation_id || command.request_id !== captured.request_id || command.prompt !== captured.prompt
          || command.provider_id !== captured.provider_id || command.model_id !== captured.model_id || command.allow_cloud !== captured.allow_cloud || command.license_note !== captured.license_note
          || JSON.stringify(command.source_snapshots) !== JSON.stringify(captured.source_snapshots)
          || !sameImageRuntimeInputs(command, captured) || !sameVideoReference(command, captured)
          || Object.entries(command.parameters).some(([key, value]) => captured.parameters[key] !== value)) invalid();
      }
      preview = { node_id: nodeId, input_digest: digest(p.input_digest), preview_digest: digest(p.preview_digest), command, production_preview: production };
    }
    if (source.execution !== null) {
      const e = record(source.execution); closed(e, ['node_id', 'owner', 'job_id', 'status', 'receipt_state', 'send_reserved', 'job', 'review_state', 'review_recovery']);
      if (e.node_id !== nodeId || !['image', 'video', 'audio', 'timeline'].includes(e.owner as string) || !executionStatuses.includes(e.status as ProductionJob['status'])
        || !['RECORDED', 'UNKNOWN_NO_AUTOMATIC_REPLAY'].includes(e.receipt_state as string) || !['NONE', 'REVIEW_RESERVED', 'APPROVED'].includes(e.review_state as string)) invalid();
      const jobId = e.job_id === null ? null : resourceId(e.job_id), job = e.job === null ? null : mediaJob(e.job, preview?.command);
      if (job && job.id !== jobId || job && preview && job.request_digest !== preview.production_preview.request_digest) invalid();
      const expectedOwner = preview?.command.operation_id === 'm9.timeline.multitrack' ? 'timeline' : preview?.command.operation_id.startsWith('m5.') ? 'image' : preview?.command.operation_id.startsWith('m7.') ? 'video' : 'audio';
      if (preview && e.owner !== expectedOwner) invalid();
      if (e.owner === 'timeline' && job && (job.remote_compute_may_continue || job.output_candidate && job.output_candidate.kind !== 'video')) invalid();
      let reviewRecovery: StudioGraphMediaExecution['review_recovery'];
      if (e.review_recovery !== undefined) {
        const proof = record(e.review_recovery); closed(proof, ['contract', 'job_version', 'request_digest']);
        if (proof.contract !== 'creative-graph-review-recovery/1' || !jobId || e.status !== 'REVIEWING' || e.review_state !== 'REVIEW_RESERVED') invalid();
        reviewRecovery = { contract: 'creative-graph-review-recovery/1', job_version: integer(proof.job_version, 1, Number.MAX_SAFE_INTEGER),
          request_digest: digest(proof.request_digest) };
        if (job && (job.status !== 'REVIEWING' || job.version !== reviewRecovery.job_version || job.request_digest !== reviewRecovery.request_digest)) invalid();
      }
      execution = { node_id: nodeId, owner: e.owner as StudioGraphMediaExecution['owner'], job_id: jobId, status: code(e.status),
        receipt_state: e.receipt_state as StudioGraphMediaExecution['receipt_state'], send_reserved: bool(e.send_reserved),
        job: hidePrivate ? null : job, review_state: e.review_state as StudioGraphMediaExecution['review_state'],
        ...(reviewRecovery ? { review_recovery: reviewRecovery } : {}) };
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
  const timelineEnabled = capabilities.timeline_execution === true;
  const imageEnabled = capabilities.image_graph === true, productionEnabled = capabilities.production_graph === true, videoEnabled = capabilities.video_graph === true;
  if (videoEnabled) { if (!mediaEnabled || capabilities.video_graph_schema_version !== 5 || capabilities.video_graph_evidence !== 'LOCAL_REQUIRED' || capabilities.storyboard_video_approval_required !== true || capabilities.automatic_video_dispatch !== false) invalid(); expectedCapabilities.video_graph = true; expectedCapabilities.video_graph_schema_version = 5; expectedCapabilities.video_graph_evidence = 'LOCAL_REQUIRED'; expectedCapabilities.storyboard_video_approval_required = true; expectedCapabilities.automatic_video_dispatch = false; }
  if (productionEnabled) {
    if (!imageEnabled || !mediaEnabled || capabilities.production_graph_schema_version !== 4 || capabilities.planning_evidence !== 'SOURCE_BOUND' || capabilities.image_control_execution !== false || capabilities.image_upscale_execution !== true) invalid();
    expectedCapabilities.production_graph = true; expectedCapabilities.production_graph_schema_version = 4; expectedCapabilities.planning_evidence = 'SOURCE_BOUND'; expectedCapabilities.image_control_execution = false;
  } else if (capabilities.production_graph_schema_version !== undefined || capabilities.planning_evidence !== undefined || capabilities.image_control_execution !== undefined) invalid();
  if (imageEnabled) {
    if (!mediaEnabled || capabilities.image_graph_schema_version !== 4 || capabilities.image_graph_evidence !== 'LOCAL_REQUIRED'
      || capabilities.image_reference_semantics !== 'WEIGHTED_PIXEL_INITIALIZATION' || capabilities.image_upscale_execution !== productionEnabled) invalid();
    expectedCapabilities.image_graph = true; expectedCapabilities.image_graph_schema_version = 4; expectedCapabilities.image_graph_evidence = 'LOCAL_REQUIRED';
    expectedCapabilities.image_reference_semantics = 'WEIGHTED_PIXEL_INITIALIZATION'; expectedCapabilities.image_upscale_execution = productionEnabled;
  } else if (capabilities.image_graph_schema_version !== undefined || capabilities.image_graph_evidence !== undefined
    || capabilities.image_reference_semantics !== undefined || capabilities.image_upscale_execution !== undefined) invalid();
  if (timelineEnabled) { if (!mediaEnabled || capabilities.timeline_evidence !== 'LOCAL_REQUIRED' || capabilities.automatic_timeline_dispatch !== false) invalid();
    expectedCapabilities.timeline_execution = true; expectedCapabilities.timeline_evidence = 'LOCAL_REQUIRED'; expectedCapabilities.automatic_timeline_dispatch = false;
  } else if (capabilities.timeline_evidence !== undefined || capabilities.automatic_timeline_dispatch !== undefined) invalid();
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
  const definitions = list(row.definitions, definitionIds.length).map(item => catalogDefinition(item, mediaEnabled, videoEnabled));
  const expectedDefinitions = videoEnabled ? [...videoGraphDefinitions] : [...(modelEnabled ? modelDefinitionIds : localDefinitionIds), ...(mediaEnabled ? mediaDefinitionIds : []), ...(timelineEnabled ? ['timeline_export' as const] : []), ...(imageEnabled ? imageDefinitionIds : []), ...(productionEnabled ? productionGraphDefinitions : [])];
  if (definitions.length !== expectedDefinitions.length || new Set(definitions.map(item => item.id)).size !== definitions.length
    || definitions.some(item => !expectedDefinitions.includes(item.id))) invalid();
  let mediaLimits: StudioGraphCatalog['media_limits'];
  if (mediaEnabled) {
    const value = record(row.media_limits); if (value.nodes !== 24 || value.generators !== 4 || value.history !== 80) invalid();
    mediaLimits = { nodes: 24, generators: 4, history: 80 };
  } else if (row.media_limits !== undefined) invalid();
  return { definitions, limits: expectedLimits, capabilities: expectedCapabilities, ...(mediaLimits ? { media_limits: mediaLimits } : {}) };
}

/** Reuse the canonical input decoder for local draft recovery; grants no authority. */
export function checkedStudioGraphDraft(value: unknown): StudioGraphDefinition { return definition(value, true); }

export function createStudioGraphClient(projectId: string, context: Pick<CollaborationContext, 'scope'>, transport: StudioGraphTransport) {
  const capturedScope = context.scope ? { ...context.scope } : undefined;
  const originalTransport = transport;
  const admitted = () => { if (capturedScope && capturedScope.projectId !== projectId) mismatch(); };
  transport = {
    json<T>(...args: Parameters<StudioGraphTransport['json']>): Promise<T> {
      admitted(); return originalTransport.json<T>(...args);
    },
    ...(originalTransport.blob ? { blob: (url: string) => { admitted(); return originalTransport.blob!(url); } } : {}),
  };
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
  const graphUrl = (value: unknown) => `${base}/graphs/${encodeURIComponent(resourceId(value, true))}`;
  const runUrl = (value: unknown) => `${base}/graph-runs/${encodeURIComponent(resourceId(value, true))}`;
  const observedGraphs = new Map<string, { version: number; can_edit: boolean; enabledIds: string[]; definition_digest: string;
    schemaVersion: number; nodes: Record<string, StudioGraphDefinitionId>; planningSnapshots: Record<string, unknown>; shotPins: Record<string, { shot_id?: string; shot_version?: number; shot_digest?: string; document_snapshot?: unknown }> }>();
  const observedRuns = new Map<string, string>();
  const observedReviewRecoveries = new Map<string, { version: number; workflow: string;
    nodes: Map<string, { owner: StudioGraphMediaExecution['owner']; jobId: string;
      proof: NonNullable<StudioGraphMediaExecution['review_recovery']> }> }>();
  const recoveryWorkflow = (run: StudioGraphRun) => JSON.stringify([run.graph_id, run.graph_version,
    run.status, run.current_node_id, run.reviewed, run.cache,
    Object.entries(run.node_states).sort(([left], [right]) => left.localeCompare(right)).map(([nodeId, state]) => [nodeId, state.status])]);

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
    const assetNodes = checkedDefinition.nodes.filter(node => ['asset_reference', 'director_plan', 'storyboard_plan'].includes(node.definition_id));
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
      schemaVersion: value.definition.schema_version, planningSnapshots: Object.fromEntries(value.definition.nodes.filter(node => node.parameters.document_snapshot).map(node => [node.id, node.parameters.document_snapshot])), nodes: Object.fromEntries(value.definition.nodes.map(node => [node.id, node.definition_id])),
      shotPins: Object.fromEntries(value.definition.nodes.filter(node => node.definition_id === 'storyboard_shot').map(node => { const edge = value.definition.edges.find(edge => edge.target_node_id === node.id && edge.target_port === 'storyboard'); const source = value.definition.nodes.find(source => source.id === edge?.source_node_id); return [node.id, { shot_id: node.parameters.shot_id, shot_version: node.parameters.shot_version, shot_digest: node.parameters.shot_digest, document_snapshot: source?.parameters.document_snapshot }]; })),
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
    const observed = observedGraphs.get(graphId), knownGraph = observed?.version === row.graph_version ? observed : undefined;
    const rawStates = record(row.node_states), stateIds = Object.keys(rawStates);
    if (stateIds.length > 24) invalid();
    const nodeStates = Object.fromEntries(stateIds.map(nodeId => {
      const state = record(rawStates[nodeId]);
      if (!nodeStatuses.includes(state.status as StudioGraphNodeStatus)) invalid();
      const nodeState: StudioGraphNodeState = { status: state.status as StudioGraphNodeStatus,
        output: hideOutputs ? null : output(state.output, modelOutput, state.status === 'SUCCEEDED' && (!knownGraph
          || knownGraph.schemaVersion === 3 && knownGraph.nodes[nodeId] === 'human_review'), knownGraph && [4, 5].includes(knownGraph.schemaVersion) ? knownGraph.nodes[nodeId] : undefined), error: state.error === null ? null : { code: code(record(state.error).code) } };
      const planning = nodeState.output?.storyboard || (nodeState.output?.direction && 'content' in nodeState.output.direction ? nodeState.output.direction : undefined);
      if (knownGraph && planning && JSON.stringify(planning.document_snapshot) !== JSON.stringify(knownGraph.planningSnapshots[nodeId])) invalid();
      if (knownGraph && nodeState.output?.shot) { const pin = knownGraph.shotPins[nodeId], shot = nodeState.output.shot; if (!pin || shot.shot_id !== pin.shot_id || shot.shot_version !== pin.shot_version || shot.shot_digest !== pin.shot_digest || JSON.stringify(shot.document_snapshot) !== JSON.stringify(pin.document_snapshot)) invalid(); }
      if (knownGraph?.schemaVersion === 5 && nodeState.output?.candidate && nodeState.output.candidate.asset?.kind !== 'video') invalid();
      if (knownGraph && nodeState.output?.candidate && (knownGraph.nodes[nodeId] === 'timeline_export'
        ? nodeState.output.candidate.owner !== 'timeline' : !['media_generate', 'image_generate', 'image_upscale', 'video_generate'].includes(knownGraph.nodes[nodeId]) || nodeState.output.candidate.owner === 'timeline'
          || ['image_generate', 'image_upscale'].includes(knownGraph.nodes[nodeId]) && nodeState.output.candidate.owner !== 'image' || knownGraph.nodes[nodeId] === 'video_generate' && nodeState.output.candidate.owner !== 'video')) invalid();
      return [id(nodeId), nodeState];
    }));
    const currentNodeId = row.current_node_id === null ? null : id(row.current_node_id);
    if (currentNodeId !== null && !Object.hasOwn(nodeStates, currentNodeId)) invalid();
    if (model && !Object.hasOwn(nodeStates, model.node_id)) invalid();
    if (media?.nodes.some(node => !Object.hasOwn(nodeStates, node.node_id))) invalid();
    if (knownGraph && media?.nodes.some(node => !['media_generate', 'timeline_export', 'image_generate', 'image_upscale', 'video_generate'].includes(knownGraph.nodes[node.node_id])
      || ['image_generate', 'image_upscale'].includes(knownGraph.nodes[node.node_id]) && (node.execution && node.execution.owner !== 'image'
        || node.preview && !(knownGraph.nodes[node.node_id] === 'image_upscale' ? node.preview.command.operation_id === 'm5.image.upscale' : GRAPH_IMAGE_OPERATIONS.includes(node.preview.command.operation_id as GraphImageOperation)))
      || knownGraph.nodes[node.node_id] === 'video_generate' && (node.execution && node.execution.owner !== 'video' || node.preview && !GRAPH_VIDEO_OPERATIONS.includes(node.preview.command.operation_id as typeof GRAPH_VIDEO_OPERATIONS[number]))
      || node.execution && (knownGraph.nodes[node.node_id] === 'timeline_export' ? node.execution.owner !== 'timeline' : node.execution.owner === 'timeline')
      || node.preview && (knownGraph.nodes[node.node_id] === 'timeline_export') !== (node.preview.command.operation_id === 'm9.timeline.multitrack'))) invalid();
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
    const recoveryNodes = new Map<string, { owner: StudioGraphMediaExecution['owner']; jobId: string;
      proof: NonNullable<StudioGraphMediaExecution['review_recovery']> }>();
    for (const node of result.media_runtime?.nodes || []) {
      const execution = node.execution;
      if (execution?.job_id && execution.review_recovery) recoveryNodes.set(node.node_id,
        { owner: execution.owner, jobId: execution.job_id, proof: execution.review_recovery });
    }
    if (recoveryNodes.size) observedReviewRecoveries.set(runId,
      { version: result.version, workflow: recoveryWorkflow(result), nodes: recoveryNodes });
    else observedReviewRecoveries.delete(runId);
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
    // Only an explicitly observed original REVIEWING receipt permits a masked
    // maintenance reply. Ordinary execution/refresh still require their job.
    const recovery = action === 'reconcile' ? observedReviewRecoveries.get(runId) : undefined;
    const original = recovery?.nodes.get(payload.node_id);
    const recoveryRequest = recovery?.version === payload.expected_version && original
      && original.proof.job_version === payload.expected_job_version && original.proof.request_digest === payload.expected_request_digest;
    return transport.json(`${runUrl(runId)}/media/${action}`, 'POST', payload).then(value => {
      const result = checkedMediaRun(value, runId, payload.node_id), execution = result.media_runtime!.nodes.find(item => item.node_id === payload.node_id)?.execution;
      const job = execution?.job;
      if (job) { if (job.request_digest !== payload.expected_request_digest) invalid(); return result; }
      if (!recoveryRequest || !recovery || !original || !result.stale || !execution
        || execution.job_id !== original.jobId || execution.owner !== original.owner || execution.review_state !== 'REVIEW_RESERVED'
        || execution.receipt_state !== 'RECORDED' || recoveryWorkflow(result) !== recovery.workflow) invalid();
      if (execution.status === 'AWAITING_REVIEW') {
        if (result.version !== payload.expected_version + 1 || execution.review_recovery !== undefined) invalid();
      } else if (execution.status === 'REVIEWING') {
        if (![payload.expected_version, payload.expected_version + 1].includes(result.version)
          || execution.review_recovery?.job_version !== payload.expected_job_version
          || execution.review_recovery?.request_digest !== payload.expected_request_digest) invalid();
      } else invalid();
      return result;
    });
  }

  function checkedTimelineRow(value: unknown, expectedId?: string): StudioTimelineRow {
    const row = record(value); if (row.novel_id !== projectId || (row.branch_id ?? null) !== (capturedScope?.branchId ?? null)) mismatch();
    let snapshot; try { snapshot = checkedGraphTimelineSnapshot({ id: row.id, version: row.version, digest: row.timeline_digest }); } catch { return invalid(); }
    if (expectedId && snapshot.id !== expectedId) mismatch();
    let timeline; try { timeline = checkedTimeline(row.timeline); } catch { return invalid(); }
    return { id: snapshot.id, version: snapshot.version, timeline_digest: snapshot.digest, title: text(row.title, 240), timeline,
      created_at: text(row.created_at, 100), updated_at: text(row.updated_at, 100) };
  }
  const planningDocuments = (signal?: AbortSignal): Promise<{ documents: PlanningDocument[] }> => transport.json(`${base}/graphs/planning-documents`, 'GET', undefined, signal).then(value => {
    const recordValue = record(value); owner(recordValue); closed(recordValue, ['project_id', 'scope', 'documents']); const documents = list(recordValue.documents, 100).map(checkedPlanningDocument); if (new Set(documents.map(document => document.id)).size !== documents.length) invalid(); return { documents };
  });
  return {
    ...createStudioProviderClient(base, transport, owner),
    graphTimelineList: (signal?: AbortSignal): Promise<{ items: StudioTimelineRow[] }> => transport.json(`${base}/production/timelines`, 'GET', undefined, signal).then(value => {
      const rows = list(record(value).items, 25).map(value => checkedTimelineRow(value)); if (new Set(rows.map(row => row.id)).size !== rows.length) invalid(); return { items: rows };
    }),
    graphTimelineGet: (timelineId: string, signal?: AbortSignal): Promise<StudioTimelineRow> => {
      let snapshotId; try { snapshotId = graphTimelineId(timelineId); } catch { return invalid(true); }
      return transport.json(`${base}/production/timelines/${encodeURIComponent(snapshotId)}`, 'GET', undefined, signal).then(value => checkedTimelineRow(value, timelineId));
    },
    catalog: (signal?: AbortSignal): Promise<StudioGraphCatalog> => transport.json(`${base}/graphs/catalog`, 'GET', undefined, signal).then(catalog),
    imageCatalog: (signal?: AbortSignal): Promise<StudioGraphCatalog> => transport.json(`${base}/graphs/catalog?include_image=true`, 'GET', undefined, signal).then(catalog),
    videoCatalog: (signal?: AbortSignal): Promise<StudioGraphCatalog> => transport.json(`${base}/graphs/catalog?include_video=true`, 'GET', undefined, signal).then(catalog),
    videoStoryboard: (documentId: string, signal?: AbortSignal) => transport.json(`/api/novels/${encodeURIComponent(projectId)}/experimental/creative/documents/${encodeURIComponent(resourceId(documentId, true))}/storyboard`, 'GET', undefined, signal).then(value => checkedStoryboardReceipt(value, documentId)),
    productionCatalog: (signal?: AbortSignal): Promise<StudioGraphCatalog> => transport.json(`${base}/graphs/catalog?include_image=true&include_production=true`, 'GET', undefined, signal).then(catalog),
    planningDocuments,
    /** Existing projection plus original-owner pin checks; never adopts a newer version.
     * The projection has no digest field. Verify the original version/digest both
     * before and after reading it, relying on the owner's monotonic revisions.
     * This is a display fence; original execution still checks the pin itself.
     */
    readDirectorWorkspace: async (value: PlanningSnapshot, signal?: AbortSignal) => {
      const snapshot = checkedPlanningSnapshot(value, true);
      const currentPin = async () => {
        if (signal?.aborted) throw new DOMException('Read aborted', 'AbortError');
        const { documents } = await planningDocuments(signal);
        if (signal?.aborted) throw new DOMException('Read aborted', 'AbortError');
        const document = documents.find(row => row.id === snapshot.id);
        if (!document) throw new ApiError({ status: 404, code: 'STUDIO_GRAPH_DIRECTOR_UNAVAILABLE', message: '图绑定的导演文档当前不可读取，请重新核对来源与权限。' });
        if (document.mode !== 'DIRECTOR' || document.version !== snapshot.version || document.digest !== snapshot.digest) {
          throw new ApiError({ status: 409, code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED', message: '导演文档与图中绑定的版本或摘要不同；未显示新版本，请在原文档与图中明确核对。' });
        }
      };
      await currentPin();
      const projection = await createDirectorWorkspaceClient(projectId, transport, capturedScope).readDirectorWorkspace(snapshot.id, signal);
      if (signal?.aborted) throw new DOMException('Read aborted', 'AbortError');
      owner(projection as unknown as Record<string, unknown>);
      if (projection.document.mode !== 'DIRECTOR' || projection.document.version !== snapshot.version) {
        throw new ApiError({ status: 409, code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED', message: '导演文档在读取时已变化，未采用此结果，请重新核对来源。' });
      }
      await currentPin();
      return projection;
    },
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
type StudioGraphMediaClient = Pick<ReturnType<typeof createStudioGraphClient>, 'previewMedia' | 'dispatchMedia' | 'executeMedia' | 'refreshMedia' | 'reconcileMedia' | 'reviewMedia' | 'mediaCandidate' | 'graphTimelineList' | 'graphTimelineGet'>;
type StudioGraphImageClient = Pick<ReturnType<typeof createStudioGraphClient>, 'imageCatalog' | 'productionCatalog' | 'planningDocuments' | 'readDirectorWorkspace' | 'videoCatalog' | 'videoStoryboard'>;
export type StudioGraphClient = Omit<ReturnType<typeof createStudioGraphClient>, keyof StudioProviderClient | keyof StudioGraphMediaClient | keyof StudioGraphImageClient>
  & Partial<StudioProviderClient> & Partial<StudioGraphMediaClient> & Partial<StudioGraphImageClient>;
