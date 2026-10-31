import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';
/** Advisory structural analysis only. Execution validation remains with the original owner. */
export function graphMissingInputs(graph: StudioGraphDefinition, definitions: readonly StudioGraphCatalogDefinition[]) {
  return graph.nodes.filter(node => node.enabled).flatMap(node => {
    const spec = definitions.find(value => value.id === node.definition_id && value.version === node.definition_version);
    if (!spec) throw new Error('节点目录不完整。');
    return spec.inputs.filter(port => port.required && !graph.edges.some(link => link.target_node_id === node.id && link.target_port === port.id && graph.nodes.some(parent => parent.id === link.source_node_id && parent.enabled))).map(port => `${node.id}.${port.id}`);
  });
}
export function graphReachableNodes(source: StudioGraphDefinition, roots: readonly string[]) {
  const seen = new Set<string>(), pending = [...roots];
  while (pending.length) { const id = pending.pop()!; if (seen.has(id)) continue; seen.add(id); pending.push(...source.edges.filter(edge => edge.source_node_id === id).map(edge => edge.target_node_id)); }
  return source.nodes.filter(node => seen.has(node.id)).map(node => node.id);
}
export function graphNodeStateImpact(source: StudioGraphDefinition, nodeId: string, enabled: boolean, definitions: readonly StudioGraphCatalogDefinition[]) {
  const node = source.nodes.find(value => value.id === nodeId);
  if (!node || node.enabled === enabled) throw new Error('节点状态已经变化。');
  const definition = structuredClone(source); definition.nodes.find(value => value.id === nodeId)!.enabled = enabled;
  const before = new Set(graphMissingInputs(source, definitions)), after = graphMissingInputs(definition, definitions), affected = graphReachableNodes(source, [nodeId]);
  return { nodeId, enabled, definition, affected, newMissing: after.filter(value => !before.has(value)), remainingMissing: after,
    unaffected: source.nodes.filter(value => !affected.includes(value.id)).map(value => value.id) };
}
