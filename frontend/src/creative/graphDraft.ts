import { productionGraphDefinitions } from './studioProductionGraphContract';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphEdge, StudioGraphNode } from './studioGraphTypes';

export const graphId = (prefix = 'node') => `${prefix}_${crypto.randomUUID().replace(/-/g, '')}`;
export const blankGraph = (): StudioGraphDefinition => ({ schema_version: 1, title: '独立创作图', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } });
export const imageGraphDefinitions = ['text_input', 'text_reference', 'asset_reference', 'image_reference', 'image_prompt', 'image_generate', 'media_review', ...productionGraphDefinitions] as const;
export const videoGraphDefinitions = ['text_input', 'text_reference', 'asset_reference', 'director_plan', 'storyboard_plan', 'storyboard_shot', 'video_generate', 'media_review', 'timeline_export'] as const;
export const graphCatalogForSchema = (catalog: readonly StudioGraphCatalogDefinition[], schema: number): StudioGraphCatalogDefinition[] => catalog
  .filter(row => schema === 5 ? videoGraphDefinitions.some(kind => kind === row.id) : schema === 4 ? imageGraphDefinitions.some(kind => kind === row.id) : !['image_reference', 'image_prompt', 'image_generate', ...productionGraphDefinitions, 'storyboard_shot', 'video_generate'].includes(row.id)).map(row =>
  row.id === 'media_review' && schema === 5 ? { ...row, inputs: [{ id: 'candidate', type: 'VIDEO_CANDIDATE', required: true, multiple: false }] } : row.id === 'timeline_export' && schema === 5 ? { ...row, outputs: [{ id: 'candidate', type: 'VIDEO_CANDIDATE', required: false, multiple: false }] } : row.id === 'human_review' && schema !== 3 ? { ...row, outputs: [] } : row);

/** Local authoring feedback mirrors the typed contract; server validation stays authoritative. */
export function connectionIssue(definition: StudioGraphDefinition, catalog: readonly StudioGraphCatalogDefinition[], edge: StudioGraphEdge): string | undefined {
  const source = definition.nodes.find(node => node.id === edge.source_node_id), target = definition.nodes.find(node => node.id === edge.target_node_id);
  if (!source || !target) return '请选择当前图中的两个节点。';
  if (source.id === target.id) return '节点不能连接自身。';
  const descriptors = graphCatalogForSchema(catalog, definition.schema_version);
  const output = descriptors.find(row => row.id === source.definition_id)?.outputs.find(port => port.id === edge.source_port);
  const input = descriptors.find(row => row.id === target.definition_id)?.inputs.find(port => port.id === edge.target_port);
  if (!output || !input) return '请选择真实的输出端口和输入端口。';
  if (output.type !== input.type) return `端口类型不匹配：${output.type} → ${input.type}。`;
  if (['image_reference', 'image_prompt', 'image_generate', 'image_style', 'image_upscale', 'storyboard_prompt'].includes(source.definition_id) || ['image_reference', 'image_prompt', 'image_generate', 'image_style', 'image_upscale', 'storyboard_prompt'].includes(target.definition_id)) {
    if (definition.schema_version !== 4) return '图片节点需要明确采用图片图 v4。';
  }
  if (['image_generate', 'image_upscale'].includes(source.definition_id) && (target.definition_id !== 'media_review' || edge.target_port !== 'candidate')) return '图片候选须连接原媒体审核节点，审核后才输出正式素材。';
  if (['storyboard_shot', 'video_generate'].includes(source.definition_id) || ['storyboard_shot', 'video_generate'].includes(target.definition_id)) { if (definition.schema_version !== 5) return '视频节点需要明确采用视频图 v5。'; }
  if (source.definition_id === 'video_generate' && (target.definition_id !== 'media_review' || edge.target_port !== 'candidate')) return '视频候选必须通过原媒体审核节点。';
  if (target.definition_id === 'timeline_export' && ![3, 5].includes(definition.schema_version)) return '时间线剪辑与导出需要明确升级为媒体图 v3。';
  if (source.definition_id === 'timeline_export' && (target.definition_id !== 'media_review' || edge.target_port !== 'candidate')) return '时间线导出候选须连接原媒体审核节点，审核后才可作为正式视频素材。';
  if (target.definition_id === 'media_generate' && ['text', 'draft'].includes(edge.target_port)) {
    if (definition.edges.some(row => row.target_node_id === target.id && row.target_port === (edge.target_port === 'draft' ? 'text' : 'draft'))) return '媒体节点的文本与已审核草稿输入互斥，请先明确移除另一条输入连接。';
    if (edge.target_port === 'draft') {
      const parent = definition.edges.find(row => row.target_node_id === source.id && row.target_port === 'draft');
      if (definition.schema_version !== 3 || source.definition_id !== 'human_review' || edge.source_port !== 'reviewed_draft'
        || !parent || parent.source_port !== 'draft' || definition.nodes.find(row => row.id === parent.source_node_id)?.definition_id !== 'text_generate') return '先连接原文字模型的 draft 到人工审核，再将该审核节点的 reviewed_draft 连接到媒体 draft；未审核模型提案不能直接进入媒体。';
    }
  }
  if (definition.edges.some(row => row.source_node_id === source.id && row.source_port === edge.source_port && row.target_node_id === target.id && row.target_port === edge.target_port)) return '此连接已经存在。';
  if (!input.multiple && definition.edges.some(row => row.target_node_id === target.id && row.target_port === edge.target_port)) return '该输入端口只接受一个连接。';
  const seen = new Set<string>(), pending = [target.id];
  while (pending.length) {
    const id = pending.pop()!; if (id === source.id) return '此连接会形成循环，无法保存。';
    if (seen.has(id)) continue; seen.add(id);
    pending.push(...definition.edges.filter(row => row.source_node_id === id).map(row => row.target_node_id));
  }
  return undefined;
}

export function retainsSavedAssetBindings(previous: readonly StudioGraphNode[], next: readonly StudioGraphNode[]): boolean {
  return previous.filter(node => ['asset_reference', 'director_plan', 'storyboard_plan'].includes(node.definition_id)).every(node => {
    const candidate = next.find(row => row.id === node.id);
    if (node.definition_id !== 'asset_reference') return candidate?.definition_id === node.definition_id && JSON.stringify(candidate.parameters.document_snapshot) === JSON.stringify(node.parameters.document_snapshot);
    return candidate?.definition_id === 'asset_reference' && (['asset_id', 'version', 'digest', 'kind'] as const).every(key => candidate.parameters[key] === node.parameters[key]);
  });
}
