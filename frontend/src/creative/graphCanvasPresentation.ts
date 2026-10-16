import type { StudioGraphEdge, StudioGraphNode, StudioGraphViewport } from './studioGraphTypes';
import { GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT, graphNodeHeight, graphPortPosition, graphScreenToWorld, clampGraphZoom } from './graphCanvasGeometry';
import type { GraphCanvasNodeDefinition, GraphCanvasRect } from './graphCanvasGeometry';

/** Disposable display projection, never a persistable/executable graph or a second owner. */
export type GraphDisplayNode = Pick<StudioGraphNode, 'id' | 'definition_id' | 'position'>;
export type GraphDisplayEdge = { id: string; start: { x: number; y: number }; end: { x: number; y: number }; bounds: GraphCanvasRect };
export const GRAPH_VIEW_OVERSCAN = 160; // Screen pixels, independent of world zoom.
const intersects = (a: GraphCanvasRect, b: GraphCanvasRect) => a.x <= b.x + b.width && a.x + a.width >= b.x
  && a.y <= b.y + b.height && a.y + a.height >= b.y;

export function createGraphDisplayIndex(nodes: readonly GraphDisplayNode[], edges: readonly StudioGraphEdge[], definitions: readonly GraphCanvasNodeDefinition[]) {
  const descriptors = new Map(definitions.map(item => [item.id, item]));
  const byId = new Map(nodes.map(node => [node.id, node]));
  const cards = nodes.map(node => ({ id: node.id, bounds: { ...node.position, width: GRAPH_NODE_WIDTH, height: graphNodeHeight(descriptors.get(node.definition_id)) } }));
  const connections: GraphDisplayEdge[] = [];
  for (const edge of edges) {
    const source = byId.get(edge.source_node_id), target = byId.get(edge.target_node_id);
    if (!source || !target) continue;
    const start = graphPortPosition(source, descriptors.get(source.definition_id), 'output', edge.source_port);
    const end = graphPortPosition(target, descriptors.get(target.definition_id), 'input', edge.target_port);
    if (!start || !end) continue;
    const bend = Math.max(GRAPH_PORT_ROW_HEIGHT, Math.abs(end.x - start.x) / 2);
    // A cubic stays in its control-point convex hull. Conservative bounds retain
    // crossing/reversed curves even when neither endpoint/card is on screen.
    const left = Math.min(start.x, end.x, start.x + bend, end.x - bend);
    const right = Math.max(start.x, end.x, start.x + bend, end.x - bend);
    connections.push({ id: edge.id, start, end, bounds: { x: left, y: Math.min(start.y, end.y), width: right - left, height: Math.abs(end.y - start.y) } });
  }
  return { cards, connections, descriptors };
}
export type GraphDisplayIndex = ReturnType<typeof createGraphDisplayIndex>;

export function projectGraphDisplay(index: GraphDisplayIndex, viewport: StudioGraphViewport,
  size: { width: number; height: number } | null, retainedIds: readonly string[] = [], overscan = GRAPH_VIEW_OVERSCAN) {
  // Unknown/hidden layout must not accidentally hide the whole graph (SSR, first
  // layout, unsupported ResizeObserver). Recover automatically on next measurement.
  const measured = size && Number.isFinite(size.width) && Number.isFinite(size.height) && size.width > 0 && size.height > 0;
  const margin = Math.max(0, overscan), zoom = clampGraphZoom(viewport.zoom);
  const world = measured ? { ...graphScreenToWorld({ x: -margin, y: -margin }, viewport), width: (size.width + margin * 2) / zoom, height: (size.height + margin * 2) / zoom } : null;
  const nodeIds = new Set(retainedIds);
  for (const card of index.cards) if (!world || intersects(card.bounds, world)) nodeIds.add(card.id);
  return { nodeIds, edges: index.connections.filter(edge => !world || intersects(edge.bounds, world)) };
}
