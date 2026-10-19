import type { ComicDocument, ComicRect } from './comicLayoutsClient';
export type ComicGeometryTarget = { panelId: string; bubbleId?: string };
export type ComicGeometryMode = 'move' | 'resize';
const valid = (r: ComicRect) => [r.x, r.y, r.width, r.height].every(Number.isSafeInteger) && r.x >= 0 && r.y >= 0 && r.width >= 16 && r.width <= 1600 && r.height >= 16 && r.height <= 12000;
const inside = (r: ComicRect, b: ComicRect) => valid(r) && r.x >= b.x && r.y >= b.y && r.x + r.width <= b.x + b.width && r.y + r.height <= b.y + b.height;
const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, Math.round(n)));
/** Canonical page-pixel geometry only. Never scales text or changes artwork pins. */
export function transformComicGeometry(document: ComicDocument, target: ComicGeometryTarget, mode: ComicGeometryMode, dx: number, dy: number): ComicDocument {
  if (![dx, dy].every(Number.isFinite) || ![document.width, document.height, document.safe_area].every(Number.isSafeInteger)
    || document.width < 320 || document.width > 1600 || document.height < 320 || document.height > 12000 || document.safe_area < 0 || document.safe_area > 128) return document;
  const panel = document.panels.find(p => p.id === target.panelId);
  if (!panel) return document;
  const rect = target.bubbleId ? panel.bubbles.find(b => b.id === target.bubbleId) : panel;
  const bubbleBounds = { x: panel.x + 8, y: panel.y + 8, width: panel.width - 16, height: panel.height - 16 };
  const bounds = target.bubbleId ? bubbleBounds : { x: document.safe_area, y: document.safe_area, width: document.width - 2 * document.safe_area, height: document.height - 2 * document.safe_area };
  // Invalid numeric drafts stay available for numeric correction, never silently repaired.
  if (!rect || !valid(bounds) || !inside(rect, bounds) || (!target.bubbleId && panel.bubbles.some(b => !inside(b, bubbleBounds)))) return document;
  let patch: ComicRect;
  if (mode === 'move') patch = { ...rect, x: clamp(rect.x + dx, bounds.x, bounds.x + bounds.width - rect.width), y: clamp(rect.y + dy, bounds.y, bounds.y + bounds.height - rect.height) };
  else {
    const children = target.bubbleId ? [] : panel.bubbles;
    patch = { ...rect, width: clamp(rect.width + dx, Math.max(16, ...children.map(b => b.x + b.width + 8 - rect.x)), bounds.x + bounds.width - rect.x), height: clamp(rect.height + dy, Math.max(16, ...children.map(b => b.y + b.height + 8 - rect.y)), bounds.y + bounds.height - rect.y) };
  }
  if (['x', 'y', 'width', 'height'].every(key => rect[key as keyof ComicRect] === patch[key as keyof ComicRect])) return document;
  return { ...document, panels: document.panels.map(p => p !== panel ? p : target.bubbleId ? { ...p, bubbles: p.bubbles.map(b => b.id === target.bubbleId ? { ...b, ...patch } : b) } : { ...p, ...patch, bubbles: p.bubbles.map(b => ({ ...b, x: b.x + patch.x - p.x, y: b.y + patch.y - p.y })) }) };
}

/** One shared translation keeps the selected panels' spacing and child geometry. */
export function translateComicPanels(document: ComicDocument, ids: readonly string[], dx: number, dy: number): ComicDocument {
  if (!ids.length || ids.length > 24 || new Set(ids).size !== ids.length || ![dx, dy].every(Number.isFinite)
    || ![document.width, document.height, document.safe_area].every(Number.isSafeInteger)
    || document.width < 320 || document.width > 1600 || document.height < 320 || document.height > 12000 || document.safe_area < 0 || document.safe_area > 128) return document;
  const panels = document.panels.filter(panel => ids.includes(panel.id));
  if (panels.length !== ids.length || new Set(panels.map(panel => panel.id)).size !== ids.length) return document;
  const bounds = { x: document.safe_area, y: document.safe_area, width: document.width - 2 * document.safe_area, height: document.height - 2 * document.safe_area };
  if (!valid(bounds) || panels.some(panel => !inside(panel, bounds) || panel.bubbles.some(bubble => !inside(bubble, { x: panel.x + 8, y: panel.y + 8, width: panel.width - 16, height: panel.height - 16 })))) return document;
  const x = clamp(dx, Math.max(...panels.map(panel => bounds.x - panel.x)), Math.min(...panels.map(panel => bounds.x + bounds.width - panel.x - panel.width)));
  const y = clamp(dy, Math.max(...panels.map(panel => bounds.y - panel.y)), Math.min(...panels.map(panel => bounds.y + bounds.height - panel.y - panel.height)));
  if (!x && !y) return document;
  return { ...document, panels: document.panels.map(panel => panels.includes(panel) ? { ...panel, x: panel.x + x, y: panel.y + y,
    bubbles: panel.bubbles.map(bubble => ({ ...bubble, x: bubble.x + x, y: bubble.y + y })) } : panel) };
}
