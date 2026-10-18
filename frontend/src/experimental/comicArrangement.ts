import { comicLayersError } from './comicLayers';
import type { ComicDocument, ComicRect } from './comicLayoutsClient';

export type ComicArrangement = { document?: ComicDocument; error?: string; changed: boolean };
const integer = (value: number, min: number, max: number) => Number.isInteger(value) && value >= min && value <= max;
const rect = (value: ComicRect) => !!value && typeof value === 'object' && integer(value.x, 0, 12000) && integer(value.y, 0, 12000) && integer(value.width, 16, 1600) && integer(value.height, 16, 12000);
const inside = (inner: ComicRect, outer: ComicRect, padding: number) => inner.x >= outer.x + padding && inner.y >= outer.y + padding && inner.x + inner.width <= outer.x + outer.width - padding && inner.y + inner.height <= outer.y + outer.height - padding;
// Manual geometry only. Original save binds approved asset snapshots; original
// raster preflight remains authoritative for text metrics, pixels and export.
export function arrangeComicVertically(document: ComicDocument): ComicArrangement {
  const fail = (error: string): ComicArrangement => ({ error, changed: false });
  const validId = (value: unknown) => typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value);
  if (!document || typeof document !== 'object' || !Array.isArray(document.panels) || document.panels.some(p => !p || typeof p !== 'object' || !validId(p.id) || !Array.isArray(p.bubbles) || p.bubbles.length > 12 || p.bubbles.some(b => !b || typeof b !== 'object' || !validId(b.id)))) return fail('格框或气泡结构与标识无效，请重新打开有效布局。');
  const layerError = comicLayersError(document); if (layerError) return fail(layerError);
  const bubbles = document.panels.flatMap(p => p.bubbles);
  if (bubbles.length > 80 || new Set(bubbles.map(b => b.id)).size !== bubbles.length) return fail('气泡标识不能重复，且总数不能超过 80。');
  if (!integer(document.width, 320, 1600) || !integer(document.height, 320, 12000) || document.width * document.height > 16000000 || !integer(document.safe_area, 0, 128)) return fail('请先修正页面尺寸与安全区。');
  const panels = [...document.panels].sort((a, b) => a.order - b.order);
  if (!panels.length || panels.length > 24 || new Set(panels.map(p => p.id)).size !== panels.length || panels.some((p, i) => p.order !== i + 1)) return fail('阅读顺序必须从 1 连续编号，格框标识不能重复。');
  if (panels.some(p => !rect(p) || p.bubbles.some(b => !rect(b) || !inside(b, p, 8)))) return fail('请先修正格框尺寸和气泡的 8 px 内边界；排列不会缩放或裁切文字。');
  let y = document.safe_area;
  const positions = new Map(panels.map(panel => {
    const next = { ...panel, x: document.safe_area, y, bubbles: panel.bubbles.map(b => ({ ...b, x: b.x + document.safe_area - panel.x, y: b.y + y - panel.y })) };
    y += panel.height + 16;
    return [panel.id, next];
  }));
  const next = { ...document, panels: document.panels.map(p => positions.get(p.id)!) };
  if (next.panels.some(p => !inside(p, { x: 0, y: 0, width: document.width, height: document.height }, document.safe_area))) return fail('当前页面放不下所有格框。请手工调整页面或格框尺寸后再预览；不会自动缩小画面或文字。');
  return { document: next, changed: next.panels.some((p, i) => p.x !== document.panels[i].x || p.y !== document.panels[i].y) };
}
