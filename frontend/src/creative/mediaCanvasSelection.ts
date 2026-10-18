import { alignGraphNodes, GRAPH_POSITION_LIMIT, type GraphAlignment } from './graphCanvasGeometry';
import type { StudioGraphDefinition } from './studioGraphTypes';
import type { CanvasDefinition } from './studioCanvasViewClient';
/** Temporary geometry projection only. Never passed to Graph validation, storage or execution. */
export function alignCanvasCards(definition: CanvasDefinition, ids: readonly string[], mode: GraphAlignment): CanvasDefinition {
  const projection: StudioGraphDefinition = { schema_version: 1, title: definition.title, viewport: definition.viewport, edges: [],
    nodes: definition.cards.map(card => ({ id: card.id, position: card.position, definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: '' } })) };
  const aligned = alignGraphNodes(projection, ids, mode); if (aligned === projection) return definition;
  const positions = new Map(aligned.nodes.map(node => [node.id, node.position]));
  return { ...definition, cards: definition.cards.map(card => ({ ...card, position: positions.get(card.id)! })) };
}
/** Translate one bounded cohort; clamping a single delta preserves relative offsets. */
export function translateCanvasCards(definition: CanvasDefinition, ids: readonly string[], dx: number, dy: number): CanvasDefinition {
  const selected = new Set(ids), cards = definition.cards.filter(c => selected.has(c.id));
  if (!cards.length || cards.length !== selected.size || !Number.isFinite(dx) || !Number.isFinite(dy)) return definition;
  const x = Math.max(Math.max(...cards.map(c => -GRAPH_POSITION_LIMIT - c.position.x)), Math.min(Math.min(...cards.map(c => GRAPH_POSITION_LIMIT - c.position.x)), dx));
  const y = Math.max(Math.max(...cards.map(c => -GRAPH_POSITION_LIMIT - c.position.y)), Math.min(Math.min(...cards.map(c => GRAPH_POSITION_LIMIT - c.position.y)), dy));
  if (!x && !y) return definition;
  return { ...definition, cards: definition.cards.map(c => selected.has(c.id) ? { ...c, position: { x: c.position.x + x, y: c.position.y + y } } : c) };
}

/** Snap the grabbed anchor in world coordinates, keeping cohort offsets and existing bounds. */
export function dragCanvasCards(definition: CanvasDefinition, ids: readonly string[], anchor: string, dx: number, dy: number): CanvasDefinition {
  const step = definition.view_options?.snap_step, card = definition.cards.find(c => c.id === anchor);
  if (!card || !ids.includes(anchor)) return definition;
  if (!step) return translateCanvasCards(definition, ids, dx, dy);
  return translateCanvasCards(definition, ids,
    Math.round((card.position.x + dx) / step) * step - card.position.x,
    Math.round((card.position.y + dy) / step) * step - card.position.y);
}
