import { graphId } from './graphDraft';
import { GRAPH_POSITION_LIMIT } from './graphCanvasGeometry';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';

/** In-app, same-draft duplication only. No external clipboard or reference resolution. */
export function graphSelectionCopy(definition: StudioGraphDefinition, selected: readonly string[], catalog: StudioGraphCatalog) {
  const ids = new Set(selected), nodes = definition.nodes.filter(node => ids.has(node.id));
  if (!nodes.length || nodes.length !== ids.size) throw new Error('请选择当前图中的节点。');
  const edges = definition.edges.filter(edge => ids.has(edge.source_node_id) && ids.has(edge.target_node_id));
  const excludedEdges = definition.edges.filter(edge => ids.has(edge.source_node_id) !== ids.has(edge.target_node_id)).length;
  const limit = definition.schema_version >= 3 ? catalog.media_limits?.nodes || 24 : catalog.limits.nodes;
  if (definition.nodes.length + nodes.length > limit || definition.edges.length + edges.length > catalog.limits.edges) throw new Error('复制将超过原图节点或连接数量限制；未粘贴任何节点。');
  const generators = new Set(['media_generate', 'timeline_export', 'image_generate', 'image_upscale', 'video_generate']);
  if ([...definition.nodes, ...nodes].filter(node => generators.has(node.definition_id)).length > (catalog.media_limits?.generators || 4)) throw new Error('复制将超过原媒体生成节点限制；未粘贴任何节点。');
  if (nodes.some(node => !catalog.definitions.some(spec => spec.id === node.definition_id))) throw new Error('当前目录不支持所选节点。');
  const offset = (axis: 'x' | 'y') => {
    const values = nodes.map(node => node.position[axis]);
    if (values.some(value => !Number.isFinite(value) || Math.abs(value) > GRAPH_POSITION_LIMIT)) throw new Error('节点坐标超出原画布边界。');
    const lower = -GRAPH_POSITION_LIMIT - Math.min(...values), upper = GRAPH_POSITION_LIMIT - Math.max(...values);
    return upper >= 32 ? 32 : lower <= -32 ? -32 : Math.max(lower, Math.min(upper, 32));
  };
  const delta = { x: offset('x'), y: offset('y') };
  const occupied = new Set([...definition.nodes, ...definition.edges].map(row => row.id));
  const fresh = (prefix: string) => {
    const value = graphId(prefix);
    if (occupied.has(value)) throw new Error('新节点标识冲突，请重新预览。');
    occupied.add(value); return value;
  };
  const mapping = new Map(nodes.map(node => [node.id, fresh('node')]));
  const copied = nodes.map(node => ({ ...structuredClone(node), id: mapping.get(node.id)!, position: { x: node.position.x + delta.x, y: node.position.y + delta.y } }));
  const next = { ...structuredClone(definition), nodes: [...structuredClone(definition.nodes), ...copied], edges: [...structuredClone(definition.edges), ...edges.map(edge => ({ ...edge, id: fresh('edge'), source_node_id: mapping.get(edge.source_node_id)!, target_node_id: mapping.get(edge.target_node_id)! }))] };
  // Conservative JSON size includes whitespace overhead relative to canonical transport.
  if (new TextEncoder().encode(JSON.stringify(next)).length > catalog.limits.definition_bytes) throw new Error('复制将超过原图定义大小限制；未粘贴任何节点。');
  return { definition: next, selected: copied.map(node => node.id), nodeCount: copied.length, edgeCount: edges.length, excludedEdges, delta };
}
export type GraphSelectionCopy = ReturnType<typeof graphSelectionCopy>;
