import { ApiError, type CollaborationContext } from '../api';
import type {
  StudioGraphAction, StudioGraphActionInput, StudioGraphCatalogDefinition, StudioGraphDefinition,
  StudioGraphDefinitionId, StudioGraphDraft, StudioGraphNode, StudioGraphOutput, StudioGraphParameters,
  StudioGraphParameterSchema, StudioGraphPort, StudioGraphPosition, StudioGraphPreflight,
  StudioGraphPreflightInput, StudioGraphCreateInput, StudioGraphSaveInput, StudioGraphRunCreateInput,
  StudioGraphRecord, StudioGraphReferenceState, StudioGraphRun, StudioGraphRunStatus, StudioGraphCatalog,
  StudioGraphScope, StudioGraphOwner, StudioGraphNodeState, StudioGraphNodeStatus,
  StudioGraphModelCapabilities, StudioGraphModelPreviewInput, StudioGraphModelDispatchInput, StudioGraphModelRefreshInput,
} from './studioGraphTypes';
import { graphModelCapabilities, graphModelRuntime } from './studioGraphModelContract';

/** Inject the existing Studio transport; graph operations never look up credentials. */
export type StudioGraphTransport = {
  json<T>(url: string, method?: string, body?: unknown, signal?: AbortSignal, idempotencyKey?: string): Promise<T>;
};

const localDefinitionIds: readonly StudioGraphDefinitionId[] = ['text_input', 'text_reference', 'draft_prepare', 'manual_transform', 'director_note', 'human_review', 'asset_reference'];
const definitionIds: readonly StudioGraphDefinitionId[] = [...localDefinitionIds, 'text_generate'];
const statuses: readonly StudioGraphRunStatus[] = ['QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'PAUSED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'];
const nodeStatuses: readonly StudioGraphNodeStatus[] = ['PENDING', 'WAITING_APPROVAL', 'QUEUED', 'WORKING', 'SUCCEEDED', 'FAILED', 'SKIPPED', 'REJECTED'];
const actions: readonly StudioGraphAction[] = ['execute', 'approve', 'reject', 'cancel', 'pause', 'resume'];
const portKinds = ['TEXT', 'DIRECTOR_NOTES', 'DRAFT', 'ASSET_REF'] as const;
const parameterKeys: Record<StudioGraphDefinitionId, readonly string[]> = {
  text_input: ['text'], text_reference: [], draft_prepare: [], manual_transform: ['result'],
  director_note: ['note'], human_review: [], asset_reference: ['asset_id', 'version', 'digest', 'kind'],
  text_generate: ['instruction', 'max_output_tokens'],
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
  const result = list(value, 16, input).map(item => id(item, input));
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
  return {};
}
function definition(value: unknown, input = false, unavailable = new Set<string>()): StudioGraphDefinition {
  const row = record(value, input);
  if (row.schema_version !== 1 && row.schema_version !== 2) invalid(input);
  const nodes: StudioGraphNode[] = list(row.nodes, 16, input).map(item => {
    const node = record(item, input), nodeId = id(node.id, input), kind = definitionId(node.definition_id, input);
    if (kind === 'text_generate' && row.schema_version !== 2) invalid(input);
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
function catalogDefinition(value: unknown): StudioGraphCatalogDefinition {
  const row = record(value), kind = definitionId(row.id);
  if (row.version !== 1 || row.model_called !== false || row.executable !== (kind !== 'asset_reference')) invalid();
  function checkedPorts(value: unknown, side: 'inputs' | 'outputs'): StudioGraphPort[] {
    const expected = ports[kind][side];
    const result = list(value, 2).map(item => {
      const port = record(item), portId = id(port.id), required = bool(port.required);
      if (!portKinds.includes(port.type as StudioGraphPort['type']) || expected[portId] !== port.type || port.multiple !== false) invalid();
      if (required !== (side === 'inputs' && portId !== 'direction')) invalid();
      return { id: portId, type: port.type as StudioGraphPort['type'], required, multiple: false as const };
    });
    if (new Set(result.map(port => port.id)).size !== Object.keys(expected).length || result.length !== Object.keys(expected).length) invalid();
    return result;
  }
  if (kind === 'asset_reference' && row.default_parameters !== null) invalid();
  return { id: kind, version: 1, inputs: checkedPorts(row.inputs, 'inputs'), outputs: checkedPorts(row.outputs, 'outputs'),
    parameters_schema: schema(row.parameters_schema, kind),
    default_parameters: kind === 'asset_reference' ? null : parameters(row.default_parameters, kind),
    executable: kind !== 'asset_reference', model_called: false, blockers: list(row.blockers, 16).map(code) };
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
  if (new TextEncoder().encode(JSON.stringify(result)).length > 64_000) invalid();
  return result;
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
  if (modelEnabled) {
    if (capabilities.model_execution_contract !== 'creative-graph-model/1') invalid();
    expectedCapabilities.model_execution = true;
    expectedCapabilities.model_execution_contract = 'creative-graph-model/1';
  } else if (capabilities.model_execution_contract !== undefined) invalid();
  if (Object.entries(expectedLimits).some(([key, value]) => limits[key] !== value)
    || Object.entries(expectedCapabilities).some(([key, value]) => capabilities[key] !== value)) invalid();
  const definitions = list(row.definitions, definitionIds.length).map(catalogDefinition);
  const expectedDefinitions = modelEnabled ? definitionIds : localDefinitionIds;
  if (definitions.length !== expectedDefinitions.length || new Set(definitions.map(item => item.id)).size !== definitions.length
    || definitions.some(item => !expectedDefinitions.includes(item.id))) invalid();
  return { definitions, limits: expectedLimits, capabilities: expectedCapabilities };
}

export function createStudioGraphClient(projectId: string, context: Pick<CollaborationContext, 'scope'>, transport: StudioGraphTransport) {
  const capturedScope = context.scope ? { ...context.scope } : undefined;
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
    const referenceStates: StudioGraphReferenceState[] = list(row.reference_states, 16).map(item => {
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
    const modelCalled = bool(row.model_called);
    if (model ? modelCalled !== (model.execution?.model_called ?? false) : modelCalled) invalid();
    const modelOutput = modelCalled && !!model && ['RESULT_REVIEW', 'TERMINAL'].includes(model.status);
    const rawStates = record(row.node_states), stateIds = Object.keys(rawStates);
    if (stateIds.length > 16) invalid();
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
      cache: { hits: integer(cache.hits, 0, 16), misses: integer(cache.misses, 0, 16), mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' },
      created_at: text(row.created_at, 64), updated_at: text(row.updated_at, 64), model_called: modelCalled, external_calls: 0,
      ...(model ? { model_runtime: model } : {}),
      applied: false, stale, reviewed: bool(row.reviewed), timeout_seconds: 3600, deadline_at: deadline(row.deadline_at) };
    if (observedRuns.has(runId) && observedRuns.get(runId) !== graphId) mismatch();
    observedRuns.set(runId, graphId);
    return result;
  }
  function checkedModelRun(value: unknown, runId: string): StudioGraphRun {
    const result = checkedRun(value, runId, observedRuns.get(runId));
    if (!result.model_runtime) invalid();
    return result;
  }

  return {
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
        reviewed_preview_digest: digest(row.reviewed_preview_digest, true) };
      return transport.json(`${url}/model/dispatch`, 'POST', payload).then(value => {
        const result = checkedModelRun(value, runId);
        if (!result.model_runtime!.execution) invalid();
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

export type StudioGraphClient = ReturnType<typeof createStudioGraphClient>;
