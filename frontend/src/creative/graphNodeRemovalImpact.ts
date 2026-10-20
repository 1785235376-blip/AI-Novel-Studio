import { removeGraphNodes } from './graphCanvasGeometry';
import { graphMissingInputs, graphReachableNodes } from './graphNodeStateImpact';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';

/** Advisory structure only. Removal, group cleanup and execution stay with their original owners. */
export function graphNodeRemovalImpact(source: StudioGraphDefinition, nodeIds: readonly string[],
  protectedNodeIds: readonly string[], definitions: readonly StudioGraphCatalogDefinition[]) {
  const requested = [...new Set(nodeIds)];
  if (!requested.length || requested.some(id => !source.nodes.some(node => node.id === id))) {
    throw new Error('所选节点已经变化。');
  }
  if (source.nodes.some(node => !definitions.some(spec => spec.id === node.definition_id && spec.version === node.definition_version))) {
    throw new Error('节点目录不完整。');
  }
  const protectedIds = requested.filter(id => protectedNodeIds.includes(id));
  const removed = requested.filter(id => !protectedNodeIds.includes(id));
  if (!removed.length) throw new Error('已保存的来源引用不能移除。');
  const definition = removeGraphNodes(structuredClone(source), removed, protectedNodeIds);
  const removedEdges = source.edges.filter(edge => removed.includes(edge.source_node_id) || removed.includes(edge.target_node_id));
  const affected = graphReachableNodes(source, removed).filter(id => !removed.includes(id));
  const before = new Set(graphMissingInputs(source, definitions));
  const remainingMissing = graphMissingInputs(definition, definitions);
  const groups = source.presentation?.groups ?? [], nextGroups = definition.presentation?.groups ?? [];
  return {
    definition, removed, protectedIds, removedEdges, affected, remainingMissing,
    newMissing: remainingMissing.filter(input => !before.has(input)),
    unaffected: definition.nodes.filter(node => !affected.includes(node.id)).map(node => node.id),
    removedGroups: groups.filter(group => !nextGroups.some(next => next.id === group.id)).map(group => group.id),
    changedGroups: nextGroups.filter(group => JSON.stringify(group) !== JSON.stringify(groups.find(old => old.id === group.id))).map(group => group.id),
  };
}
