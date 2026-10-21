import { checkedStudioGraphDraft } from '../studioGraphClient';
import { graphDraftIncarnation, type StudioGraphDraftOwner } from '../studioGraphLocalDraft';
import type { StudioGraphRecord } from '../studioGraphTypes';

export type CanvasAudioTemplateParameters = Readonly<{ in_ms: number; out_ms: number; gain_db?: number; fade_in_ms?: number; fade_out_ms?: number }>;

/** A parameter copy for one card task. The original Graph remains the template owner. */
export type CanvasAudioWorkflowTemplateRef = Readonly<{
  contract: 'studio-canvas-audio-template/1';
  graph_id: string;
  graph_version: number;
  definition_digest: string;
  execution_digest: string;
  node_id: string;
  parameters: CanvasAudioTemplateParameters;
}>;

const name = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}$/.test(value);
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const ownerFields = ['projectId', 'incarnation', 'actorId', 'actorWorkspaceId', 'mode', 'workspaceId', 'storylineId', 'branchId'] as const;
const safeOwnerId = (value: unknown) => typeof value === 'string' && value.length > 0 && value.length <= 240 && !/[\u0000-\u001f\u007f]/.test(value);
// Original MediaNodeParameters.model_dump() retains these absent fields as null.
// They are absence markers, never template controls or permission to accept values.
const originalAbsentParameters = new Set(['width', 'height', 'steps', 'seed', 'cfg', 'negative_prompt', 'size', 'quality',
  'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate']);

export function captureCanvasAudioWorkflowTemplate(graph: StudioGraphRecord, nodeId: string,
  owner: StudioGraphDraftOwner): CanvasAudioWorkflowTemplateRef {
  if (!object(owner) || ownerFields.some(field => typeof owner[field] !== 'string')
    || !safeOwnerId(owner.projectId) || !safeOwnerId(owner.actorId) || !graphDraftIncarnation(owner.incarnation)
    || (owner.mode === 'local' ? [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].some(Boolean)
      : owner.mode !== 'collaboration' || ![owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].every(safeOwnerId)
        || owner.actorWorkspaceId !== owner.workspaceId)) throw new Error('当前项目实例或身份范围尚未核对。');
  if (!object(graph) || !object(graph.scope) || graph.project_id !== owner.projectId || graph.scope.novel_id !== owner.projectId
    || graph.scope.mode !== owner.mode || graph.can_edit !== true
    || (owner.mode === 'local' ? ['workspace_id', 'storyline_id', 'branch_id'].some(key => (graph.scope as unknown as Record<string, unknown>)[key] != null)
      : graph.scope.mode !== 'collaboration' || graph.scope.workspace_id !== owner.workspaceId
        || graph.scope.storyline_id !== owner.storylineId || graph.scope.branch_id !== owner.branchId)
    || !name(graph.id) || !Number.isSafeInteger(graph.version) || graph.version < 1
    || !digest(graph.definition_digest) || !digest(graph.execution_digest)) throw new Error('原图版本或项目范围不可用于本次任务模板。');

  // The existing Graph contract owns validation and defaults. Media nodes belong to schema 3;
  // schema 2 is the original text-model graph and must never be relabelled as a media graph.
  const rawDefinition = graph.definition;
  const definition = checkedStudioGraphDraft(rawDefinition && Array.isArray(rawDefinition.nodes) ? {
    ...rawDefinition, nodes: rawDefinition.nodes.map(node => object(node) && node.definition_id === 'media_generate'
      && object(node.parameters) && object(node.parameters.parameters) ? { ...node, parameters: { ...node.parameters,
        parameters: Object.fromEntries(Object.entries(node.parameters.parameters).filter(([key, value]) => value !== null || !originalAbsentParameters.has(key))) } } : node),
  } : rawDefinition);
  if (definition.schema_version !== 3 || typeof nodeId !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(nodeId)) {
    throw new Error('请选择原媒体图中真实保存的音频截取节点。');
  }
  const references = definition.nodes.filter(node => node.definition_id === 'asset_reference');
  if (!Array.isArray(graph.reference_states) || graph.reference_states.length !== references.length
    || new Set(graph.reference_states.map(state => state?.node_id)).size !== graph.reference_states.length
    || graph.reference_states.some(state => !state || state.state !== 'CURRENT' || !references.some(node => node.id === state.node_id))) {
    throw new Error('原图素材来源已变化或缺少当前版本证明，请重新读取。');
  }
  const node = definition.nodes.find(row => row.id === nodeId);
  if (!node || !node.enabled || node.definition_id !== 'media_generate' || node.parameters.operation_id !== 'm8.audio.trim') {
    throw new Error('该节点不是可用的本地音频截取模板。');
  }
  const values = node.parameters.parameters;
  if (!values || Object.keys(values).some(key => !['in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms'].includes(key))
    || !Number.isSafeInteger(values.in_ms) || !Number.isSafeInteger(values.out_ms)
    || (values.in_ms as number) < 0 || (values.out_ms as number) > 600000
    || (values.out_ms as number) <= (values.in_ms as number) || (values.out_ms as number) - (values.in_ms as number) > 120000
    || Object.hasOwn(values, 'gain_db') && (typeof values.gain_db !== 'number' || !Number.isFinite(values.gain_db) || values.gain_db < -60 || values.gain_db > 12)
    || ['fade_in_ms', 'fade_out_ms'].some(key => Object.hasOwn(values, key) && (typeof values[key] !== 'number'
      || !Number.isSafeInteger(values[key]) || (values[key] as number) < 0 || (values[key] as number) > 120000))
    || ((values.fade_in_ms as number | undefined) ?? 0) + ((values.fade_out_ms as number | undefined) ?? 0) > (values.out_ms as number) - (values.in_ms as number)) {
    throw new Error('原图模板的截取、增益或淡化参数不受支持，请重新读取已保存版本。');
  }
  const parameters: { in_ms: number; out_ms: number; gain_db?: number; fade_in_ms?: number; fade_out_ms?: number } = {
    in_ms: values.in_ms as number, out_ms: values.out_ms as number,
    ...(Object.hasOwn(values, 'gain_db') ? { gain_db: values.gain_db as number } : {}),
    ...(Object.hasOwn(values, 'fade_in_ms') ? { fade_in_ms: values.fade_in_ms as number } : {}),
    ...(Object.hasOwn(values, 'fade_out_ms') ? { fade_out_ms: values.fade_out_ms as number } : {}),
  };
  return Object.freeze({ contract: 'studio-canvas-audio-template/1' as const,
    graph_id: graph.id, graph_version: graph.version, definition_digest: graph.definition_digest,
    execution_digest: graph.execution_digest, node_id: nodeId,
    parameters: Object.freeze(parameters) });
}
