import { graphWorldToScreen, graphScreenToWorld } from './graphCanvasGeometry';
import type { CanvasDefinition, CanvasCard } from './studioCanvasViewClient';
export const MEDIA_CARD_WIDTH = 240, MEDIA_CARD_HEIGHT = 120, MEDIA_RENDER_LIMIT = 128;
/** Fixed domain geometry. Culling bounds rendered DOM, not saved content. */
export function visibleMediaCards(definition: CanvasDefinition, width: number, height: number, query = ''): { cards: CanvasCard[]; matched: number; clipped: boolean } {
  const needle = query.trim().toLocaleLowerCase(), matched = definition.cards.filter(card => !needle || card.id.toLocaleLowerCase().includes(needle) || card.asset?.asset_id.toLocaleLowerCase().includes(needle));
  const visible = matched.filter(card => { const point = graphWorldToScreen(card.position, definition.viewport);
    return point.x + MEDIA_CARD_WIDTH * definition.viewport.zoom >= 0 && point.y + MEDIA_CARD_HEIGHT * definition.viewport.zoom >= 0 && point.x <= width && point.y <= height; });
  return { cards: visible.slice(0, MEDIA_RENDER_LIMIT), matched: matched.length, clipped: visible.length > MEDIA_RENDER_LIMIT };
}
export function mediaViewportCenter(definition: CanvasDefinition, width: number, height: number) { return graphScreenToWorld({ x: width / 2, y: height / 2 }, definition.viewport); }
