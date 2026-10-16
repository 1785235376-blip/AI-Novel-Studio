import type { StudioGraphDefinition, StudioGraphNode, StudioGraphPosition, StudioGraphViewport } from './studioGraphTypes';

/** Domain geometry only; canvas chrome uses the shared design-system tokens. */
export const GRAPH_NODE_WIDTH = 320;
export const GRAPH_NODE_HEADER_HEIGHT = 64;
export const GRAPH_PORT_ROW_HEIGHT = 48;
export const GRAPH_MIN_ZOOM = 0.35;
export const GRAPH_MAX_ZOOM = 2.5;
export const GRAPH_POSITION_LIMIT = 100_000;

export type GraphCanvasPort = { id: string; type: string; label?: string; required?: boolean };
export type GraphCanvasNodeDefinition = {
  id: string;
  label?: string;
  inputs: readonly GraphCanvasPort[];
  outputs: readonly GraphCanvasPort[];
};
export type GraphCanvasRect = StudioGraphPosition & { width: number; height: number };

export function clampGraphZoom(value: number): number {
  return Number.isFinite(value) ? Math.min(GRAPH_MAX_ZOOM, Math.max(GRAPH_MIN_ZOOM, value)) : 1;
}

export function clampGraphPosition(value: number): number {
  return Number.isFinite(value) ? Math.min(GRAPH_POSITION_LIMIT, Math.max(-GRAPH_POSITION_LIMIT, value)) : 0;
}

export function graphScreenToWorld(point: StudioGraphPosition, viewport: StudioGraphViewport): StudioGraphPosition {
  const zoom = clampGraphZoom(viewport.zoom);
  return { x: (point.x - viewport.x) / zoom, y: (point.y - viewport.y) / zoom };
}

export function graphWorldToScreen(point: StudioGraphPosition, viewport: StudioGraphViewport): StudioGraphPosition {
  const zoom = clampGraphZoom(viewport.zoom);
  return { x: point.x * zoom + viewport.x, y: point.y * zoom + viewport.y };
}

/** Zoom around a viewport-local pointer, preserving the world point under it. */
export function zoomGraphAt(viewport: StudioGraphViewport, anchor: StudioGraphPosition, value: number): StudioGraphViewport {
  const point = graphScreenToWorld(anchor, viewport), zoom = clampGraphZoom(value);
  return { x: clampGraphPosition(anchor.x - point.x * zoom), y: clampGraphPosition(anchor.y - point.y * zoom), zoom };
}

export function graphNodeHeight(descriptor?: GraphCanvasNodeDefinition): number {
  return GRAPH_NODE_HEADER_HEIGHT + GRAPH_PORT_ROW_HEIGHT * Math.max(1, descriptor?.inputs.length ?? 0, descriptor?.outputs.length ?? 0);
}

export function graphSelectionRect(start: StudioGraphPosition, end: StudioGraphPosition): GraphCanvasRect {
  return { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) };
}

export function graphNodesInScreenRect(
  nodes: readonly StudioGraphNode[], rect: GraphCanvasRect, viewport: StudioGraphViewport,
  definitions: readonly GraphCanvasNodeDefinition[],
): string[] {
  const origin = graphScreenToWorld(rect, viewport), zoom = clampGraphZoom(viewport.zoom);
  const right = origin.x + rect.width / zoom, bottom = origin.y + rect.height / zoom;
  return nodes.filter(node => {
    const height = graphNodeHeight(definitions.find(item => item.id === node.definition_id));
    return node.position.x <= right && node.position.x + GRAPH_NODE_WIDTH >= origin.x
      && node.position.y <= bottom && node.position.y + height >= origin.y;
  }).map(node => node.id);
}

export function moveGraphNodes(definition: StudioGraphDefinition, ids: readonly string[], screenDelta: StudioGraphPosition): StudioGraphDefinition {
  const selected = new Set(ids), zoom = clampGraphZoom(definition.viewport.zoom);
  return { ...definition, nodes: definition.nodes.map(node => selected.has(node.id)
    ? { ...node, position: { x: clampGraphPosition(node.position.x + screenDelta.x / zoom), y: clampGraphPosition(node.position.y + screenDelta.y / zoom) } }
    : node) };
}

export function graphPortPosition(node: StudioGraphNode, descriptor: GraphCanvasNodeDefinition | undefined, direction: 'input' | 'output', portId: string): StudioGraphPosition | null {
  const ports = direction === 'input' ? descriptor?.inputs : descriptor?.outputs;
  const index = ports?.findIndex(port => port.id === portId) ?? -1;
  if (index < 0) return null;
  return { x: node.position.x + (direction === 'output' ? GRAPH_NODE_WIDTH : 0), y: node.position.y + GRAPH_NODE_HEADER_HEIGHT + GRAPH_PORT_ROW_HEIGHT * (index + 0.5) };
}

export function graphEdgePath(source: StudioGraphPosition, target: StudioGraphPosition): string {
  const bend = Math.max(GRAPH_PORT_ROW_HEIGHT, Math.abs(target.x - source.x) / 2);
  return `M ${source.x} ${source.y} C ${source.x + bend} ${source.y}, ${target.x - bend} ${target.y}, ${target.x} ${target.y}`;
}

export function removeGraphNodes(definition: StudioGraphDefinition, ids: readonly string[], protectedIds: readonly string[] = []): StudioGraphDefinition {
  const protectedSet = new Set(protectedIds), removed = new Set(ids.filter(id => !protectedSet.has(id)));
  return { ...definition, nodes: definition.nodes.filter(node => !removed.has(node.id)), edges: definition.edges.filter(edge => !removed.has(edge.source_node_id) && !removed.has(edge.target_node_id)) };
}

export function isGraphEditableTarget(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]'));
}
