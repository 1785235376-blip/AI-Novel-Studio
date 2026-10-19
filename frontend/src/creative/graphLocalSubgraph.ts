import { checkedStudioGraphDraft } from './studioGraphClient';
import { graphId } from './graphDraft';
import { GRAPH_LOCAL_SUBGRAPH_CHILD_IDS, GRAPH_LOCAL_SUBGRAPH_CONTRACT } from './studioGraphTypes';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';

export type LocalSubgraphSource = { source: StudioGraphRecord; input: string; output: string; childNodes: number; totalNodes: number };
export const localSubgraphPinKey = (source: StudioGraphRecord) => JSON.stringify([source.project_id, source.scope,
  source.id, source.version, source.definition_digest, source.execution_digest]);

/** Advisory finite authoring check. Only the original server grants access/current-pin authority. */
export function inspectLocalSubgraphSource(source: StudioGraphRecord, catalog: StudioGraphCatalog): LocalSubgraphSource {
  if (catalog.capabilities.local_subgraph_contract !== GRAPH_LOCAL_SUBGRAPH_CONTRACT
    || catalog.capabilities.local_subgraph_depth !== 1 || catalog.capabilities.local_subgraph_child_nodes !== 16
    || catalog.capabilities.local_subgraph_total_nodes !== 24 || catalog.capabilities.local_subgraph_cache !== false) throw new Error('当前受限子调用目录不匹配，请重新读取。');
  const definition = checkedStudioGraphDraft(source.definition), nodes = definition.nodes;
  if (definition.schema_version !== 1 || !source.can_edit || source.reference_states.length || !Number.isSafeInteger(source.version)
    || source.version < 1 || !/^[a-f0-9]{64}$/.test(source.definition_digest) || !/^[a-f0-9]{64}$/.test(source.execution_digest)) throw new Error('必须选择当前可读取、可编辑的已保存 schema 1 子图。');
  if (!nodes.length || nodes.length > 16 || nodes.some(node => !node.enabled || !GRAPH_LOCAL_SUBGRAPH_CHILD_IDS.some(kind => kind === node.definition_id))) throw new Error('整个子图须为 1–16 个已启用的纯本地节点；不含审核、资产、模型、媒体或嵌套调用。');
  const inputs = nodes.filter(node => node.definition_id === 'text_reference' && !definition.edges.some(edge => edge.target_node_id === node.id));
  if (inputs.length !== 1) throw new Error('本首片需要唯一、未连接的 text_reference.text 输入接口。');
  const input = inputs[0].id;
  for (const node of nodes) {
    const descriptor = catalog.definitions.find(row => row.id === node.definition_id);
    if (!descriptor || descriptor.inputs.some(port => port.required && !(node.id === input && port.id === 'text')
      && !definition.edges.some(edge => edge.target_node_id === node.id && edge.target_port === port.id))) throw new Error('子图存在未满足的必需输入，不能生成父草稿。');
  }
  const outputs = nodes.filter(node => ['draft_prepare', 'manual_transform'].includes(node.definition_id)).filter(node => {
    const closure = new Set([node.id]), queue = [node.id];
    while (queue.length) {
      const target = queue.pop();
      for (const edge of definition.edges.filter(edge => edge.target_node_id === target)) {
        if (!closure.has(edge.source_node_id)) { closure.add(edge.source_node_id); queue.push(edge.source_node_id); }
      }
    }
    return closure.has(input) && closure.size === nodes.length;
  });
  if (outputs.length !== 1) throw new Error('本首片需要唯一 DRAFT 输出，且其上游闭包必须覆盖整个子图；不接受隐藏或游离节点。');
  if (nodes.length + 3 > 24) throw new Error('固定父链与子图合计不能超过 24 个节点。');
  return { source, input, output: outputs[0].id, childNodes: nodes.length, totalNodes: nodes.length + 3 };
}

export function buildLocalSubgraphParent(plan: LocalSubgraphSource, text: string): StudioGraphDefinition {
  if (!text.trim() || text.length > 8000 || plan.childNodes > 16 || plan.totalNodes > 24) throw new Error('请填写 1–8000 字符的父级作者文本，并重新核对容量。');
  const input = graphId('text'), call = graphId('call'), review = graphId('review'), source = plan.source;
  return checkedStudioGraphDraft({ schema_version: 6, title: `本地子调用 · ${source.definition.title}`.slice(0, 160),
    viewport: { x: 0, y: 0, zoom: 1 }, nodes: [
      { id: input, definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text } },
      { id: call, definition_id: 'local_subgraph', definition_version: 1, enabled: true, position: { x: 320, y: 0 }, parameters: {
        graph_id: source.id, expected_version: source.version, definition_digest: source.definition_digest, execution_digest: source.execution_digest,
        input_node_id: plan.input, input_port: 'text', output_node_id: plan.output, output_port: 'draft' } },
      { id: review, definition_id: 'human_review', definition_version: 1, enabled: true, position: { x: 640, y: 0 }, parameters: {} },
    ], edges: [
      { id: graphId('edge'), source_node_id: input, source_port: 'text', target_node_id: call, target_port: 'text' },
      { id: graphId('edge'), source_node_id: call, source_port: 'draft', target_node_id: review, target_port: 'draft' },
    ] });
}

/** First UI slice edits text/layout only; pins and topology are fixed until a new explicit draft. */
export function retainsLocalSubgraphTopology(previous: StudioGraphDefinition, next: StudioGraphDefinition): boolean {
  if (previous.schema_version !== 6) return true;
  const topology = (value: StudioGraphDefinition) => ({ schema_version: value.schema_version, edges: value.edges,
    nodes: value.nodes.map(node => ({ id: node.id, definition_id: node.definition_id, definition_version: node.definition_version,
      enabled: node.enabled, parameters: node.definition_id === 'text_input' ? { text: 'AUTHOR_EDITABLE' } : node.parameters })) });
  return JSON.stringify(topology(previous)) === JSON.stringify(topology(next));
}
