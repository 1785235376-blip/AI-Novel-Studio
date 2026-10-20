import type { StudioGraphDefinition, StudioGraphEdge } from './studioGraphTypes';
export type GraphDependencyDirection = 'upstream' | 'downstream';
/** Inspect authored edges only; never infer execution order or omit disabled nodes. */
export function inspectGraphDependencies(definition: StudioGraphDefinition, selected: readonly string[], direction: GraphDependencyDirection) {
  const nodes = new Map(definition.nodes.map(node => [node.id, node]));
  const roots = new Set(selected.filter(id => nodes.has(id)));
  const adjacency = new Map<string, { next: string; edge: StudioGraphEdge }[]>();
  for (const edge of definition.edges) {
    if (!nodes.has(edge.source_node_id) || !nodes.has(edge.target_node_id)) continue;
    const from = direction === 'upstream' ? edge.target_node_id : edge.source_node_id;
    const next = direction === 'upstream' ? edge.source_node_id : edge.target_node_id;
    const list = adjacency.get(from) || []; list.push({ next, edge }); adjacency.set(from, list);
  }
  const distances = new Map([...roots].map(id => [id, 0]));
  const queue = [...roots];
  for (let index = 0; index < queue.length; index++) {
    const from = queue[index];
    for (const { next } of adjacency.get(from) || []) if (!distances.has(next)) {
      distances.set(next, distances.get(from)! + 1); queue.push(next);
    }
  }
  const links = new Map<string, StudioGraphEdge[]>();
  for (const edge of definition.edges) {
    if (!distances.has(edge.source_node_id) || !distances.has(edge.target_node_id)) continue;
    const id = direction === 'upstream' ? edge.source_node_id : edge.target_node_id;
    const list = links.get(id) || []; list.push(edge); links.set(id, list);
  }
  return definition.nodes.filter(node => distances.has(node.id) && !roots.has(node.id))
    .map(node => ({ node, distance: distances.get(node.id)!, links: links.get(node.id) || [] }))
    .sort((a, b) => a.distance - b.distance);
}
