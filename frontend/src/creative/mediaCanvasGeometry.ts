import { canvasHiddenCards } from './mediaCanvasGroups';
import { graphWorldToScreen, graphScreenToWorld } from './graphCanvasGeometry';
import type { CanvasDefinition, CanvasCard } from './studioCanvasViewClient';
export const MEDIA_CARD_WIDTH = 240, MEDIA_CARD_HEIGHT = 120, MEDIA_RENDER_LIMIT = 128;
/** Fixed domain geometry. Culling bounds rendered DOM, not saved content. */
export function visibleMediaCards(definition: CanvasDefinition, width: number, height: number, query = ''): { cards: CanvasCard[]; matched: number; clipped: boolean } {
  const needle = query.trim().toLocaleLowerCase(), matched = definition.cards.filter(card => !needle || card.id.toLocaleLowerCase().includes(needle) || card.asset?.asset_id.toLocaleLowerCase().includes(needle));
  const hidden = canvasHiddenCards(definition);
  const visible = matched.filter(card => !hidden.has(card.id)).filter(card => { const point = graphWorldToScreen(card.position, definition.viewport);
    return point.x + MEDIA_CARD_WIDTH * definition.viewport.zoom >= 0 && point.y + MEDIA_CARD_HEIGHT * definition.viewport.zoom >= 0 && point.x <= width && point.y <= height; });
  return { cards: visible.slice(0, MEDIA_RENDER_LIMIT), matched: matched.length, clipped: visible.length > MEDIA_RENDER_LIMIT };
}
export function mediaViewportCenter(definition: CanvasDefinition, width: number, height: number) { return graphScreenToWorld({ x: width / 2, y: height / 2 }, definition.viewport); }

/** Complete world bounds, including the camera; no sampled omission. */
export function mediaOverview(definition: CanvasDefinition, width: number, height: number) {
  const topLeft = graphScreenToWorld({ x: 0, y: 0 }, definition.viewport), bottomRight = graphScreenToWorld({ x: width, y: height }, definition.viewport);
  let left = topLeft.x, top = topLeft.y, right = bottomRight.x, bottom = bottomRight.y;
  for (const card of definition.cards) { left = Math.min(left, card.position.x); top = Math.min(top, card.position.y); right = Math.max(right, card.position.x + MEDIA_CARD_WIDTH); bottom = Math.max(bottom, card.position.y + MEDIA_CARD_HEIGHT); }
  const margin = 24; left -= margin; top -= margin; right += margin; bottom += margin;
  const scale = Math.min(200 / Math.max(1, right - left), 120 / Math.max(1, bottom - top));
  const offsetX = (200 - (right - left) * scale) / 2, offsetY = (120 - (bottom - top) * scale) / 2;
  return { left, top, right, bottom, scale, offsetX, offsetY, camera: { x: topLeft.x, y: topLeft.y, width: bottomRight.x - topLeft.x, height: bottomRight.y - topLeft.y } };
}
