import { connectionIssue, graphCatalogForSchema } from './graphDraft';
import { graphMissingInputs, graphReachableNodes } from './graphNodeStateImpact';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition } from './studioGraphTypes';

export type GraphConnectionCatalog = { definitions: readonly StudioGraphCatalogDefinition[];
  limits: { edges: number; definition_bytes: number } };
/** Replace exactly one occupied input, using the original typed-edge authority. */
export function graphConnectionReplacement(source: StudioGraphDefinition, catalog: GraphConnectionCatalog,
  edgeId: string, output: { nodeId: string; portId: string }) {
  const index = source.edges.findIndex(edge => edge.id === edgeId), previous = source.edges[index];
  if (!previous || source.edges.filter(edge => edge.id === edgeId).length !== 1) throw new Error('原连接已经变化，请重新选择。');
  const definitions = graphCatalogForSchema(catalog.definitions, source.schema_version);
  const target = source.nodes.find(node => node.id === previous.target_node_id);
  const input = definitions.find(row => row.id === target?.definition_id)?.inputs.find(port => port.id === previous.target_port);
  if (!input || input.multiple !== false || source.edges.filter(edge => edge.target_node_id === previous.target_node_id && edge.target_port === previous.target_port).length !== 1) {
    throw new Error('仅支持恰有一条原连接的单输入端口。');
  }
  if (previous.source_node_id === output.nodeId && previous.source_port === output.portId) throw new Error('新输出与原来源相同，无需重接。');
  const next = { ...previous, source_node_id: output.nodeId, source_port: output.portId };
  const remaining = { ...source, edges: source.edges.filter((_, position) => position !== index) };
  const issue = connectionIssue(remaining, catalog.definitions, next);
  if (issue) throw new Error(issue);
  const definition = structuredClone(source); definition.edges[index] = next;
  if (definition.edges.length > catalog.limits.edges || new TextEncoder().encode(JSON.stringify(definition)).length > catalog.limits.definition_bytes) {
    throw new Error('重接后的图超出原容量上限，未修改草稿。');
  }
  const before = new Set(graphMissingInputs(source, definitions));
  return { previous: { ...previous }, next, type: input.type, definition,
    affected: graphReachableNodes(source, [previous.target_node_id]),
    newMissing: graphMissingInputs(definition, definitions).filter(value => !before.has(value)) };
}
