import type { StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphEdge, StudioGraphNode } from './studioGraphTypes';

export const graphId = (prefix = 'node') => `${prefix}_${crypto.randomUUID().replace(/-/g, '')}`;
export const blankGraph = (): StudioGraphDefinition => ({ schema_version: 1, title: '独立创作图', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } });

/** Local authoring feedback mirrors the typed contract; server validation stays authoritative. */
export function connectionIssue(definition: StudioGraphDefinition, catalog: readonly StudioGraphCatalogDefinition[], edge: StudioGraphEdge): string | undefined {
  const source = definition.nodes.find(node => node.id === edge.source_node_id), target = definition.nodes.find(node => node.id === edge.target_node_id);
  if (!source || !target) return '请选择当前图中的两个节点。';
  if (source.id === target.id) return '节点不能连接自身。';
  const output = catalog.find(row => row.id === source.definition_id)?.outputs.find(port => port.id === edge.source_port);
  const input = catalog.find(row => row.id === target.definition_id)?.inputs.find(port => port.id === edge.target_port);
  if (!output || !input) return '请选择真实的输出端口和输入端口。';
  if (output.type !== input.type) return `端口类型不匹配：${output.type} → ${input.type}。`;
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
  return previous.filter(node => node.definition_id === 'asset_reference').every(node => {
    const candidate = next.find(row => row.id === node.id);
    return candidate?.definition_id === 'asset_reference' && (['asset_id', 'version', 'digest', 'kind'] as const).every(key => candidate.parameters[key] === node.parameters[key]);
  });
}
