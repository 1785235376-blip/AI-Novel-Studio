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

/** Snap the grabbed anchor in world units; one bounded translation preserves every selected offset.
 * At the coordinate boundary, preserving the group takes precedence over exact grid alignment. */
export function snapGraphNodes(definition: StudioGraphDefinition, ids: readonly string[], anchorId: string,
  screenDelta: StudioGraphPosition, step: number): StudioGraphDefinition {
  const selected = new Set(ids), nodes = definition.nodes.filter(node => selected.has(node.id));
  const anchor = nodes.find(node => node.id === anchorId);
  if (!anchor || nodes.length !== selected.size || ![8, 16, 24, 32].includes(step)
    || !Number.isFinite(screenDelta.x) || !Number.isFinite(screenDelta.y)
    || nodes.some(node => !Number.isFinite(node.position.x) || !Number.isFinite(node.position.y)
      || Math.abs(node.position.x) > GRAPH_POSITION_LIMIT || Math.abs(node.position.y) > GRAPH_POSITION_LIMIT)
    || (!screenDelta.x && !screenDelta.y)) return definition;
  const zoom = clampGraphZoom(definition.viewport.zoom);
  const delta = { x: 0, y: 0 };
  for (const axis of ['x', 'y'] as const) {
    const desired = Math.round((anchor.position[axis] + screenDelta[axis] / zoom) / step) * step - anchor.position[axis];
    const minimum = Math.max(...nodes.map(node => -GRAPH_POSITION_LIMIT - node.position[axis]));
    const maximum = Math.min(...nodes.map(node => GRAPH_POSITION_LIMIT - node.position[axis]));
    delta[axis] = Math.max(minimum, Math.min(maximum, desired));
  }
  if (!delta.x && !delta.y) return definition;
  return { ...definition, nodes: definition.nodes.map(node => selected.has(node.id)
    ? { ...node, position: { x: node.position.x + delta.x, y: node.position.y + delta.y } } : node) };
}

export function graphPortPosition(node: Pick<StudioGraphNode, 'position'>, descriptor: GraphCanvasNodeDefinition | undefined, direction: 'input' | 'output', portId: string): StudioGraphPosition | null {
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
  const next = { ...definition, nodes: definition.nodes.filter(node => !removed.has(node.id)), edges: definition.edges.filter(edge => !removed.has(edge.source_node_id) && !removed.has(edge.target_node_id)) };
  if (definition.presentation?.groups) {
    next.presentation = { ...definition.presentation };
    const groups = definition.presentation.groups.map(group => ({ ...group, node_ids: group.node_ids.filter(id => !removed.has(id)) })).filter(group => group.node_ids.length);
    if (groups.length) next.presentation.groups = groups;
    else delete next.presentation.groups;
    if (!Object.keys(next.presentation).length) delete next.presentation;
  }
  return next;
}

export function isGraphEditableTarget(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]'));
}

export type GraphAlignment = 'left' | 'center' | 'top' | 'distribute';

/** Selected presentation only. Reject invalid inputs rather than silently repairing stored geometry. */
export function alignGraphNodes(definition: StudioGraphDefinition, ids: readonly string[], mode: GraphAlignment): StudioGraphDefinition {
  const selected = new Set(ids), nodes = definition.nodes.filter(node => selected.has(node.id));
  if (nodes.length !== selected.size || nodes.length < (mode === 'distribute' ? 3 : 2)
    || nodes.some(node => !Number.isFinite(node.position.x) || !Number.isFinite(node.position.y)
      || Math.abs(node.position.x) > GRAPH_POSITION_LIMIT || Math.abs(node.position.y) > GRAPH_POSITION_LIMIT)) return definition;
  const xs = nodes.map(node => node.position.x), ys = nodes.map(node => node.position.y);
  const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys);
  // All rendered cards have the same width, so equal left-coordinate spacing also gives equal gaps.
  const ordered = [...nodes].sort((a, b) => a.position.x - b.position.x || a.id.localeCompare(b.id));
  const distributed = new Map(ordered.map((node, index) => [node.id, left + (right - left) * index / (nodes.length - 1)]));
  let changed = false;
  const next = definition.nodes.map(node => {
    if (!selected.has(node.id)) return node;
    const position = mode === 'top' ? { ...node.position, y: top } : { ...node.position,
      x: mode === 'left' ? left : mode === 'center' ? (left + right) / 2 : distributed.get(node.id)! };
    if (position.x === node.position.x && position.y === node.position.y) return node;
    changed = true;
    return { ...node, position };
  });
  return changed ? { ...definition, nodes: next } : definition;
}
