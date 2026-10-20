import type { StudioGraphDefinition, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

/** Structural descendants only: shared nodes can belong to more than one Director branch. */
export function directorRunBranch(definition: StudioGraphDefinition, directorId: string) {
  if (!definition.nodes.some(node => node.id === directorId && node.definition_id === 'director_plan')) return [];
  const ids = new Set([directorId]), queue = [directorId];
  for (let index = 0; index < queue.length; index++) for (const edge of definition.edges) {
    if (edge.source_node_id === queue[index] && !ids.has(edge.target_node_id) && definition.nodes.some(node => node.id === edge.target_node_id)) {
      ids.add(edge.target_node_id); queue.push(edge.target_node_id);
    }
  }
  return definition.nodes.filter(node => ids.has(node.id));
}
const scopeKey = (scope: StudioGraphRecord['scope']) => JSON.stringify(Object.entries(scope).sort(([a], [b]) => a.localeCompare(b)));
export function directorRunMatches(run: StudioGraphRun, graph: StudioGraphRecord) {
  return run.project_id === graph.project_id && scopeKey(run.scope) === scopeKey(graph.scope)
    && run.graph_id === graph.id && run.graph_version === graph.version;
}
export type DirectorRunChoice = Pick<StudioGraphRun, 'id' | 'version' | 'status'>;
export function directorRunChoice(run: StudioGraphRun): DirectorRunChoice { return { id: run.id, version: run.version, status: run.status }; }
/** Keep status metadata only; never retain node outputs, model receipts, assets or review payloads. */
export function projectDirectorRun(run: StudioGraphRun, graph: StudioGraphRecord, directorId: string) {
  if (!directorRunMatches(run, graph)) throw new Error('运行不属于当前已保存图版本，未显示分支状态。');
  const branch = directorRunBranch(graph.definition, directorId);
  if (!branch.length) throw new Error('当前图没有这个导演节点。');
  return { ...directorRunChoice(run), stale: run.stale, updatedAt: run.updated_at,
    currentNode: branch.some(node => node.id === run.current_node_id) ? run.current_node_id : undefined,
    rows: branch.map(node => ({ id: node.id, kind: node.definition_id, enabled: node.enabled, status: run.node_states[node.id]?.status })),
  };
}
