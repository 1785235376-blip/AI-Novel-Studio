import { checkedStudioGraphVideoParameters } from './studioGraphClient';
import { GRAPH_VIDEO_OPERATIONS, type StudioGraphCatalog, type StudioGraphDefinition } from './studioGraphTypes';
import type { ProductionProvider } from './studioProductionClient';

export function selectedVideoBindingNodes(definition: StudioGraphDefinition, selected: readonly string[]) {
  if (definition.schema_version !== 5 || selected.length < 1 || selected.length > 4 || new Set(selected).size !== selected.length)
    throw new Error('请明确选择 1–4 个同一操作的视频生成节点。');
  const nodes = selected.map(id => {
    const matches = definition.nodes.filter(node => node.id === id);
    if (matches.length !== 1 || matches[0].definition_id !== 'video_generate') throw new Error(`节点 ${id}：请选择当前图中的视频生成节点。`);
    return matches[0];
  });
  const operation = nodes[0].parameters.operation_id;
  if (!GRAPH_VIDEO_OPERATIONS.includes(operation as typeof GRAPH_VIDEO_OPERATIONS[number]) || nodes.some(node => node.parameters.operation_id !== operation))
    throw new Error('所选视频节点必须使用同一 operation；未修改任何节点。');
  return nodes;
}

/** Check only selected parameters; other unfinished branches remain valid local drafts. */
export function graphSelectedVideoBinding(definition: StudioGraphDefinition, selected: readonly string[], catalog: StudioGraphCatalog, provider: ProductionProvider) {
  const nodes = selectedVideoBindingNodes(definition, selected), operation = nodes[0].parameters.operation_id;
  if (provider.local !== true || provider.readiness !== 'CONFIGURED_NOT_VERIFIED' || provider.operation_id !== operation)
    throw new Error('请选择当前操作的本地服务配置；配置发现不代表推理已验证。');
  if (!catalog.capabilities.video_graph || nodes.some(node => !catalog.definitions.some(spec => spec.id === node.definition_id && spec.version === node.definition_version)))
    throw new Error('当前目录不支持所选视频节点，请重新读取原目录。');
  const generators = new Set(['media_generate', 'timeline_export', 'image_generate', 'image_upscale', 'video_generate']);
  if (definition.nodes.length > (catalog.media_limits?.nodes ?? 24) || definition.edges.length > catalog.limits.edges
    || definition.nodes.filter(node => generators.has(node.definition_id)).length > (catalog.media_limits?.generators ?? 4))
    throw new Error('当前草稿超过原图节点、连接或生成节点容量；未修改任何绑定。');
  const ids = new Set(selected);
  for (const node of nodes) {
    for (const [field, value] of Object.entries(node.parameters.parameters ?? {})) {
      if (value != null && !provider.supported_parameters.includes(field))
        throw new Error(`节点 ${node.id}：所选配置不支持 parameters.${field}；原值保留，请明确处理后重新预览。`);
    }
    // Reuse the exact Save decoder without normalizing or copying its output back.
    try { checkedStudioGraphVideoParameters({ ...node.parameters, provider_id: provider.provider_id, model_id: provider.model_id, allow_cloud: false }); }
    catch { throw new Error(`节点 ${node.id}：视频参数不符合原保存规则；原参数保留，请在节点中核对。`); }
  }
  const changes = nodes.map(node => ({ nodeId: node.id,
    before: { provider_id: node.parameters.provider_id ?? '', model_id: node.parameters.model_id ?? '', allow_cloud: node.parameters.allow_cloud },
    after: { provider_id: provider.provider_id, model_id: provider.model_id, allow_cloud: false as const } }));
  if (!changes.some(row => row.before.provider_id !== row.after.provider_id || row.before.model_id !== row.after.model_id || row.before.allow_cloud !== false))
    throw new Error('所选节点已使用该本地绑定且 allow_cloud=false；没有可应用的变化。');
  const next = { ...definition, nodes: definition.nodes.map(node => ids.has(node.id)
    ? { ...node, parameters: { ...node.parameters, provider_id: provider.provider_id, model_id: provider.model_id, allow_cloud: false } } : node) };
  if (new TextEncoder().encode(JSON.stringify(next)).length > Math.min(catalog.limits.definition_bytes, 96_000))
    throw new Error('绑定将超过原图定义字节容量；未修改任何节点。');
  return { definition: next, changes };
}
export type SelectedVideoBindingPreview = ReturnType<typeof graphSelectedVideoBinding>;
